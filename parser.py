"""Parse flashcards from the Deutsch Google Doc export."""

import hashlib
import os
import re
import urllib.request

DOC_ID = os.environ.get(
    "GOOGLE_DOC_ID", "1TX2Qd17AJ9nQ_A3QUtNSNbQ5WEqt4hfFVoaAUD_ifCw"
)
EXPORT_URL = f"https://docs.google.com/document/d/{DOC_ID}/export?format=txt"

ENGLISH_LINE = re.compile(
    r"^(to |a |an |the |no |slow |social |free |fuel |perception|please )",
    re.I,
)

CLOZE_SECTION = re.compile(
    r"^(EN_DE|DE_EN)\s*\nFront:\s*(.+?)\s*\nBack:\s*(.+?)(?=\n\s*\n|\n(?:EN_DE|DE_EN)\s*\n|\Z)",
    re.MULTILINE | re.DOTALL,
)


def fetch_doc(url: str = EXPORT_URL) -> str:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read().decode("utf-8")


def _group_key(en_de_front: str, de_en_front: str) -> str:
    raw = f"{en_de_front}|{de_en_front}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def parse_cloze_block(block: str) -> list[dict]:
    block = block.strip()
    if not block:
        return []

    sections: dict[str, dict[str, str]] = {}
    for match in CLOZE_SECTION.finditer(block):
        direction = match.group(1).lower()
        sections[direction] = {
            "front": match.group(2).strip(),
            "back": match.group(3).strip(),
        }

    if not sections:
        return []

    group_key = _group_key(
        sections.get("en_de", {}).get("front", block[:80]),
        sections.get("de_en", {}).get("front", block[:80]),
    )

    cards = []
    for direction, payload in sections.items():
        if payload["front"] and payload["back"]:
            cards.append(
                {
                    "direction": direction,
                    "front": payload["front"],
                    "back": payload["back"],
                    "group_key": group_key,
                    "deck": "phrase_lexicon",
                    "source": "cloze",
                }
            )
    return cards


def _card_section(text: str) -> str:
    if "Phrase Trainer" in text:
        return text.split("Phrase Trainer", 1)[1]
    if "Phrase Lexicon" in text:
        return text.split("Phrase Lexicon", 1)[1]
    return text


def parse_cloze_cards(text: str) -> list[dict]:
    section = _card_section(text)
    deck = "phrase_trainer" if "Phrase Trainer" in text else "phrase_lexicon"

    cards: list[dict] = []
    for block in re.split(r"^---\s*$", section, flags=re.MULTILINE):
        for card in parse_cloze_block(block):
            card["deck"] = deck
            cards.append(card)
    return cards


def parse_phrase_lexicon_legacy(text: str) -> list[dict]:
    if "Phrase Lexicon" not in text:
        return []

    section = text.split("Phrase Lexicon", 1)[1]
    if "---" in section:
        return []

    lines = [ln.strip() for ln in section.splitlines() if ln.strip()]

    cards = []
    i = 0
    while i < len(lines) - 1:
        front, back = lines[i], lines[i + 1]
        if ENGLISH_LINE.match(front) or "/" in front:
            group_key = hashlib.sha1(f"{front}|{back}".encode()).hexdigest()[:16]
            cards.append(
                {
                    "direction": "en_de",
                    "front": front,
                    "back": back,
                    "group_key": group_key,
                    "deck": "phrase_lexicon",
                    "source": "phrase_lexicon_legacy",
                }
            )
            cards.append(
                {
                    "direction": "de_en",
                    "front": back,
                    "back": front,
                    "group_key": group_key,
                    "deck": "phrase_lexicon",
                    "source": "phrase_lexicon_legacy",
                }
            )
            i += 2
        else:
            i += 1
    return cards


def parse_gwod_cards(text: str) -> list[dict]:
    cards = []
    for match in re.finditer(
        r"Today's GWoD:\s*(.+?)\s*\n(?:.*?\n){0,80}?^WU:\s*(.+)$",
        text,
        re.MULTILINE,
    ):
        word = re.sub(r"\s*\([^)]+\)\s*$", "", match.group(1)).strip()
        meaning = match.group(2).strip()
        if word and meaning:
            group_key = hashlib.sha1(f"{meaning}|{word}".encode()).hexdigest()[:16]
            cards.append(
                {
                    "direction": "en_de",
                    "front": meaning,
                    "back": word,
                    "group_key": group_key,
                    "deck": "gwod",
                    "source": "gwod",
                }
            )
            cards.append(
                {
                    "direction": "de_en",
                    "front": word,
                    "back": meaning,
                    "group_key": group_key,
                    "deck": "gwod",
                    "source": "gwod",
                }
            )
    return cards


def parse_all(text: str | None = None) -> list[dict]:
    if text is None:
        text = fetch_doc()

    cloze = parse_cloze_cards(text)
    legacy = parse_phrase_lexicon_legacy(text) if not cloze else []
    cards = cloze + legacy + parse_gwod_cards(text)

    seen: set[tuple[str, str, str]] = set()
    unique: list[dict] = []
    for card in cards:
        key = (card["direction"], card["front"], card["back"])
        if key not in seen:
            seen.add(key)
            unique.append(card)
    return unique
