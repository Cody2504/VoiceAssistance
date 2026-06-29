"""Final QVH from-scratch A/B results table (CSV + PNG).

Run:  /workspace/tvenv/bin/python final_table_qvh.py
Reads the three eval metrics.json files; writes to report_qvh_scratch/.
"""
import glob
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

OUT = "/workspace/runs/sgdetr/report_qvh_scratch"
EVALS = {
    "Released plain ckpt (reference)": "eval_qvh_plain_released",
    "Arm A: from scratch (baseline)": "eval_scratch_qvh_base",
    "Arm B: from scratch + MomentMix": "eval_scratch_qvh_mmix",
}
COLS = {
    "test/MR-mAP-Full_Avg": "mAP avg",
    "test/MR-mAP-Short_Avg": "mAP Short",
    "test/MR-mAP-Middle_Avg": "mAP Middle",
    "test/MR-mAP-Long_Avg": "mAP Long",
    "test/MR-R1-Full_0.5": "R1@0.5",
    "test/MR-R1-Full_0.7": "R1@0.7",
    "test/HL-HIT@1-VeryGood": "HIT@1 (VG)",
}

rows = {}
for label, task in EVALS.items():
    f = sorted(glob.glob(f"/workspace/runs/sgdetr/logs/{task}/runs/*/lightning_logs/*/metrics.json"))[-1]
    m = json.load(open(f))
    rows[label] = {col: round(m[tag], 2) for tag, col in COLS.items()}

df = pd.DataFrame.from_dict(rows, orient="index")[list(COLS.values())]
delta = df.loc["Arm B: from scratch + MomentMix"] - df.loc["Arm A: from scratch (baseline)"]
df.loc["Δ (B − A)"] = delta.round(2)
df.index.name = "Model (QVH val, 1549 queries)"
df.to_csv(f"{OUT}/qvh_final_results_table.csv")
print(df.to_string())

fig, ax = plt.subplots(figsize=(11, 2.2), dpi=150)
ax.axis("off")
tbl = ax.table(cellText=df.reset_index().values,
               colLabels=[df.index.name] + list(df.columns),
               loc="center", cellLoc="center")
tbl.auto_set_font_size(False)
tbl.set_fontsize(8.5)
tbl.scale(1, 1.5)
tbl.auto_set_column_width(col=list(range(len(df.columns) + 1)))
for j in range(len(df.columns) + 1):
    tbl[0, j].set_text_props(weight="bold")
    tbl[len(df), j].set_text_props(weight="bold")  # delta row
fig.suptitle("SG-DETR on QVHighlights from scratch: offline MomentMix A/B (identical recipe, seed 40)", fontsize=10)
fig.savefig(f"{OUT}/qvh_final_results_table.png", bbox_inches="tight")
print("saved table to", OUT)
