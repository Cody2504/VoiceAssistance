"""Query-side of visual-entities image search: describe the query image with the
same 32B VLM (symmetric prompt), and parse its output into a description + strong
brand/wordmark tokens. Pure `parse_entity_output` is unit-tested; the VLM call is
safe-by-default (None on error so the caller falls back to existing streams)."""
import logging
import re
from typing import Optional

log = logging.getLogger(__name__)

QUERY_ENTITY_PROMPT = (
    "This is a query image for an image search. Identify and describe WHAT it shows: "
    "(1) any brand, product, or logo you recognize, by name; (2) any visible text or "
    "packaging words, verbatim; (3) the object type and a short description. If you "
    "cannot name it, describe it (shape, colour, type). Be concise (<= 40 words). End "
    "with a line 'NAMES: <comma-separated brand/product/wordmark names, or none>'."
)


def parse_entity_output(text: str) -> dict:
    """Split a VLM entity description into {description, tokens}. `tokens` come from a
    trailing 'NAMES: a, b' line (case-insensitive); 'none'/empty -> []. The NAMES line
    is stripped from `description`. No NAMES line -> tokens=[], description=text."""
    text = (text or "").strip()
    m = re.search(r"(?im)^\s*names\s*:\s*(.*)$", text)
    tokens: list[str] = []
    if m:
        raw = m.group(1).strip()
        if raw.lower() not in ("", "none"):
            tokens = [t.strip() for t in raw.split(",") if t.strip() and t.strip().lower() != "none"]
        text = (text[: m.start()] + text[m.end():]).strip()
    return {"description": text, "tokens": tokens}


def describe_query_image(data_url: str) -> Optional[dict]:
    """Run the 32B VLM on the query image -> {description, tokens}. None on any error
    (caller falls back to the existing CLIP/DINO/OCR streams)."""
    try:
        from main.encoders.visual_entities import get_visual_entity_captioner
        cap = get_visual_entity_captioner()
        if not cap.is_available():
            return None
        content = [{"type": "text", "text": QUERY_ENTITY_PROMPT},
                   {"type": "image_url", "image_url": {"url": _as_data_url(data_url)}}]
        resp = cap._client.chat.completions.create(
            model=cap.model, messages=[{"role": "user", "content": content}],
            max_tokens=120, temperature=0)
        return parse_entity_output(resp.choices[0].message.content or "")
    except Exception as e:  # noqa: BLE001
        log.warning("describe_query_image failed (%s)", e)
        return None


def _as_data_url(image: str) -> str:
    return image if image.startswith("data:") else f"data:image/jpeg;base64,{image}"
