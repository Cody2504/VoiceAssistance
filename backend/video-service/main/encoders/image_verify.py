"""Vision-LLM verification of image-search candidates.

CLIP-L image search ranks moments by cosine similarity. On a small or mixed
corpus the tail packs visually-unrelated videos whose vectors merely rank next
(a tennis query frame returning abstract linear-algebra lectures). A score-ratio
gate can't separate them — the cosine scores genuinely sit close together.

So we add one Qwen3-VL pass that *looks* at the query frame alongside each
candidate's cached shot thumbnail and keeps only the candidates that actually
depict the same scene/subject. The provider accepts multiple images in a single
chat completion, so this is ONE round-trip regardless of candidate count
(query image + N thumbnails in one message).

Reuses the same OpenRouter Qwen3-VL endpoint as ``VLMCaptioner`` / ``VideoQA``
(``VLM_MODEL`` / ``OPENROUTER_API_KEY``). Safe-by-default: if the VLM is
unavailable or the call errors, ``verify`` returns "keep all" so image search
never regresses to empty on an infra hiccup — only a *successful* judgement of
"no match" prunes.

Public API:
    v = ImageMatchVerifier.from_config(config)
    mask = v.verify(query_image_data_url, [jpeg_bytes, ...])  # -> list[bool]
"""
import base64
import logging
import os
import re
from typing import List, Optional

log = logging.getLogger(__name__)

_UNAVAILABLE = "unavailable"

_INSTRUCTION = (
    "You compare video frames. The FIRST image below is a QUERY frame. "
    "The remaining {n} images are CANDIDATE frames, numbered 1 to {n} in order, "
    "each taken from a different video. Decide which candidates depict the SAME "
    "scene or subject as the QUERY — they could plausibly come from the same "
    "video (same activity, setting, and visual content). Reject any candidate on "
    "an unrelated topic (e.g. a math lecture vs a tennis match). Reply with ONE "
    "line in exactly this format: 'MATCHES: <comma-separated candidate numbers>' "
    "or 'MATCHES: none'. List the matches in order of confidence, BEST FIRST "
    "(most likely the exact same source video — same title text, logo, or scene)."
)


def parse_match_response(text: str, n: int) -> List[int]:
    """Parse a VLM reply into the sorted 1-based candidate numbers it matched.

    We only trust the strict ``MATCHES: ...`` marker the prompt asks for — its
    single line is parsed for integers in ``[1, n]``. A reply without the marker
    (the model went off-format) returns ``[]`` rather than scraping stray digits
    from prose like "images 1 and 3 are unrelated", which would invert the
    meaning. ``MATCHES: none`` → ``[]``.
    """
    m = re.search(r"matches\s*:\s*(.*)", text or "", re.IGNORECASE | re.DOTALL)
    if not m:
        return []
    line = m.group(1).splitlines()[0]
    return sorted({int(x) for x in re.findall(r"\d+", line) if 1 <= int(x) <= n})


def parse_ranked_response(text: str, n: int) -> List[int]:
    """Like ``parse_match_response`` but PRESERVES the model's order (best-first)
    instead of sorting — used for re-ranking. Dedupes keeping first occurrence;
    no strict marker / "none" → ``[]``."""
    m = re.search(r"matches\s*:\s*(.*)", text or "", re.IGNORECASE | re.DOTALL)
    if not m:
        return []
    line = m.group(1).splitlines()[0]
    out: List[int] = []
    for tok in re.findall(r"\d+", line):
        v = int(tok)
        if 1 <= v <= n and v not in out:
            out.append(v)
    return out


def _resolve_enabled(raw: str, has_api_key: bool) -> bool:
    raw = (raw or "").strip().lower()
    if raw == "auto":
        return has_api_key
    return raw in ("true", "1", "yes")


def _as_data_url(image: str) -> str:
    """Pass through a data URL; wrap bare base64 as a jpeg data URL."""
    return image if image.startswith("data:") else f"data:image/jpeg;base64,{image}"


class ImageMatchVerifier:
    """Verify image-search candidates against the query image via Qwen3-VL."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
        max_new_tokens: int = 32,
        enabled: Optional[bool] = None,
    ):
        self.api_key = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY", "")
        self.model = model or os.environ.get("VLM_MODEL", "qwen/qwen3-vl-8b-instruct")
        self.base_url = base_url
        self.max_new_tokens = max_new_tokens
        if enabled is None:
            enabled = _resolve_enabled(os.environ.get("IMAGE_VERIFY_ENABLED", "auto"), bool(self.api_key))
        self.enabled = enabled
        self._client = None

    @classmethod
    def from_config(cls, config) -> "ImageMatchVerifier":
        return cls(
            api_key=config.openrouter_api_key,
            model=config.vlm_model,
            base_url=config.openrouter_base_url,
            enabled=_resolve_enabled(
                os.environ.get("IMAGE_VERIFY_ENABLED", "auto"),
                bool(config.openrouter_api_key),
            ),
        )

    def _lazy_load(self) -> None:
        if self._client is not None:
            return
        if not self.enabled or not self.api_key:
            self._client = _UNAVAILABLE
            return
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        except ImportError:
            log.warning("openai package not installed; image verification disabled")
            self._client = _UNAVAILABLE

    def is_available(self) -> bool:
        self._lazy_load()
        return self._client not in (None, _UNAVAILABLE)

    def verify(self, query_image: str, candidate_jpegs: List[bytes]) -> List[bool]:
        """Return a keep-mask aligned with ``candidate_jpegs``.

        - VLM unavailable or call errors → keep all (non-regressing).
        - A successful judgement keeps only the matched candidates; "none" →
          all ``False`` (the caller decides whether to fall back to top-1).
        """
        n = len(candidate_jpegs)
        if n == 0:
            return []
        if not self.is_available():
            return [True] * n
        try:
            text = self._call(query_image, candidate_jpegs)
        except Exception as e:  # noqa: BLE001 — never let verification break search
            log.warning("image verification call failed (%s); keeping all candidates", e)
            return [True] * n
        matched = set(parse_match_response(text, n))
        log.info("image verify: %d/%d candidates kept (%s)", len(matched), n, sorted(matched))
        return [(i + 1) in matched for i in range(n)]

    def rank(self, query_image: str, candidate_jpegs: List[bytes]) -> List[int]:
        """Ordered 1-based survivors, best-first. Unavailable/error → keep all in
        original order (no-op). A successful 'none' → ``[]`` (caller falls back)."""
        n = len(candidate_jpegs)
        if n == 0:
            return []
        if not self.is_available():
            return list(range(1, n + 1))
        try:
            text = self._call(query_image, candidate_jpegs)
        except Exception as e:  # noqa: BLE001 — never let verification break search
            log.warning("image rank call failed (%s); keeping all", e)
            return list(range(1, n + 1))
        ranked = parse_ranked_response(text, n)
        log.info("image rank: %d/%d kept (%s)", len(ranked), n, ranked)
        return ranked

    def _call(self, query_image: str, candidate_jpegs: List[bytes]) -> str:
        n = len(candidate_jpegs)
        content: list = [{"type": "text", "text": _INSTRUCTION.format(n=n)}]
        content.append({"type": "image_url", "image_url": {"url": _as_data_url(query_image)}})
        for j in candidate_jpegs:
            b64 = base64.b64encode(j).decode()
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            max_tokens=self.max_new_tokens,
            temperature=0,
        )
        return resp.choices[0].message.content or ""


_singleton: Optional[ImageMatchVerifier] = None


def get_verifier() -> ImageMatchVerifier:
    global _singleton
    if _singleton is None:
        try:
            from main.encoders.config import config
            _singleton = ImageMatchVerifier.from_config(config)
        except Exception:
            _singleton = ImageMatchVerifier()
    return _singleton


def verify_image_matches(query_image: str, candidate_jpegs: List[bytes]) -> List[bool]:
    """Module-level convenience over the process singleton."""
    try:
        return get_verifier().verify(query_image, candidate_jpegs)
    except Exception as exc:  # noqa: BLE001
        log.warning("verify_image_matches failed (%s); keeping all", exc)
        return [True] * len(candidate_jpegs)


def verify_image_matches_ranked(query_image: str, candidate_jpegs: List[bytes]) -> List[int]:
    """Module-level convenience: ordered 1-based survivors (best-first). On any
    error keep all in original order so search never regresses to empty."""
    try:
        return get_verifier().rank(query_image, candidate_jpegs)
    except Exception as exc:  # noqa: BLE001
        log.warning("verify_image_matches_ranked failed (%s); keeping all", exc)
        return list(range(1, len(candidate_jpegs) + 1))
