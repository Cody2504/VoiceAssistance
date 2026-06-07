#!/usr/bin/env python3
"""Fusion gate (Option A, module #2) — fuse visual grounding s_v(t) with audio
excitement s_a(t) under a QUERY-CONDITIONED gate.

Pipeline (all on frozen models, no training for this pass):
  s_v(t) = cosine( IV2-text(query), IV2-video(clip_t) )      # visual grounding
  s_a(t) = audio-excitement curve (audio_excitement.py)       # PANN read-out
  g(query) = how audio-relevant the query is, from the SAME text tower:
             g = relu( max_c cos(q, audio_concept_c) - cos(q, neutral_anchor) )
             scaled to [0,1]  -> trusts audio for event-like queries
             ("a player dunks and the crowd roars"), ignores it for visual-only
             ("a referee stands still").
  fused(t) = (1 - w) * s_v_norm(t) + w * s_a_norm(t),  w = alpha * g

Why query-conditioned: today's Charades ablation showed audio adds ~0 on
average; the win is only on audio-salient queries/domains. The gate is what
keeps audio from hurting non-audio queries (it down-weights itself).

Usage (on the pod, weights + clip present):
  export IV2_SGDETR_VIDEO_CKPT=/root/iv2test/sgdetr_assets/fe_weights/video_encoder.pt
  export IV2_SGDETR_TEXT_CKPT=/root/iv2test/sgdetr_assets/fe_weights/text_encoder.pt
  python3 fuse_grounding_audio.py --video clips/basketball_03.mp4 \
      --query "a basketball player dunks the ball" \
      --excitement clips/basketball_03_excitement.json --device cuda
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np

# Contrastive anchor sets for the query-conditioned gate. The IV2 text space is
# low-contrast (all cosines cluster ~0.3), so the gate scores the query by the
# MARGIN between its closeness to audio-salient vs audio-neutral/visual anchors,
# then amplifies that margin through a temperature (--gate-temp).
AUDIO_CONCEPTS = [
    "the crowd cheers and applauds loudly",
    "a referee blows a whistle",
    "people shouting and screaming with excitement",
    "loud roar of an excited stadium crowd",
]
VISUAL_ANCHORS = [
    "a quiet empty court with no people",
    "a person standing still doing nothing",
    "a static view of an empty stadium",
    "a calm silent scene",
]


def l2(x: np.ndarray) -> np.ndarray:
    return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-8)


def minmax(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    return (x - x.min()) / (x.max() - x.min()) if x.size and x.max() > x.min() else x


def visual_grounding(video, query_embs, device, clip_len, frames, size):
    """Return (clip_centers_sec, s_v over clips) for each query emb row."""
    from jockey.open_source.training import iv2_feature_extractor as ife
    clips, fps = ife.read_clips(video, clip_len, frames, size)
    venc = ife.load_encoder("sgdetr", device)
    vfeat = np.stack([venc.encode_clip(clips[i]) for i in range(clips.shape[0])], axis=0)
    centers = (np.arange(clips.shape[0]) + 0.5) * clip_len
    sims = l2(query_embs) @ l2(vfeat).T          # [n_query, n_clip]
    return centers, sims, vfeat.shape


def embed_text(queries, device):
    """Embed a list of strings with the SG-DETR IV2 text tower -> [n, dim] L2 space."""
    import torch
    from transformers import BertTokenizer
    from jockey.open_source.training.test_text_tower import embed_queries
    ckpt = os.environ["IV2_SGDETR_TEXT_CKPT"]
    model = torch.jit.load(ckpt, map_location=device).to(device).eval()
    tok = BertTokenizer.from_pretrained("bert-large-uncased")
    return embed_queries(model, tok, queries, device)


# Lexical audio-salience terms (weights). The IV2 text tower's sentence
# embeddings are near-collinear (text-text cos ~0.99), so an embedding-anchor
# gate can't separate queries — a lexical gate is the robust zero-training
# stand-in. The thesis-grade upgrade is a learned MLP on the query embedding.
AUDIO_TERMS = {
    "cheer": 1.0, "crowd": 0.9, "applau": 0.9, "roar": 1.0, "whistle": 0.9,
    "dunk": 0.8, "slam": 0.7, "goal": 0.8, "score": 0.6, "celebrat": 0.8,
    "shout": 0.7, "scream": 0.7, "fans": 0.7, "buzzer": 0.8, "ovation": 0.9,
    "loud": 0.5, "excite": 0.6, "yell": 0.7, "clap": 0.7, "win": 0.4,
}


def embedding_margin(query_emb, audio_embs, visual_embs):
    """Diagnostic: closeness of query to audio vs visual anchors (low-contrast here)."""
    q = l2(query_emb.reshape(1, -1))[0]
    ca = float(np.mean(l2(audio_embs) @ q))
    cv = float(np.mean(l2(visual_embs) @ q))
    return ca - cv, ca, cv


def lexical_gate(query: str) -> float:
    """Audio-relevance of the query in [0,1] from audio-salient terms."""
    low = query.lower()
    score = 0.0
    for term, wt in AUDIO_TERMS.items():
        if term in low:
            score = max(score, wt)          # strongest matched term sets the floor
            score = min(1.0, score + 0.1 * wt)  # small boost for multiple matches
    return float(np.clip(score, 0.0, 1.0))


def resample(src_t, src_v, dst_t):
    """Linear-interpolate (src_t, src_v) onto dst_t."""
    if len(src_t) < 2:
        return np.full_like(dst_t, src_v[0] if len(src_v) else 0.0, dtype=np.float32)
    return np.interp(dst_t, src_t, src_v).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--query", required=True)
    ap.add_argument("--excitement", required=True, help="*_excitement.json from audio_excitement.py")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--alpha", type=float, default=1.0, help="max audio weight at g=1")
    ap.add_argument("--gate-temp", type=float, default=60.0, help="gate margin amplification")
    ap.add_argument("--clip-len", type=float, default=2.0)
    ap.add_argument("--frames", type=int, default=4)
    ap.add_argument("--size", type=int, default=224)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    stem = os.path.splitext(os.path.basename(args.video))[0]
    slug = "".join(c if c.isalnum() else "_" for c in args.query.lower())[:40].strip("_")
    out_dir = args.out or os.path.dirname(os.path.abspath(args.video))

    # 1) text embeddings: query + audio anchors + visual anchors (one tower load)
    print("[1/4] embedding query + contrastive anchors ...")
    n_a = len(AUDIO_CONCEPTS)
    all_text = [args.query] + AUDIO_CONCEPTS + VISUAL_ANCHORS
    embs = embed_text(all_text, args.device)
    q_emb = embs[0]
    audio_embs = embs[1:1 + n_a]
    visual_embs = embs[1 + n_a:]
    g = lexical_gate(args.query)
    margin, ca, cv = embedding_margin(q_emb, audio_embs, visual_embs)
    w = float(np.clip(args.alpha * g, 0.0, 1.0))
    print(f"      lexical gate g={g:.3f} -> audio weight w={w:.3f}   "
          f"[embed-margin diag={margin:+.3f} (audio {ca:.3f} vs visual {cv:.3f}) — "
          f"too collinear to gate on]")

    # 2) visual grounding s_v(t)
    print("[2/4] visual grounding (IV2 cosine) ...")
    centers, sims, vshape = visual_grounding(
        args.video, q_emb.reshape(1, -1), args.device, args.clip_len, args.frames, args.size)
    sv_t, sv = centers, sims[0]
    print(f"      video feats {vshape}, {len(sv_t)} clips")

    # 3) audio excitement s_a(t)
    print("[3/4] loading audio excitement ...")
    js = json.load(open(args.excitement))
    sa_t = np.asarray(js["times"]); sa = np.asarray(js["excitement"])

    # 4) fuse on a common time grid (the finer audio grid)
    grid = sa_t
    sv_g = minmax(resample(sv_t, sv, grid))
    sa_g = minmax(sa)
    fused = (1 - w) * sv_g + w * sa_g
    fused_n = minmax(fused)

    # peaks of fused (reuse audio z-spike detector)
    from jockey.open_source.training.audio_excitement import find_peaks
    peaks = find_peaks(grid, fused_n, thresh=1.5)
    print("[4/4] fused peaks (candidate highlights for this query):")
    for t, v in peaks:
        print(f"        t={t:6.1f}s  fused={v:.2f}")

    # save + plot
    res = {"video": args.video, "query": args.query, "gate_g": g, "margin": margin,
           "audio_weight_w": w, "times": grid.tolist(), "s_v": sv_g.tolist(),
           "s_a": sa_g.tolist(), "fused": fused_n.tolist(),
           "peaks": [{"t": t, "e": v} for t, v in peaks]}
    js_path = os.path.join(out_dir, f"{stem}__{slug}_fused.json")
    json.dump(res, open(js_path, "w"), indent=2)

    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(grid, sv_g, color="#1f77b4", lw=1.6, alpha=0.8, label="s_v(t) visual grounding")
    ax.plot(grid, sa_g, color="#d62728", lw=1.4, alpha=0.6, label="s_a(t) audio excitement")
    ax.plot(grid, fused_n, color="#2ca02c", lw=2.4, label=f"fused (w={w:.2f})")
    for t, v in peaks:
        ax.axvline(t, color="#2ca02c", ls="--", alpha=0.5)
    ax.set_xlabel("time (s)"); ax.set_ylabel("score (norm)")
    ax.set_title(f"Fusion gate — {os.path.basename(args.video)}\n"
                 f"query={args.query!r}  gate g={g:.2f} w={w:.2f}")
    ax.legend(loc="upper right"); ax.grid(alpha=0.3)
    fig.tight_layout()
    png = os.path.join(out_dir, f"{stem}__{slug}_fused.png")
    fig.savefig(png, dpi=110)
    print(f"\nwrote:\n  {js_path}\n  {png}")


if __name__ == "__main__":
    main()
