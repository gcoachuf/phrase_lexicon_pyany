"""Quick parser checks for the cloze card format."""

from parser import merge_html_back_formatting, parse_all, parse_cloze_block, parse_cloze_cards

EXAMPLE = """---
EN_DE
Front: to contribute to the well-being of others: zum Wohl anderer _____
Back: beitragen

DE_EN
Front: zum Wohl anderer beitragen: to _____ to the well-being of others
Back: contribute

---"""

EXAMPLE_HTML = """<html><head><style>.c2{text-decoration:underline}</style></head><body>
<p><span>Back: </span><span class="c2">beitragen</span></p>
<p><span>Back: </span><span class="c2">contribute</span><span> more</span></p>
</body></html>"""


def test_cloze_parse():
    cards = parse_cloze_cards(EXAMPLE)
    assert len(cards) == 2
    en_de = next(c for c in cards if c["direction"] == "en_de")
    de_en = next(c for c in cards if c["direction"] == "de_en")
    assert "_____" in en_de["front"]
    assert en_de["back"] == "beitragen"
    assert de_en["back"] == "contribute"


def test_back_underline_from_html():
    cards = parse_cloze_cards(EXAMPLE)
    merge_html_back_formatting(cards, EXAMPLE_HTML)
    en_de = next(c for c in cards if c["direction"] == "en_de")
    de_en = next(c for c in cards if c["direction"] == "de_en")
    assert en_de["back_html"] == "<strong>beitragen</strong>"
    assert de_en["back_html"] == "<strong>contribute</strong> more"


NOTE_BLOCK = """---
DE_EN
Front: Keine _____ [noun] _____ [preposition] anderen Menschen zu haben bedeutet Freiheit.
Back: Keine Verantwortung gegenüber anderen Menschen zu haben bedeutet Freiheit. Note: Verantwortung pairs with gegenüber (towards/faced with).
Hint: example

---"""


def test_note_not_in_back():
    cards = parse_cloze_cards(NOTE_BLOCK)
    assert len(cards) == 1
    card = cards[0]
    assert card["back"] == (
        "Keine Verantwortung gegenüber anderen Menschen zu haben bedeutet Freiheit."
    )
    assert "pairs with" not in card["back"]
    assert "Note" not in card["back"]
    assert card["note"] == "Verantwortung pairs with gegenüber (towards/faced with)."


def test_note_on_own_line_not_in_back():
    block = """---
DE_EN
Front: test _____
Back: answer line one
answer line two
Note: this is a note only
---"""
    cards = parse_cloze_cards(block)
    assert cards[0]["back"] == "answer line one answer line two"
    assert cards[0]["note"] == "this is a note only"
    assert "note only" not in cards[0]["back"]


if __name__ == "__main__":
    test_cloze_parse()
    test_back_underline_from_html()
    test_note_not_in_back()
    test_note_on_own_line_not_in_back()
    print("ok")
