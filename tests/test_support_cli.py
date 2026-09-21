"""Tests for scripts/support_login.py.

Run as a subprocess: the script rebinds the module-level Flask app to a
different database, which would contaminate the in-process fixtures.
"""
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "support_login.py")


def run_cli(*args):
    return subprocess.run([sys.executable, SCRIPT] + list(args),
                          capture_output=True, text=True, cwd=REPO_ROOT)


@pytest.fixture
def populated_db(tmp_path):
    """A real kidallowance database with one account, built out of process."""
    path = tmp_path / "app.db"
    build = (
        "import sys; sys.path.insert(0, %r)\n"
        "from app import app, db, models\n"
        "app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///%s'\n"
        "del app.extensions['sqlalchemy']\n"
        "db.init_app(app)\n"
        "with app.app_context():\n"
        "    db.create_all()\n"
        "    u = models.User(firstname='Zsolt', email='real@example.com')\n"
        "    u.set_password('pw'); db.session.add(u); db.session.commit()\n"
        % (REPO_ROOT, path)
    )
    subprocess.run([sys.executable, "-c", build], check=True, cwd=REPO_ROOT,
                   capture_output=True)
    return path


def test_empty_database_explains_itself(tmp_path):
    """An empty file must produce guidance, not a SQLAlchemy traceback."""
    empty = tmp_path / "empty.db"
    empty.write_bytes(b"")

    result = run_cli("--email", "someone@example.com", "--database",
                     str(empty))

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "empty (0 bytes)" in result.stderr


def test_missing_database_file_is_reported(tmp_path):
    result = run_cli("--email", "someone@example.com", "--database",
                     str(tmp_path / "nope.db"))

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "No such database file" in result.stderr


def test_database_without_tables_explains_itself(tmp_path):
    """A non-empty SQLite file that has no kidallowance schema."""
    import sqlite3
    path = tmp_path / "other.db"
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE unrelated (x INTEGER)")
    conn.commit()
    conn.close()

    result = run_cli("--email", "someone@example.com", "--database",
                     str(path))

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "No kidallowance tables" in result.stderr
    assert "--database" in result.stderr, "should suggest the real DB path"


def test_unknown_email_is_reported(populated_db):
    result = run_cli("--email", "nobody@example.com", "--database",
                     str(populated_db))

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "No account found" in result.stderr


def test_mints_a_url_for_a_real_account(populated_db):
    result = run_cli("--email", "real@example.com", "--database",
                     str(populated_db), "--base-url",
                     "https://kidallowance.net")

    assert result.returncode == 0, result.stderr
    assert "real@example.com" in result.stdout
    assert "https://kidallowance.net/support?t=" in result.stdout


def test_does_not_write_to_the_database(populated_db):
    """Minting a token must leave the database byte-identical."""
    before = populated_db.read_bytes()
    result = run_cli("--email", "real@example.com", "--database",
                     str(populated_db))
    assert result.returncode == 0
    assert populated_db.read_bytes() == before
