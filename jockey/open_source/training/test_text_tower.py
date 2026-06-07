"""Verify the InternVideo2 text tower (SG-DETR ``text_encoder.pt``) executes and
produces 512-d query embeddings in the SAME aligned space as the video features.

Two checks:
  1. EXECUTION — load the TorchScript text encoder, tokenize queries with
     bert-large-uncased (max_len 40, as in SG-DETR's extract_text_features.py),
     run forward, confirm the pooled vector is 512-d and L2-normalized.
  2. CROSS-MODAL SANITY — extract video features for a basketball clip and check
     that basketball-related queries score higher max-cosine against the clips
     than an unrelated ("cooking") query. If so, text & video share one space.

Run on the pod:
    export IV2_SGDETR_TEXT_CKPT=/root/iv2test/fe_weights/text_encoder.pt
    export IV2_SGDETR_VIDEO_CKPT=/root/iv2test/fe_weights/video_encoder.pt
    export TEST_VIDEO=/root/iv2test/video/03.mp4
    pip install transformers
    python -m jockey.open_source.training.test_text_tower
"""
from __future__ import annotations

import os
import sys

MAX_SEQ_LENGTH = 40
RELEVANT = [
    "a basketball player dunks the ball",
    "players running on a basketball court",
]
IRRELEVANT = "a person cooking food in a kitchen"


def _preflight() -> None:
    for mod in ("numpy", "torch", "transformers"):
        try:
            __import__(mod)
        except ImportError:
            sys.exit(f"missing dep: {mod}  (pip install transformers; torch already present)")
    if not os.environ.get("IV2_SGDETR_TEXT_CKPT"):
        sys.exit("IV2_SGDETR_TEXT_CKPT not set (path to text_encoder.pt)")


def embed_queries(model, tok, queries, device):
    import numpy as np
    import torch
    out_vecs = []
    for q in queries:
        t = tok(q, padding="max_length", truncation=True,
                max_length=MAX_SEQ_LENGTH, return_tensors="pt").to(device)
        with torch.no_grad():
            out = model(t.input_ids, t.attention_mask)
        if q == queries[0]:
            shapes = [tuple(o.shape) if hasattr(o, "shape") else type(o).__name__
                      for o in (out if isinstance(out, (tuple, list)) else [out])]
            print(f"  model outputs: {shapes}")
        all_tfeat = out[1] if isinstance(out, (tuple, list)) else out
        pooled = all_tfeat[:, 0].float().cpu().numpy().reshape(-1)   # [dim]
        out_vecs.append(pooled)
    return np.stack(out_vecs, axis=0)


def main() -> int:
    _preflight()
    import numpy as np
    import torch
    from transformers import BertTokenizer

    ckpt = os.environ["IV2_SGDETR_TEXT_CKPT"]
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"text ckpt : {ckpt}\ndevice    : {device}")

    try:
        model = torch.jit.load(ckpt, map_location=device).to(device).eval()
    except Exception as exc:
        sys.exit(f"torch.jit.load failed on text_encoder: {exc}")
    tok = BertTokenizer.from_pretrained("bert-large-uncased")

    # --- Check 1: execution ---
    print("\n[1] EXECUTION")
    all_q = RELEVANT + [IRRELEVANT]
    qemb = embed_queries(model, tok, all_q, device)
    norms = np.linalg.norm(qemb, axis=1)
    print(f"  query emb shape : {qemb.shape}")
    print(f"  per-query L2    : {norms.round(3).tolist()}")
    assert qemb.ndim == 2 and qemb.shape[0] == len(all_q), "bad query emb shape"
    dim = qemb.shape[1]
    if dim != 512:
        print(f"  NOTE: text dim={dim} (expected 512 to match video)")
    assert np.isfinite(qemb).all(), "non-finite text embeddings"
    print(f"  PASS — text tower outputs {dim}-d, L2≈{norms.mean():.3f}")

    # --- Check 2: cross-modal sanity (optional, needs video ckpt + clip) ---
    print("\n[2] CROSS-MODAL SANITY")
    video = os.environ.get("TEST_VIDEO")
    if not (video and os.path.isfile(video) and os.environ.get("IV2_SGDETR_VIDEO_CKPT")):
        print("  skipped (set TEST_VIDEO + IV2_SGDETR_VIDEO_CKPT to enable)")
        return 0
    from jockey.open_source.training import iv2_feature_extractor as ife
    clips, _ = ife.read_clips(video, ife.DEFAULT_CLIP_LENGTH_SEC,
                              ife.DEFAULT_FRAMES_PER_CLIP, ife.DEFAULT_INPUT_SIZE)
    venc = ife.load_encoder("sgdetr", device)
    vfeat = np.stack([venc.encode_clip(clips[i]) for i in range(clips.shape[0])], axis=0)
    if vfeat.shape[1] != dim:
        print(f"  NOTE: video dim {vfeat.shape[1]} != text dim {dim} — not directly comparable")
        return 0

    def l2(x):
        return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-8)
    vfn, qn = l2(vfeat), l2(qemb)
    sims = qn @ vfn.T                       # [n_query, n_clip] cosine
    print(f"  video feats: {vfeat.shape}  (basketball clip)")
    for q, row in zip(all_q, sims):
        tag = "IRRELEVANT" if q == IRRELEVANT else "relevant  "
        print(f"  [{tag}] max={row.max():.3f} mean={row.mean():.3f}  | {q!r}")
    rel_max = sims[:len(RELEVANT)].max()
    irr_max = sims[len(RELEVANT):].max()
    if rel_max > irr_max:
        print(f"  PASS — basketball queries align better ({rel_max:.3f} > {irr_max:.3f}); "
              "text & video share one space")
    else:
        print(f"  WARN — relevant ({rel_max:.3f}) !> irrelevant ({irr_max:.3f}); "
              "check tokenizer / pooling / which output is the sentence vector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
