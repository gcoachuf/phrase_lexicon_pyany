"""Parse flashcards from the Deutsch Google Doc export."""

import hashlib
import base64
import html as html_module
import os
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

DOC_ID = os.environ.get(
    "GOOGLE_DOC_ID", "1TX2Qd17AJ9nQ_A3QUtNSNbQ5WEqt4hfFVoaAUD_ifCw"
).strip()
DEFAULT_DOC_TAB = "t.x0jh4b5vn4op"
TRAINER_START_MARKER = "*****START***TRAINER*****"
TRAINER_END_MARKER = "*****END***TRAINER*****"

_data_dir = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
HINTS_DIR = _data_dir / "hints"
HINTS_DIR.mkdir(parents=True, exist_ok=True)


def normalize_tab_id(tab: str) -> str:
    tab = tab.strip()
    if not tab:
        return ""
    if not tab.startswith("t."):
        tab = f"t.{tab}"
    return tab


def current_doc_tab() -> str:
    return normalize_tab_id(os.environ.get("GOOGLE_DOC_TAB", DEFAULT_DOC_TAB))


def export_url(doc_id: str | None = None, doc_tab: str | None = None) -> str:
    doc_id = (doc_id or DOC_ID).strip()
    tab = normalize_tab_id(doc_tab if doc_tab is not None else current_doc_tab())
    url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
    if tab:
        url += f"&tab={tab}"
    return url


def doc_source() -> dict[str, str]:
    tab = current_doc_tab()
    return {
        "doc_id": DOC_ID,
        "doc_tab": tab,
        "export_url": export_url(),
    }


def fetch_doc(url: str | None = None) -> str:
    if url is None:
        url = export_url()
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read().decode("utf-8")


def fetch_doc_html() -> str:
    url = export_url().replace("format=txt", "format=html")
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _persist_hint_src(src: str) -> str:
    if not src.startswith("data:image/"):
        return src

    header, _, payload = src.partition(",")
    if not payload:
        return ""

    raw = base64.b64decode(payload)
    ext = "png"
    if "image/jpeg" in header or "image/jpg" in header:
        ext = "jpg"
    elif "image/gif" in header:
        ext = "gif"
    elif "image/webp" in header:
        ext = "webp"

    digest = hashlib.sha1(raw).hexdigest()[:16]
    path = HINTS_DIR / f"{digest}.{ext}"
    if not path.exists():
        path.write_bytes(raw)
    return f"/api/hints/{digest}.{ext}"


ENGLISH_LINE = re.compile(
    r"^(to |a |an |the |no |slow |social |free |fuel |perception|please )",
    re.I,
)

IMAGE_URL_RE = re.compile(
    r"https?://[^\s<>\"']+"
    r"(?:\.(?:png|jpe?g|gif|webp|svg)(?:\?[^\s<>\"']*)?"
    r"|(?:docs\.google\.com|googleusercontent\.com|ggpht\.com)[^\s<>\"']*)",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _strip_after_markers(text: str, markers: tuple[str, ...] = ("Note:", "Hint:", "Visual hint:")) -> str:
    """Remove trailing field sections accidentally merged into a line."""
    cleaned = text
    for marker in markers:
        match = re.search(rf"\s{re.escape(marker)}\s*", cleaned, re.IGNORECASE)
        if match:
            cleaned = cleaned[: match.start()]
    return cleaned.strip()


def _trim_html_fragment_at_markers(fragment: str) -> str:
    match = re.search(r"Note:\s*|Hint:\s*|Visual hint:\s*|Front:\s*", fragment, re.IGNORECASE)
    if match:
        fragment = fragment[: match.start()]
    return fragment


def _extract_trainer_region(text: str) -> tuple[str, bool]:
    """Return trainer content between START/END markers, if present."""
    cleaned = text.lstrip("\ufeff")
    start = cleaned.find(TRAINER_START_MARKER)
    if start == -1:
        return cleaned, False

    start += len(TRAINER_START_MARKER)
    end = cleaned.find(TRAINER_END_MARKER, start)
    region = cleaned[start:end].strip() if end != -1 else cleaned[start:].strip()
    return region, True


def normalize_card(card: dict) -> dict:
    direction = card["direction"].strip().lower()
    if direction not in ("en_de", "de_en"):
        direction = "en_de"
    hint = normalize_text(card.get("hint", card.get("visual_hint", "")))
    hint_value, hint_type = classify_hint(hint)
    back_html = card.get("back_html", "")
    if back_html:
        back_html = strip_back_html(back_html)
    return {
        **card,
        "direction": direction,
        "front": normalize_text(card["front"]),
        "back": normalize_text(_strip_after_markers(card["back"])),
        "back_html": back_html,
        "note": normalize_text(card.get("note", "")),
        "hint": hint_value,
        "hint_type": hint_type,
    }


def classify_hint(text: str) -> tuple[str, str]:
    text = normalize_text(text) if text else ""
    if not text:
        return "", "none"

    if text.startswith("data:image/") or text.startswith("/api/hints/"):
        return text, "image"

    image_match = IMAGE_URL_RE.search(text)
    if image_match:
        return image_match.group(0).rstrip(".,;)"), "image"

    url_match = re.search(r"https?://\S+", text)
    if url_match:
        url = url_match.group(0).rstrip(".,;)")
        if re.search(r"\.(png|jpe?g|gif|webp|svg)(\?|$)", url, re.I):
            return url, "image"

    return text, "text"


def card_identity(card: dict) -> tuple[str, str, str]:
    normalized = normalize_card(card)
    return normalized["direction"], normalized["front"], normalized["back"]


def _group_key(en_de_front: str, de_en_front: str) -> str:
    raw = f"{en_de_front}|{de_en_front}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def _parse_direction_content(content: str) -> dict[str, str]:
    front = ""
    back = ""
    note_lines: list[str] = []
    hint_lines: list[str] = []
    in_hint = False
    in_back = False
    in_note = False

    def _split_inline_note(text: str) -> tuple[str, str | None]:
        match = re.search(r"\sNote:\s*", text, re.IGNORECASE)
        if not match:
            return _strip_after_markers(text), None
        return text[: match.start()].strip(), text[match.end() :].strip()

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            if in_hint:
                in_hint = False
            if in_note:
                in_note = False
            continue

        if re.match(r"^Front:\s*", stripped, re.I):
            in_hint = False
            in_back = False
            in_note = False
            front = re.sub(r"^Front:\s*", "", stripped, flags=re.I)
        elif re.match(r"^Back:\s*", stripped, re.I):
            in_hint = False
            in_note = False
            in_back = True
            back_part, inline_note = _split_inline_note(
                re.sub(r"^Back:\s*", "", stripped, flags=re.I)
            )
            back = back_part
            if inline_note:
                note_lines.append(inline_note)
                in_back = False
                in_note = True
        elif re.match(r"^Note:\s*", stripped, re.I):
            in_hint = False
            in_back = False
            in_note = True
            rest = re.sub(r"^Note:\s*", "", stripped, flags=re.I)
            if rest:
                note_lines.append(rest)
        elif re.match(r"^(?:Hint|Visual hint):\s*", stripped, re.I):
            in_back = False
            in_note = False
            in_hint = True
            rest = re.sub(r"^(?:Hint|Visual hint):\s*", "", stripped, flags=re.I)
            if rest:
                hint_lines.append(rest)
        elif in_hint:
            hint_lines.append(stripped)
        elif in_note:
            note_lines.append(stripped)
        elif in_back:
            back_part, inline_note = _split_inline_note(stripped)
            if inline_note:
                back = normalize_text(f"{back} {back_part}")
                note_lines.append(inline_note)
                in_back = False
                in_note = True
            else:
                back = normalize_text(f"{back} {back_part}")
        elif stripped.upper() in ("EN_DE", "DE_EN"):
            break

    return {
        "front": front,
        "back": back,
        "note": normalize_text(" ".join(note_lines)),
        "hint": normalize_text(" ".join(hint_lines)),
    }


def _block_hints(sections: dict[str, dict[str, str]]) -> dict[str, str]:
    """Image hints are shared across directions; text hints stay per direction."""
    shared_image = ""
    for payload in sections.values():
        value, hint_type = classify_hint(payload.get("hint", ""))
        if hint_type == "image":
            shared_image = value
            break

    if shared_image:
        return {direction: shared_image for direction in sections}

    return {direction: payload.get("hint", "") for direction, payload in sections.items()}


def _extract_html_image_hints(html: str) -> list[str]:
    hints: list[str] = []
    for part in re.split(r"Hint:\s*</span>", html, flags=re.IGNORECASE)[1:]:
        img = re.search(r'<img[^>]+src="([^"]+)"', part, re.IGNORECASE)
        hints.append(img.group(1) if img else "")
    return hints


def _apply_group_image_hints(cards: list[dict]) -> None:
    by_group: dict[str, list[dict]] = {}
    for card in cards:
        by_group.setdefault(card["group_key"], []).append(card)

    for group in by_group.values():
        shared_image = ""
        for card in group:
            _, hint_type = classify_hint(card.get("hint", ""))
            if hint_type == "image":
                shared_image = card["hint"]
                break
        if shared_image:
            for card in group:
                card["hint"] = shared_image


def merge_html_image_hints(cards: list[dict], html: str) -> None:
    images = _extract_html_image_hints(html)
    img_idx = 0
    for card in cards:
        if card.get("hint"):
            continue
        while img_idx < len(images) and not images[img_idx]:
            img_idx += 1
        if img_idx >= len(images):
            break
        card["hint"] = _persist_hint_src(images[img_idx])
        img_idx += 1
    _apply_group_image_hints(cards)


UNDERLINE_CLASS_RE = re.compile(
    r"\.(c\d+)\{[^}]*text-decoration:\s*underline[^}]*\}",
    re.IGNORECASE,
)


def _underline_classes(html: str) -> set[str]:
    return set(UNDERLINE_CLASS_RE.findall(html))


class _BackHtmlConverter(HTMLParser):
    def __init__(self, underline_classes: set[str]):
        super().__init__(convert_charrefs=True)
        self._underline_classes = underline_classes
        self._stack: list[str] = []
        self._parts: list[str] = []

    def _span_is_underline(self, attrs: list[tuple[str, str | None]]) -> bool:
        attr_map = {key: value or "" for key, value in attrs}
        classes = attr_map.get("class", "").split()
        if self._underline_classes.intersection(classes):
            return True
        style = attr_map.get("style", "").replace(" ", "")
        return "text-decoration:underline" in style

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "span":
            if self._span_is_underline(attrs):
                self._parts.append("<strong>")
                self._stack.append("u")
            else:
                self._stack.append("n")
        elif tag in ("u", "strong", "b"):
            self._parts.append("<strong>")
            self._stack.append("u")

    def handle_endtag(self, tag: str) -> None:
        if tag == "span" and self._stack:
            kind = self._stack.pop()
            if kind == "u":
                self._parts.append("</strong>")
        elif tag in ("u", "strong", "b") and self._stack and self._stack[-1] == "u":
            self._stack.pop()
            self._parts.append("</strong>")

    def handle_data(self, data: str) -> None:
        text = data.replace("\xa0", " ")
        self._parts.append(html_module.escape(text))

    def result(self) -> str:
        while self._stack:
            kind = self._stack.pop()
            if kind == "u":
                self._parts.append("</strong>")
        return _strip_after_markers(re.sub(r"\s+", " ", "".join(self._parts)).strip())


def strip_back_html(back_html: str) -> str:
    """Keep only <strong> markup for safe answer rendering."""
    if not back_html:
        return ""
    text = back_html.replace("<u>", "<strong>").replace("</u>", "</strong>")
    text = re.sub(r"<(?!/?strong>)[^>]+>", "", text, flags=re.IGNORECASE)
    text = _strip_after_markers(text)
    if "<strong>" not in text:
        return ""
    return text.strip()


def plain_back_text(back: str, back_html: str = "") -> str:
    if back_html:
        return _strip_after_markers(
            re.sub(r"</?(?:u|strong)>", "", back_html, flags=re.IGNORECASE)
        )
    return back


def _extract_html_back_fragments(html: str) -> list[str]:
    """Take each Back: field through the end of its paragraph.

    Google Docs often splits one Back line across several <span>s (plain text,
    then underlined answer words). Stopping at the first </span> drops those
    later spans, so pills never appear.
    """
    fragments: list[str] = []
    for match in re.finditer(r"Back:\s*", html, re.IGNORECASE):
        rest = html[match.end() :]
        if rest.startswith("</span>"):
            rest = rest[len("</span>") :]
        end = re.search(r"</p>\s*<p", rest, re.IGNORECASE)
        if not end:
            end = re.search(r"</p>", rest, re.IGNORECASE)
        fragment = rest[: end.start() if end else len(rest)]
        fragments.append(_trim_html_fragment_at_markers(fragment))
    return fragments


def _fragment_to_back_html(fragment: str, underline_classes: set[str]) -> str:
    fragment = _trim_html_fragment_at_markers(fragment)
    converter = _BackHtmlConverter(underline_classes)
    converter.feed(fragment)
    return strip_back_html(converter.result())


def merge_html_back_formatting(
    cards: list[dict], html: str, style_html: str | None = None
) -> None:
    """Apply underline formatting from Google Doc HTML exports."""
    style_source = style_html or html
    underline_classes = _underline_classes(style_source)
    fragments = _extract_html_back_fragments(html)
    for card, fragment in zip(cards, fragments):
        formatted = _fragment_to_back_html(fragment, underline_classes)
        if formatted:
            card["back_html"] = formatted


def parse_cloze_block(block: str) -> list[dict]:
    block = block.strip()
    if not block or block.startswith("Phrase Lexicon"):
        return []

    parts = re.split(r"^(EN_DE|DE_EN)\s*$", block, flags=re.MULTILINE | re.IGNORECASE)
    sections: dict[str, dict[str, str]] = {}
    for index in range(1, len(parts), 2):
        direction = parts[index].lower()
        sections[direction] = _parse_direction_content(parts[index + 1])

    if not sections:
        return []

    group_key = _group_key(
        sections.get("en_de", {}).get("front", block[:80]),
        sections.get("de_en", {}).get("front", block[:80]),
    )
    hints = _block_hints(sections)

    cards = []
    for direction, payload in sections.items():
        if payload["front"] and payload["back"]:
            cards.append(
                {
                    "direction": direction,
                    "front": payload["front"],
                    "back": payload["back"],
                    "note": payload.get("note", ""),
                    "hint": hints.get(direction, ""),
                    "group_key": group_key,
                    "deck": "phrase_lexicon",
                    "source": "cloze",
                }
            )
    return cards


def _card_section(text: str) -> tuple[str, str]:
    for heading in ("Trainer", "Phrase Trainer"):
        if heading in text:
            section = text.split(heading, 1)[1]
            if "Phrase Lexicon" in section:
                section = section.split("Phrase Lexicon", 1)[0]
            return section, "trainer"

    if "Phrase Lexicon" in text:
        return text.split("Phrase Lexicon", 1)[1], "phrase_lexicon"

    # Dedicated trainer tab export: cloze blocks without a section heading.
    if re.search(r"^(EN_DE|DE_EN)\s*$", text, re.MULTILINE | re.IGNORECASE):
        return text, "trainer"

    return text, "phrase_lexicon"


def parse_cloze_cards(text: str) -> list[dict]:
    section, deck = _card_section(text)

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
    html: str | None = None
    html_styles: str | None = None
    if text is None:
        text = fetch_doc()
        try:
            html = fetch_doc_html()
            html_styles = html
        except Exception:
            html = None

    text, trainer_marked = _extract_trainer_region(text)
    if html:
        html, _ = _extract_trainer_region(html)

    cloze = parse_cloze_cards(text)
    if html and cloze:
        merge_html_image_hints(cloze, html)
        merge_html_back_formatting(cloze, html, style_html=html_styles or html)
    legacy = parse_phrase_lexicon_legacy(text) if not cloze and not trainer_marked else []
    gwod = parse_gwod_cards(text) if not trainer_marked else []
    cards = cloze + legacy + gwod

    seen: set[tuple[str, str, str]] = set()
    unique: list[dict] = []
    for card in cards:
        key = card_identity(card)
        if key not in seen:
            seen.add(key)
            unique.append(normalize_card(card))
    return unique
