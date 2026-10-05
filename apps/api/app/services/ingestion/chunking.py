"""Section- and page-aware chunking. Each chunk keeps page number + section for citation."""
import re
from dataclasses import dataclass

HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*$")
NUMBERED_HEADING = re.compile(r"^(\d+(?:\.\d+)*)[.)]?\s+([A-Z][^.!?]{2,80})$")

TARGET_WORDS = 170
MAX_WORDS = 240
OVERLAP_WORDS = 25


@dataclass
class Chunk:
    index: int
    page_no: int
    section: str
    text: str


def _blocks(page_text: str, section: str) -> list[tuple[str, str]]:
    """Split a page into (section, paragraph) blocks tracking the current heading."""
    out: list[tuple[str, str]] = []
    buf: list[str] = []

    def flush():
        if buf:
            out.append((section, " ".join(buf).strip()))
            buf.clear()

    for raw in page_text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        h = HEADING.match(line) or (NUMBERED_HEADING.match(line) if len(line) < 90 else None)
        if h:
            flush()
            section = h.group(2).strip() if h.re is HEADING else line
            continue
        buf.append(line)
    flush()
    return out


def _window(words: list[str]) -> list[list[str]]:
    if len(words) <= MAX_WORDS:
        return [words]
    wins, i = [], 0
    while i < len(words):
        wins.append(words[i: i + TARGET_WORDS])
        if i + TARGET_WORDS >= len(words):
            break
        i += TARGET_WORDS - OVERLAP_WORDS
    return wins


def chunk_pages(pages: list[tuple[int, str]]) -> list[Chunk]:
    chunks: list[Chunk] = []
    section = ""
    for page_no, text in pages:
        cur_words: list[str] = []
        cur_section = section
        blocks = _blocks(text, section)
        for sec, para in blocks:
            words = para.split()
            # start a new chunk on section change or when the target size is reached
            if cur_words and (sec != cur_section or len(cur_words) + len(words) > TARGET_WORDS + 40):
                for w in _window(cur_words):
                    chunks.append(Chunk(len(chunks), page_no, cur_section, " ".join(w)))
                cur_words = []
            cur_section = sec
            cur_words.extend(words)
        if cur_words:
            for w in _window(cur_words):
                chunks.append(Chunk(len(chunks), page_no, cur_section, " ".join(w)))
        if blocks:
            section = blocks[-1][0]
    return [c for c in chunks if len(c.text) >= 40]
