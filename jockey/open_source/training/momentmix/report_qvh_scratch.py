"""Harvest QVH from-scratch A/B tfevents -> per-epoch CSV + ablation figures.

Run:  /workspace/tvenv/bin/python report_qvh_scratch.py
Outputs to /workspace/runs/sgdetr/report_qvh_scratch/.
NOTE: these tfevents store scalars in the tensor proto field, not simple_value.
"""
import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from tensorboard.backend.event_processing.event_file_loader import EventFileLoader
from tensorboard.util import tensor_util

OUT = "/workspace/runs/sgdetr/report_qvh_scratch"
os.makedirs(OUT, exist_ok=True)

TAGS = {
    "train/total_loss": "train_loss",
    "val/MR-mAP-Full_Avg": "val_mAP_avg",
    "val/MR-mAP-Short_Avg": "val_mAP_short",
    "val/MR-mAP-Middle_Avg": "val_mAP_middle",
    "val/MR-mAP-Long_Avg": "val_mAP_long",
    "val/MR-R1-Full_0.5": "val_R1_05",
    "val/MR-R1-Full_0.7": "val_R1_07",
    "val/HL-HIT@1-VeryGood": "val_HIT1_VG",
}
ARMS = {"baseline": "scratch_qvh_base", "momentmix": "scratch_qvh_mmix"}
REF = {"val_mAP_avg": 53.95, "val_mAP_short": 20.27}  # released plain ckpt


def value_of(v):
    if v.HasField("tensor"):
        return float(tensor_util.make_ndarray(v.tensor))
    return float(v.simple_value)


frames = []
for arm, task in ARMS.items():
    files = sorted(glob.glob(
        f"/workspace/runs/sgdetr/logs/{task}/runs/*/tensorboard/version_0/events*"))
    rows = {}  # step -> dict
    for f in files:
        for e in EventFileLoader(f).Load():
            if not e.summary.value:
                continue
            v = e.summary.value[0]
            if v.tag in TAGS:
                rows.setdefault(e.step, {})[TAGS[v.tag]] = value_of(v)
    df = pd.DataFrame.from_dict(rows, orient="index").sort_index()
    df = df[df["val_mAP_avg"].notna()]
    df.index.name = "step"
    df = df.reset_index()
    df.insert(0, "arm", arm)
    df.insert(2, "epoch", range(1, len(df) + 1))
    frames.append(df)

data = pd.concat(frames, ignore_index=True)
data.to_csv(f"{OUT}/qvh_ab_records.csv", index=False)

base = data[data.arm == "baseline"]
mmix = data[data.arm == "momentmix"]
done = mmix.epoch.max() >= 160
suffix = "" if done else f" (MomentMix in progress: epoch {int(mmix.epoch.max())}/160)"

for xcol, fname in [("epoch", "fig_qvh_mmix_ablation.png"),
                    ("step", "fig_qvh_mmix_ablation_steps.png")]:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), dpi=130)
    for ax, ycol, title, refkey in [
        (axes[0], "val_mAP_avg", "val mAP (avg)", "val_mAP_avg"),
        (axes[1], "val_mAP_short", "val Short-mAP", "val_mAP_short"),
    ]:
        ax.plot(base[xcol], base[ycol], "r-o", ms=3, lw=1.5, label="Baseline (from scratch)")
        ax.plot(mmix[xcol], mmix[ycol], "b-o", ms=3, lw=1.5, label="+ MomentMix (ours)")
        ax.axhline(REF[refkey], color="gray", ls="--", lw=1,
                   label=f"released plain ckpt ({REF[refkey]:.1f})")
        ax.set_xlabel("Epoch" if xcol == "epoch" else "Training step")
        ax.set_ylabel(title)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    axes[0].set_title("QVHighlights from scratch: mAP (avg)")
    axes[1].set_title("Short-moment mAP")
    fig.suptitle(f"SG-DETR on QVHighlights: offline MomentMix A/B{suffix}", y=1.02)
    fig.tight_layout()
    fig.savefig(f"{OUT}/{fname}", bbox_inches="tight")
    plt.close(fig)

print(data.groupby("arm").agg(epochs=("epoch", "max"),
                              best_mAP=("val_mAP_avg", "max"),
                              best_short=("val_mAP_short", "max")))
print("saved to", OUT)
