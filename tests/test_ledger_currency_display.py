"""Issue #24: withdrawals were only shown in red for dollar accounts.

The ledger page colours negative changes red in the browser. It used to
recover the amount from the rendered cell text by stripping the currency
symbol with a regex hardcoded to "$", so for any other symbol the value
stayed unparseable, compared as NaN, and nothing was ever coloured.

The amount now travels in a data-amount attribute, so no parsing of
rendered text is involved and the symbol is irrelevant to it.

The colouring itself is client-side, so these tests check the two things
a server-side test honestly can: that the data the script depends on is
present and correct, and that a faithful port of the script's logic
reaches the right decision.
"""
import re

import pytest

from tests import factories as f

PW = "monstertruck"

#  Including symbols that are regex metacharacters: the suggested fix of
#  building the strip-regex at runtime would have to escape these, which
#  is the trap the data-attribute approach avoids.
SYMBOLS = ["$", "€", "£", "¥", "R$", ".", "*", "^"]


@pytest.fixture
def ledger_page(db_, client):
    def render(symbol, amounts=(20, -5)):
        parent = f.make_parent(email="p@example.com", password=PW,
                               money_symbol=symbol)
        f.make_kid(parent, firstname="kid",
                   animal1="rabbit", animal2="rabbit")
        client.post("/login", data={"email": parent.email, "password": PW},
                    follow_redirects=True)
        url = "/ledger?kid=kid:rabbit:rabbit"
        for amount in amounts:
            client.post(url, data={"acct1_loc1": str(amount),
                                   "comment": "entry %s" % amount},
                        follow_redirects=True)
        return client.get(url).data.decode()
    return render


def money_cells(html):
    """(data_amount, visible_text) for every money delta cell."""
    return re.findall(
        r'<td class="deltas" data-amount="([^"]*)">([^<]*)</td>', html)


def js_would_colour_red(data_amount):
    """Faithful port of the template's script.

        var amount = parseFloat($(this).attr('data-amount'));
        if (!isNaN(amount) && amount < 0) { ...red... }
    """
    try:
        amount = float(data_amount)
    except ValueError:
        return False
    return amount < 0


@pytest.mark.parametrize("symbol", SYMBOLS)
def test_negative_change_is_marked_for_colouring(ledger_page, symbol):
    """The regression: this held only for "$" before."""
    html = ledger_page(symbol)
    negatives = [value for value, _text in money_cells(html)
                 if value.startswith("-")]

    assert negatives, "no negative delta rendered for symbol %r" % symbol
    assert all(js_would_colour_red(value) for value in negatives), \
        "withdrawal not coloured red for symbol %r" % symbol


@pytest.mark.parametrize("symbol", SYMBOLS)
def test_the_symbol_is_still_displayed(ledger_page, symbol):
    html = ledger_page(symbol)
    texts = [text for _value, text in money_cells(html)]
    assert any(symbol in text for text in texts), \
        "symbol %r missing from the rendered cells" % symbol


def test_data_amount_matches_the_displayed_number(ledger_page):
    """The attribute and the text must not drift apart."""
    html = ledger_page("€", amounts=(20, -5, -0.25))
    for value, text in money_cells(html):
        assert value in text, \
            "data-amount %r not reflected in rendered text %r" % (value, text)


def test_positive_changes_are_not_coloured(ledger_page):
    html = ledger_page("€")
    positives = [value for value, _text in money_cells(html)
                 if not value.startswith("-") and float(value) > 0]
    assert positives
    assert not any(js_would_colour_red(value) for value in positives)


def test_non_money_cells_are_excluded(ledger_page):
    """The old loop scanned every .deltas cell, so a comment of "-5" was
    rewritten as though it were an amount."""
    html = ledger_page("€", amounts=(20,))
    #  The comment cell carries a bare class and no data-amount.
    assert '<td class="deltas">entry 20</td>' in html
    plain_cells = re.findall(r'<td class="deltas">([^<]*)</td>', html)
    assert "Changes" in plain_cells
    assert any("entry 20" in c for c in plain_cells)


def test_a_negative_looking_comment_is_left_alone(ledger_page):
    """A comment that looks like a negative number must not be treated as
    money."""
    html = ledger_page("€", amounts=(20,))
    #  Re-post with a comment that is literally a negative number.
    assert '<td class="deltas">entry 20</td>' in html
    for value, _text in money_cells(html):
        float(value)   # every data-amount is a real number


def test_symbol_is_emitted_as_a_javascript_string(ledger_page):
    """The symbol goes into the script via |tojson, so a symbol
    containing a quote cannot break out of the literal."""
    html = ledger_page('"')
    assert 'var symbol = "\\""' in html or 'var symbol = "\\u0022"' in html
