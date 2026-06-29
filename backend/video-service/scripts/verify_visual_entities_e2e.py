"""End-to-end check of the visual-entities image-search path: describe each query
image with the 32B VLM, retrieve over jockey_visual_entities, and report whether the
right scene/video ranks #1. Run with vast.env sourced (+ PYTHONPATH=backend)."""
import sys, base64
sys.path.insert(0, "/workspace/VoiceAssistance/backend/video-service")
sys.path.insert(0, "/workspace/VoiceAssistance/backend")
from main.api import search as S
from main.settings import get_settings
from main.search.visual_entities_query import describe_query_image
s = get_settings(); qc = S._qdrant()
vids = {p.payload["video_id"]: p.payload["original_filename"]
        for p in qc.scroll("jockey_videos", limit=500, with_payload=True)[0]}
vm = {v: {"original_filename": fn, "duration_s": 0.0} for v, fn in vids.items()}
def durl(p):
    with open(p, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
CASES = [("/tmp/query_affinity_logo.png", "hockey_bsu.mp4"),
         ("/tmp/query_pocky.png", "store_tokyo.mp4"),
         ("/tmp/query_tokyo_item1.jpg", "store_tokyo.mp4")]
for qp, target in CASES:
    q = describe_query_image(durl(qp))
    shots = S._corpus_shots_visual_entities(q, vm, 10) if q else []
    top = [vids.get(sh["video_id"], "?") for sh in shots]
    seen, grouped = set(), []
    for n in top:
        if n in seen:
            continue
        seen.add(n); grouped.append(n)
    rank = grouped.index(target) + 1 if target in grouped else -1
    desc = (q and q["description"][:55]) or None
    toks = q and q["tokens"]
    print(f"{qp.split('/')[-1]:26s} tokens={toks} top={grouped[:3]} | target {target} rank {rank}")
    print(f"    desc={desc!r}")
print("DONE")
