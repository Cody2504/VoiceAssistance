"""End-to-end test of the video-service IV2GroundingService on one clip.

Exercises the wired grounding flow (encode video -> embed query -> cosine
moments/saliency) WITHOUT the full service stack (no DB/MinIO/Qdrant): it loads
the service module by file path and calls it directly.

Run on the pod:
    export IV2_SGDETR_VIDEO_CKPT=/root/iv2test/fe_weights/video_encoder.pt
    export IV2_SGDETR_TEXT_CKPT=/root/iv2test/fe_weights/text_encoder.pt
    export TEST_VIDEO=/root/iv2test/video/03.mp4
    export IV2_SERVICE_FILE=/root/iv2test/iv2_grounding_service.py   # pushed copy
    python -m jockey.open_source.training.test_ground_iv2
"""
from __future__ import annotations

import importlib.util
import os
import sys

VIDEO = os.environ.get("TEST_VIDEO", "/root/iv2test/video/03.mp4")
SERVICE_FILE = os.environ.get("IV2_SERVICE_FILE", "/root/iv2test/iv2_grounding_service.py")
QUERIES = [
    "a basketball player dunks the ball",
    "players running on the basketball court",
    "a person cooking food in a kitchen",   # off-topic control
]


def _load_service_module():
    spec = importlib.util.spec_from_file_location("iv2_grounding_service", SERVICE_FILE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["iv2_grounding_service"] = mod
    spec.loader.exec_module(mod)             # only stdlib+numpy at import time
    return mod


def main() -> int:
    for var in ("IV2_SGDETR_VIDEO_CKPT", "IV2_SGDETR_TEXT_CKPT"):
        if not os.environ.get(var):
            sys.exit(f"{var} not set")
    if not os.path.isfile(VIDEO):
        sys.exit(f"video not found: {VIDEO}")
    if not os.path.isfile(SERVICE_FILE):
        sys.exit(f"service module not found: {SERVICE_FILE} (push it to the pod)")

    G = _load_service_module()
    svc = G.IV2GroundingService(
        video_ckpt=os.environ["IV2_SGDETR_VIDEO_CKPT"],
        text_ckpt=os.environ["IV2_SGDETR_TEXT_CKPT"],
        device=os.environ.get("IV2_DEVICE", "cuda"),
    )

    print(f"video: {VIDEO}")
    feats = svc.encode_video_to_features(VIDEO)
    print(f"features: shape={feats.shape}  (clips x dim)\n")

    print("=== predict_moments (cosine grounding) ===")
    for q in QUERIES:
        moments = svc.predict_moments(q, feats, top_n=3)
        pretty = [(round(t0, 1), round(t1, 1), round(sc, 3)) for t0, t1, sc in moments]
        print(f"  {q!r}\n    -> {pretty}")

    print("\n=== predict_saliency (top-5 clips for highlight query) ===")
    sal = svc.predict_saliency(feats, "an exciting highlight moment")
    top = sorted(sal, key=lambda x: -x[2])[:5]
    for t0, t1, sc in top:
        print(f"  [{t0:5.1f}-{t1:5.1f}s]  score={sc:.3f}")

    # sanity: the basketball queries should peak higher than the cooking control
    rel = max(svc.predict_moments(QUERIES[0], feats, top_n=1)[0][2],
              svc.predict_moments(QUERIES[1], feats, top_n=1)[0][2])
    irr = svc.predict_moments(QUERIES[2], feats, top_n=1)[0][2]
    verdict = "PASS" if rel > irr else "WARN"
    print(f"\n{verdict} — basketball peak {rel:.3f} vs cooking peak {irr:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
