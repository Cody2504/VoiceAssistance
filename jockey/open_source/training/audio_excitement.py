#!/usr/bin/env python3
"""Audio-excitement head (Option A, module #1) — sports-highlight cue from audio.

Reads a video's audio, runs PANN CNN14 (AudioSet 527 classes) over sliding
windows, and reduces the per-window class probabilities to a single
**excitement curve** e(t) by a weighted read-out of the sports-relevant
AudioSet classes (cheering / crowd / applause / whistle / shouting).

No training required for the qualitative pass: PANN is pretrained on AudioSet,
which already contains these classes. (A learned MLP on the same per-window
527-vector is the optional "fine-tune" — the read-out weights below are its
zero-training stand-in.)

Outputs, next to the video (or to --out):
  <stem>_excitement.json   curve + peaks + metadata
  <stem>_excitement.png    plot: total e(t) with peaks + per-class panels

Usage:
  python3 audio_excitement.py video/basketball/03.mp4
  python3 audio_excitement.py clip.mp4 --win 1.5 --hop 0.5 --topk 5 --device cuda
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import wave
from typing import Optional

import numpy as np

SR = 32000  # PANN CNN14 expects 32 kHz mono

# AudioSet display-names (substring, case-insensitive) -> excitement weight.
# Referee whistle and crowd cheer are the sharpest sports-highlight markers.
EXCITEMENT_WEIGHTS = {
    "cheering": 1.0,
    "applause": 0.9,
    "crowd": 0.8,
    "whistle": 0.7,      # also matches "Whistling"
    "shout": 0.6,        # "Shout", "Children shouting"
    "yell": 0.6,
    "screaming": 0.6,
    "chatter": 0.3,      # "Chatter", "Hubbub, speech noise, speech babble"
    "speech": 0.15,      # commentator ambient — low weight, noisy alone
}


def load_audio_32k_mono(video_path: str) -> np.ndarray:
    """ffmpeg -> 32kHz mono float32 in [-1, 1]."""
    fd, wav = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-ar", str(SR), "-ac", "1",
             "-f", "wav", "-loglevel", "quiet", wav],
            check=True, capture_output=True,
        )
        with wave.open(wav, "rb") as wf:
            raw = wf.readframes(wf.getnframes())
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    finally:
        try:
            os.remove(wav)
        except OSError:
            pass


def build_weight_vector(labels: list[str]) -> tuple[np.ndarray, dict]:
    """Map the 527 AudioSet labels -> per-class excitement weight (substring match)."""
    w = np.zeros(len(labels), dtype=np.float32)
    matched: dict[str, list[str]] = {}
    for i, lab in enumerate(labels):
        low = lab.lower()
        for key, weight in EXCITEMENT_WEIGHTS.items():
            if key in low:
                w[i] = max(w[i], weight)
                matched.setdefault(key, []).append(lab)
    return w, matched


def excitement_curve(samples: np.ndarray, tagger, labels: list[str],
                     win: float, hop: float):
    """Slide PANN over the clip -> (times, total_excitement, per_class_probs, weight_vec)."""
    weight_vec, matched = build_weight_vector(labels)
    win_n, hop_n = int(win * SR), int(hop * SR)
    n = samples.shape[0]
    times, total = [], []
    # track a few headline classes individually for the plot
    headline = ["cheering", "applause", "crowd", "whistle"]
    head_idx = {k: np.array([i for i, l in enumerate(labels) if k in l.lower()])
                for k in headline}
    per_class = {k: [] for k in headline}

    start = 0
    while start < n:
        seg = samples[start:start + win_n]
        if seg.size < int(0.3 * SR):  # skip <0.3s tail
            break
        x = seg.reshape(1, -1).astype(np.float32)
        clipwise, _ = tagger.inference(x)         # (1, 527)
        scores = np.asarray(clipwise[0])
        times.append((start + win_n / 2) / SR)    # window center
        total.append(float((scores * weight_vec).sum()))
        for k, idx in head_idx.items():
            per_class[k].append(float(scores[idx].max()) if idx.size else 0.0)
        start += hop_n

    times = np.asarray(times)
    total = np.asarray(total)
    # normalize total to [0,1] for readability
    if total.size and total.max() > total.min():
        norm = (total - total.min()) / (total.max() - total.min())
    else:
        norm = total
    return times, norm, total, {k: np.asarray(v) for k, v in per_class.items()}, matched


def _rolling_median(x: np.ndarray, win_pts: int) -> np.ndarray:
    """Local baseline via centered rolling median (edge-padded)."""
    if win_pts < 3 or x.size < win_pts:
        return np.full_like(x, np.median(x) if x.size else 0.0)
    half = win_pts // 2
    pad = np.pad(x, half, mode="edge")
    return np.array([np.median(pad[i:i + win_pts]) for i in range(x.size)])


def find_peaks(times: np.ndarray, curve: np.ndarray, thresh: float = 1.5,
               min_gap: float = 2.0, baseline: bool = True,
               baseline_win_sec: float = 6.0):
    """Peaks of the excitement curve.

    baseline=True (default): score each window by a robust z-spike
        z(t) = (e(t) - rolling_median(e)) / (1.4826 * rolling_MAD(e))
    and keep local maxima with z >= `thresh` (default 1.5 sigma). Scale-
    invariant — robust to both continuous crowd ambiance (tennis) and
    intermittent crowds (basketball) without per-clip tuning.
    baseline=False: absolute threshold on the normalized curve (legacy;
        in that mode pass thresh~0.5).
    """
    if not curve.size:
        return []
    if baseline:
        hop = (times[1] - times[0]) if times.size > 1 else 0.5
        win_pts = max(5, int(round(baseline_win_sec / max(hop, 1e-6))))
        floor = _rolling_median(curve, win_pts)
        mad = _rolling_median(np.abs(curve - floor), win_pts)
        scale = 1.4826 * mad
        scale = np.where(scale < 1e-6, np.median(scale[scale > 0]) if np.any(scale > 0) else 1.0, scale)
        sig = (curve - floor) / scale
    else:
        sig = curve
    peaks = []
    for i in range(len(sig)):
        lo, hi = max(0, i - 1), min(len(sig), i + 2)
        if sig[i] >= thresh and sig[i] == sig[lo:hi].max():
            if not peaks or (times[i] - peaks[-1][0]) >= min_gap:
                peaks.append((float(times[i]), float(curve[i])))
            elif curve[i] > peaks[-1][1]:
                peaks[-1] = (float(times[i]), float(curve[i]))
    return peaks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--win", type=float, default=1.5, help="window seconds")
    ap.add_argument("--hop", type=float, default=0.5, help="hop seconds")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--thresh", type=float, default=1.5,
                    help="z-spike sigma for peak detection (baseline mode)")
    ap.add_argument("--out", default=None, help="output dir (default: alongside video)")
    args = ap.parse_args()

    from panns_inference import AudioTagging, labels  # type: ignore

    stem = os.path.splitext(os.path.basename(args.video))[0]
    out_dir = args.out or os.path.dirname(os.path.abspath(args.video))
    os.makedirs(out_dir, exist_ok=True)

    print(f"[1/4] decoding audio: {args.video}")
    samples = load_audio_32k_mono(args.video)
    dur = samples.shape[0] / SR
    print(f"      {dur:.1f}s @ {SR}Hz")

    print(f"[2/4] loading PANN CNN14 (device={args.device}) ...")
    tagger = AudioTagging(checkpoint_path=None, device=args.device)
    lab = list(labels)

    print(f"[3/4] sliding window win={args.win}s hop={args.hop}s ...")
    times, norm, raw, per_class, matched = excitement_curve(
        samples, tagger, lab, args.win, args.hop)
    peaks = find_peaks(times, norm, thresh=args.thresh)
    print(f"      matched AudioSet classes: "
          f"{ {k: len(v) for k, v in matched.items()} }")
    print(f"      {len(peaks)} excitement peaks (thresh={args.thresh}):")
    for t, v in peaks:
        print(f"        t={t:6.1f}s  e={v:.2f}")

    # save json
    js = {
        "video": args.video, "duration_sec": dur,
        "win": args.win, "hop": args.hop, "thresh": args.thresh,
        "times": times.tolist(), "excitement": norm.tolist(),
        "excitement_raw": raw.tolist(),
        "per_class": {k: v.tolist() for k, v in per_class.items()},
        "peaks": [{"t": t, "e": v} for t, v in peaks],
        "matched_classes": matched,
    }
    js_path = os.path.join(out_dir, f"{stem}_excitement.json")
    with open(js_path, "w") as f:
        json.dump(js, f, indent=2)

    # plot
    print("[4/4] plotting ...")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (ax0, ax1) = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
    ax0.plot(times, norm, color="#d62728", lw=2, label="excitement e(t)")
    ax0.fill_between(times, norm, color="#d62728", alpha=0.15)
    for t, v in peaks:
        ax0.axvline(t, color="#1f77b4", ls="--", alpha=0.6)
        ax0.annotate(f"{t:.0f}s", (t, v), fontsize=8, color="#1f77b4")
    ax0.set_ylabel("excitement (norm)")
    ax0.set_title(f"Audio-excitement head — {os.path.basename(args.video)} "
                  f"({dur:.0f}s, {len(peaks)} peaks)")
    ax0.legend(loc="upper right"); ax0.grid(alpha=0.3)
    for k, col in zip(["cheering", "applause", "crowd", "whistle"],
                      ["#ff7f0e", "#2ca02c", "#9467bd", "#8c564b"]):
        if per_class[k].size:
            ax1.plot(times, per_class[k], label=k, color=col, alpha=0.8)
    ax1.set_xlabel("time (s)"); ax1.set_ylabel("class prob")
    ax1.legend(loc="upper right", ncol=4, fontsize=8); ax1.grid(alpha=0.3)
    fig.tight_layout()
    png_path = os.path.join(out_dir, f"{stem}_excitement.png")
    fig.savefig(png_path, dpi=110)
    print(f"\nwrote:\n  {js_path}\n  {png_path}")


if __name__ == "__main__":
    main()
