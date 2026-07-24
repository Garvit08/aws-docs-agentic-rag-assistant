from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

CONTENT_ID = "main-col-body"
SOURCE_TYPE = "official_aws_docs"

#todo: Need to pass these from properties 
CHUNK_SIZE = 1000            
CHUNK_OVERLAP = 150         
SHORT_SECTION_THRESHOLD = 40  
SLUG_MAX_LEN = 50

_HEADING_TAGS = {"h1", "h2", "h3"}
_LEAF_BLOCK_TAGS = {"p", "pre", "li", "blockquote", "dt", "dd", "caption", "figcaption"}
_WHOLE_BLOCK_TAGS = {"table"}  # emit combined text, do not descend (avoids cell fragmentation)
_SKIP_TAGS = {"script", "style", "noscript"}


@dataclass
class Chunk:
    """A retrieval chunk plus the metadata required on every chunk."""

    content: str
    source_url: str
    title: str
    service: str
    section: str
    document_id: str
    chunk_id: str
    source_type: str = SOURCE_TYPE



def _normalize(text: str) -> str:
    """Collapse runs of whitespace to single spaces and trim."""
    return re.sub(r"\s+", " ", text).strip()


def _slugify(text: str) -> str:
    """lowercase, strip punctuation, spaces/underscores -> hyphens, cap length."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)   
    text = re.sub(r"[\s_]+", "-", text)    
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:SLUG_MAX_LEN].rstrip("-") or "section"



def _content_root(html: bytes | str):
    """Return the #main-col-body element with script/style/noscript removed."""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.find(id=CONTENT_ID)
    if root is None:
        raise ValueError(f"#{CONTENT_ID} not found in document")
    for tag in root.find_all(_SKIP_TAGS):
        tag.decompose()
    return root


def _iter_blocks(node):
    
    # print("iter blocks:", node)

    print("3####"*30)
    for child in node.children:
        name = getattr(child, "name", None)
        if name is None or name in _SKIP_TAGS:
            continue
        if name in _HEADING_TAGS:
            text = _normalize(child.get_text(" ", strip=True))
            if text:
                yield ("heading", text)
        elif name in _LEAF_BLOCK_TAGS:
            text = child.get_text().strip("\n") if name == "pre" \
                else _normalize(child.get_text(" ", strip=True))
            if text:
                yield ("block", text)
        elif name in _WHOLE_BLOCK_TAGS:
            text = _normalize(child.get_text(" ", strip=True))
            if text:
                yield ("block", text)
        else:
            yield from _iter_blocks(child)



def _group_sections(events) -> list[dict]:
    """Group the linear event stream into sections keyed by nearest heading."""
    sections: list[dict] = []
    current: dict = {"heading": None, "paragraphs": []}
    for kind, text in events:
        if kind == "heading":
            if current["heading"] is not None or current["paragraphs"]:
                sections.append(current)
            current = {"heading": text, "paragraphs": []}
        else:
            current["paragraphs"].append(text)
    if current["heading"] is not None or current["paragraphs"]:
        sections.append(current)
    return sections


def _fold_short_sections(sections: list[dict]) -> list[dict]:
    """Fold trivially short sections (body <=40 chars) into the next section."""
    result: list[dict] = []
    carry: list[str] = []
    for sec in sections:
        body = "\n\n".join(sec["paragraphs"]).strip()
        if len(body) <= SHORT_SECTION_THRESHOLD:
            if sec["heading"]:
                carry.append(sec["heading"])
            if body:
                carry.append(body)
            continue
        result.append({"heading": sec["heading"], "paragraphs": carry + sec["paragraphs"]})
        carry = []
    if carry:  
        if result:
            result[-1]["paragraphs"].extend(carry)
        else:
            result.append({"heading": None, "paragraphs": carry})
    return result



def _overlap_tail(text: str, overlap: int) -> str:
    """Return up to `overlap` trailing chars, trimmed to a word boundary."""
    if overlap <= 0 or len(text) <= overlap:
        return ""
    tail = text[-overlap:]
    space = tail.find(" ")
    return tail[space + 1:].strip() if space != -1 else tail.strip()


def _char_windows(text: str, size: int, overlap: int) -> list[str]:
    """Hard-split an oversized single block into overlapping char windows."""
    windows: list[str] = []
    start, n, step = 0, len(text), max(size - overlap, 1)
    while start < n:
        end = min(start + size, n)
        if end < n:  # prefer to break at whitespace
            space = text.rfind(" ", start, end)
            if space > start:
                end = space
        windows.append(text[start:end].strip())
        if end >= n:
            break
        start = max(end - overlap, start + step - size + 1, start + 1)
    return [w for w in windows if w]


def _pack(paragraphs: list[str], size: int, overlap: int) -> list[str]:
    """Greedily pack paragraphs into ~size chunks with char overlap between them."""
    units: list[str] = []
    for para in paragraphs:
        units.extend([para] if len(para) <= size else _char_windows(para, size, overlap))

    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = unit if not current else f"{current}\n\n{unit}"
        if not current or len(candidate) <= size:
            current = candidate
        else:
            chunks.append(current)
            tail = _overlap_tail(current, overlap)
            current = f"{tail}\n\n{unit}" if tail else unit
    if current:
        chunks.append(current)
    return chunks



def chunk_html(
    html: bytes | str,
    *,
    source_url: str,
    title: str,
    service: str,
    document_id: str,
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[Chunk]:
    """Chunk one snapshot's HTML into metadata-stamped Chunk objects."""
    root = _content_root(html)
    blocks = _iter_blocks(root)
    raw_sections = _group_sections(blocks)
    sections = _fold_short_sections(raw_sections)

    chunks: list[Chunk] = []
    for sec in sections:
        section_value = sec["heading"] or title
        slug = _slugify(section_value)
        for n, part in enumerate(_pack(sec["paragraphs"], size, overlap)):
            chunks.append(
                Chunk(
                    content=part,
                    source_url=source_url,
                    title=title,
                    service=service,
                    section=section_value,
                    document_id=document_id,
                    chunk_id=f"{document_id}#{slug}-{n}",
                )
            )
    return chunks


def chunk_snapshot(source: dict, snapshots_dir: Path) -> list[Chunk]:
    """Convenience: chunk the snapshot for one aws_sources.yaml entry."""
    html = (snapshots_dir / f"{source['id']}.html").read_bytes()
    return chunk_html(
        html,
        source_url=source["url"],
        title=source["title"],
        service=source["service"],
        document_id=source["id"],
    )


# INGESTION_DIR = Path(__file__).resolve().parent
# SOURCES_PATH = Path(r'D:\aws-docs-agentic-rag-assistant\ingestion\snapshots')
# source = {"id": "s3-event-notifications", 
#           "service": "s3", "title": "Amazon S3 Event Notifications",
#     "url": "https://docs.aws.amazon.com/AmazonS3/latest/userguide/EventNotifications.html"}
# print(chunk_snapshot(source,SOURCES_PATH))