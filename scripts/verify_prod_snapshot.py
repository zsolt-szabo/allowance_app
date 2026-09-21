#!/usr/bin/env python3
"""Read-only integrity report for a kidallowance database.

Checks the invariants the application relies on but never enforces.  Run this
against a *copy* of the production database before starting the port, so that
pre-existing history can be told apart from regressions introduced later:

    sqlite3 /path/to/app.db ".backup /tmp/snapshot.db"
    ./scripts/verify_prod_snapshot.py /tmp/snapshot.db

Expect findings on a database that has been live for years -- none of these
rules has ever been enforced.  The point is to record the starting state.

Uses raw sqlite3 rather than the ORM so it stays usable even as the models
change underneath it, and so it can never write to the file it inspects.
"""
import argparse
import os
import sqlite3
import sys
from collections import defaultdict

ACCOUNTS = range(1, 6)
LOCATIONS = range(1, 8)


def money(value):
    return round(value or 0, 2)


class Report:
    def __init__(self):
        self.findings = defaultdict(list)
        self.checked = defaultdict(int)

    def add(self, category, message):
        self.findings[category].append(message)

    def count(self, category, n=1):
        self.checked[category] += n

    @property
    def total(self):
        return sum(len(v) for v in self.findings.values())


def connect(path):
    # file:...?mode=ro guarantees we cannot modify the snapshot.
    uri = "file:%s?mode=ro" % os.path.abspath(path)
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def check_ledger(conn, report):
    """Per kid: totals must chain from changes, and the two axes must agree."""
    kids = conn.execute("SELECT id, firstname FROM kid ORDER BY id").fetchall()
    for kid in kids:
        rows = conn.execute(
            "SELECT * FROM ledger WHERE kid_id = ? ORDER BY id",
            (kid["id"],)).fetchall()
        prev_acc = [0] * 5
        prev_loc = [0] * 7
        for row in rows:
            report.count("ledger rows")
            acc_tot = [money(row["total_acc%s" % i]) for i in ACCOUNTS]
            loc_tot = [money(row["total_loc%s" % j]) for j in LOCATIONS]
            acc_chg = [money(row["change_acc%s" % i]) for i in ACCOUNTS]
            loc_chg = [money(row["change_loc%s" % j]) for j in LOCATIONS]

            # 1. The two-axis invariant.
            if money(sum(acc_tot)) != money(sum(loc_tot)):
                report.add(
                    "two-axis imbalance",
                    "kid %s (%s) ledger row %s: accounts total %s but "
                    "locations total %s"
                    % (kid["id"], kid["firstname"], row["id"],
                       money(sum(acc_tot)), money(sum(loc_tot))))

            # 2. Running totals must equal previous totals plus this delta.
            want_acc = [money(p + c) for p, c in zip(prev_acc, acc_chg)]
            want_loc = [money(p + c) for p, c in zip(prev_loc, loc_chg)]
            if acc_tot != want_acc:
                report.add(
                    "totals do not chain",
                    "kid %s ledger row %s: account totals %s, expected %s"
                    % (kid["id"], row["id"], acc_tot, want_acc))
            if loc_tot != want_loc:
                report.add(
                    "totals do not chain",
                    "kid %s ledger row %s: location totals %s, expected %s"
                    % (kid["id"], row["id"], loc_tot, want_loc))

            # 3. No bucket should ever be negative.
            for i, value in zip(ACCOUNTS, acc_tot):
                if value < 0:
                    report.add("negative balance",
                               "kid %s ledger row %s: account %s = %s"
                               % (kid["id"], row["id"], i, value))
            for j, value in zip(LOCATIONS, loc_tot):
                if value < 0:
                    report.add("negative balance",
                               "kid %s ledger row %s: location %s = %s"
                               % (kid["id"], row["id"], j, value))

            prev_acc, prev_loc = acc_tot, loc_tot


def check_allowances(conn, report):
    """Percentages must sum to 100, counting only active buckets."""
    rows = conn.execute(
        "SELECT a.*, k.firstname AS kid_name, k.id AS kid_pk, k.* "
        "FROM allowance a JOIN kid k ON k.id = a.kid_id "
        "ORDER BY a.id").fetchall()
    for row in rows:
        report.count("allowances")
        acc_sum = sum(row["account%s_perc" % i] or 0
                      for i in ACCOUNTS if row["acct%s_used" % i])
        loc_sum = sum(row["location%s_perc" % j] or 0
                      for j in LOCATIONS if row["location%s_used" % j])
        if round(acc_sum, 2) != 100:
            report.add(
                "allowance percentages",
                "allowance %s (kid %s): active sub-account percentages sum to "
                "%s, not 100" % (row["id"], row["kid_pk"], round(acc_sum, 2)))
        if round(loc_sum, 2) != 100:
            report.add(
                "allowance percentages",
                "allowance %s (kid %s): active location percentages sum to "
                "%s, not 100" % (row["id"], row["kid_pk"], round(loc_sum, 2)))


def check_payout_days(conn, report):
    """The intended ('allowance_id', 'payout_day') uniqueness is not enforced
    by the schema, so duplicates -- which cause double payouts -- can exist."""
    duplicates = conn.execute(
        "SELECT allowance_id, payout_day, COUNT(*) AS n FROM allowance_days "
        "GROUP BY allowance_id, payout_day HAVING n > 1").fetchall()
    for row in duplicates:
        report.add(
            "duplicate payout days",
            "allowance %s has payout day %s listed %s times -- it pays out "
            "%s times that day" % (row["allowance_id"], row["payout_day"],
                                   row["n"], row["n"]))

    out_of_range = conn.execute(
        "SELECT id, allowance_id, payout_day FROM allowance_days "
        "WHERE payout_day < 1 OR payout_day > 28").fetchall()
    for row in out_of_range:
        report.add("payout day out of range",
                   "allowance_days %s: payout_day = %s (expected 1-28)"
                   % (row["id"], row["payout_day"]))


def check_orphans(conn, report):
    """Rows whose parent no longer exists (deletes are hand-rolled)."""
    queries = [
        ("kid with no parent",
         "SELECT k.id FROM kid k LEFT JOIN user u ON u.id = k.parent_id "
         "WHERE u.id IS NULL"),
        ("allowance with no kid",
         "SELECT a.id FROM allowance a LEFT JOIN kid k ON k.id = a.kid_id "
         "WHERE k.id IS NULL"),
        ("allowance_days with no allowance",
         "SELECT d.id FROM allowance_days d "
         "LEFT JOIN allowance a ON a.id = d.allowance_id WHERE a.id IS NULL"),
        ("ledger with no kid",
         "SELECT l.id FROM ledger l LEFT JOIN kid k ON k.id = l.kid_id "
         "WHERE k.id IS NULL"),
    ]
    for label, sql in queries:
        for row in conn.execute(sql).fetchall():
            report.add("orphaned rows", "%s: id %s" % (label, row[0]))


def check_allowance_without_days(conn, report):
    """The payout engine is driven by an inner join, so an allowance with no
    payout days silently never pays."""
    rows = conn.execute(
        "SELECT a.id, a.kid_id, a.nickname FROM allowance a "
        "LEFT JOIN allowance_days d ON d.allowance_id = a.id "
        "WHERE d.id IS NULL").fetchall()
    for row in rows:
        report.add("allowance never pays out",
                   "allowance %s (%r, kid %s) has no payout days"
                   % (row["id"], row["nickname"], row["kid_id"]))


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("database", help="path to a COPY of app.db")
    parser.add_argument("--quiet", action="store_true",
                        help="only print the summary")
    args = parser.parse_args()

    if not os.path.exists(args.database):
        parser.error("no such file: %s" % args.database)

    report = Report()
    with connect(args.database) as conn:
        check_ledger(conn, report)
        check_allowances(conn, report)
        check_payout_days(conn, report)
        check_orphans(conn, report)
        check_allowance_without_days(conn, report)

    print("kidallowance integrity report for %s" % args.database)
    print("=" * 72)
    for label, n in sorted(report.checked.items()):
        print("  inspected %s %s" % (n, label))
    print()

    if not report.findings:
        print("No problems found.")
        return 0

    for category in sorted(report.findings):
        items = report.findings[category]
        print("%s (%s)" % (category.upper(), len(items)))
        shown = items if not args.quiet else items[:5]
        for item in shown:
            print("   - %s" % item)
        if args.quiet and len(items) > len(shown):
            print("   ... and %s more" % (len(items) - len(shown)))
        print()

    print("=" * 72)
    print("%s finding(s) across %s categor(ies)."
          % (report.total, len(report.findings)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
