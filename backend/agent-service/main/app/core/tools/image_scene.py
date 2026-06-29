"""Tool: find the scene/highlight in a video that matches an attached image.

The user attaches an image to the chat turn; this tool embeds it (CLIP-L, via
the video-service `/search/image` endpoint) against the video's shots and returns
the best-matching scene(s) as truncated clips with (t_start, t_end). The image is
not a tool argument (the LLM can't produce base64) — it's read from the per-request
`current_image` context var set by the chat endpoint.
"""
from typing import Any, Literal

from langchain.tools import tool

from cm_shared.internal import current_image, post_request
from cm_shared.response import unwrap_response as _unwrap

# An arbitrary query image usually matches only the one video it actually came
# from. The backend returns a fixed top_n by cosine score, so the tail pads the
# answer with unrelated videos (whatever vectors rank next). Keep the top match
# plus any results close to it and stop at the first big score drop — this is
# self-calibrating (no absolute threshold): a lone strong match returns 1 result,
# several genuine matches all survive.
_KEEP_RATIO = 0.85


def _relevance_gate(shots: list[dict]) -> list[dict]:
    if not shots:
        return shots
    top = shots[0].get("score") or 0
    if top <= 0:
        return shots[:1]
    kept = [shots[0]]
    for sh in shots[1:]:
        if (sh.get("score") or 0) >= top * _KEEP_RATIO:
            kept.append(sh)
        else:
            break  # shots are ranked desc — the first big drop ends the relevant cluster
    return kept


# Cross-video corpus results span a wider score range than one video's moments, so
# the per-video 0.85 ratio is too strict (it would drop a genuine second video that
# scores lower). Keep everything within half the top score — the real cluster (incl.
# several videos showing the same logo/object) — and drop the unrelated low tail.
_CORPUS_KEEP_RATIO = 0.5


def _corpus_relevance_gate(shots: list[dict]) -> list[dict]:
    if not shots:
        return shots
    top = shots[0].get("score") or 0
    if top <= 0:
        return shots[:1]
    return [sh for sh in shots if (sh.get("score") or 0) >= top * _CORPUS_KEEP_RATIO]


@tool
async def find_scene_by_image(video_id: str) -> dict[str, Any]:
    """Find the scene/moment in a single video that visually matches the image the
    user attached to this message. Use when the user attaches an image and asks to
    find where in the video that scene/object/shot appears (image-to-moment).

    Returns the top matching scene as a clip (t_start, t_end) plus ranked
    alternatives. If no image is attached, returns an error the assistant should
    relay (ask the user to attach an image).
    """
    image = current_image.get()
    if not image:
        return {"error": "no_image", "message": "No image attached. Ask the user to attach an image to search by."}

    resp = _unwrap(await post_request(
        "video-service",
        f"/api/v1/videos/{video_id}/search/image",
        json={"image": image},
    ))
    shots = _relevance_gate((resp or {}).get("shots", []) if isinstance(resp, dict) else [])
    top = shots[0] if shots else None
    return {
        "video_id": video_id,
        "matched_scene": top,  # {idx, t_start, t_end, score, ...} — the highlight clip
        "ranked_scenes": shots,
        "shots": shots,  # top-level alias so the frontend clip extractor renders the moments
    }


@tool
async def search_scene_by_image(
    top_n: int = 3, group_by: Literal["clip", "video"] = "clip"
) -> dict[str, Any]:
    """Find the moments ACROSS ALL of the user's videos that visually match the image
    the user attached to this message (corpus-wide image-to-moment).

    Use when an image is attached and the user asks which video / where the scene,
    object, or person in the image appears, WITHOUT pinning one specific video —
    e.g. "find the moment the player in the image" / "which video is this from".

    `group_by="clip"` (default) returns ranked moments; `group_by="video"` returns
    the single best moment per video. Each result carries `video_id`,
    `original_filename`, `t_start`, `t_end` and `score` so the answer can cite the
    exact video and timestamp. The image is supplied automatically — do NOT pass it.
    If no image is attached, returns an error the assistant should relay.
    """
    image = current_image.get()
    if not image:
        return {"error": "no_image", "message": "No image attached. Ask the user to attach an image to search by."}

    # Returns {"query": "(image)", "group_by": ..., "shots": [...]}. The fused
    # CLIP+DINOv2+OCR ranker (+VLM verify) still pads a small/mixed corpus with an
    # unrelated low-score tail, so gate to the genuine high-score cluster before the
    # answer cites them. `shots` feeds the frontend clip extractor + reflect. (This
    # only trims the tail — it cannot fix a wrong top match, e.g. a clean logo on a
    # white background matching by background; for logos prefer an in-context crop.)
    resp = _unwrap(await post_request(
        "video-service",
        "/api/v1/videos/search/image",
        json={"image": image, "top_n": top_n, "group_by": group_by},
    ))
    if isinstance(resp, dict) and resp.get("shots"):
        resp["shots"] = _corpus_relevance_gate(resp["shots"])
    return resp
