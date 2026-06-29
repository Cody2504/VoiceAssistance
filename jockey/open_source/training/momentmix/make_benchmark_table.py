"""Paper-style QVHighlights benchmark table (SG-DETR Table 3 layout) + our rows.

Published rows = QVH *test* numbers transcribed from SG-DETR paper Table 3
(arXiv:2410.01615). Our rows = QVH *val* (test labels are hidden; no server
submission) from the local eval JSONs. The split difference is footnoted; the
released w/PT ckpt anchors the gap (val 58.93 vs test 58.8).

Run: /tmp/mmixvenv/bin/python make_benchmark_table.py
Outputs: docs/thesis/sgdetr-qvh-scratch/qvh_benchmark_table.{png,csv,tex}
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = "/mnt/d/MR-DETR/VoiceAssistance/docs/thesis/sgdetr-qvh-scratch"
COLS = ["R1@0.5", "R1@0.7", "mAP@0.5", "mAP@0.75", "mAP Avg", "HD mAP", "HIT@1"]
KEYS = ["test/MR-R1-Full_0.5", "test/MR-R1-Full_0.7", "test/MR-mAP-Full_0.5",
        "test/MR-mAP-Full_0.75", "test/MR-mAP-Full_Avg",
        "test/HL-mAP-VeryGood", "test/HL-HIT@1-VeryGood"]

# QVHighlights TEST, SG-DETR paper Table 3 (HD columns are >= Very Good)
PUBLISHED = [
    ("MDETR",          [52.9, 33.0, 54.8, 29.4, 30.7, 35.7, 55.6]),
    ("UMT †",     [56.2, 41.2, 53.4, 37.0, 36.1, 38.2, 60.0]),
    ("UniVTG",         [58.9, 40.9, 57.6, 35.6, 35.5, 38.2, 61.0]),
    ("QD-DETR",        [62.4, 45.0, 62.6, 39.9, 39.9, 38.6, 62.4]),
    ("CG-DETR",        [65.4, 48.4, 64.5, 42.8, 42.9, 40.3, 66.2]),
    ("BAM-DETR",       [62.7, 48.6, 64.6, 46.3, 45.4, None, None]),
    ("TR-DETR",        [64.7, 49.0, 64.0, 43.7, 42.6, 39.9, 63.4]),
    ("Mr. BLIP",       [74.7, 60.5, 68.1, 53.4, 51.4, None, None]),
    ("SG-DETR",        [72.2, 56.6, 73.2, 55.8, 54.1, 43.8, 69.1]),
    ("SG-DETR w/ PT",  [74.2, 60.4, 76.2, 60.8, 58.8, 44.7, 71.0]),
]

OURS_FILES = [
    ("SG-DETR (released ckpt, our eval)", "released_plain_metrics.json"),
    ("SG-DETR from scratch (repro)",      "armA_metrics.json"),
    ("SG-DETR + MomentMix (ours)",        "armB_metrics.json"),
]


def load_row(fname):
    m = json.load(open(os.path.join(OUT, fname)))
    vals = [m[k] for k in KEYS]
    return [round(v * 100, 1) if v <= 1 else round(v, 1) for v in vals]


ours = [(label, load_row(f)) for label, f in OURS_FILES]
fmt = lambda v: "–" if v is None else f"{v:.1f}"

# best-per-column within the ours panel (for bolding)
best_ours = [max(r[c] for _, r in ours) for c in range(len(COLS))]

# ---------------------------------------------------------------- PNG
header = ["Method"] + COLS
sec1 = [f"QVHighlights test (published, SG-DETR paper Table 3)"] + [""] * len(COLS)
sec2 = ["QVHighlights val (this thesis, identical from-scratch recipe)"] + [""] * len(COLS)
cells = [sec1] + [[n] + [fmt(v) for v in r] for n, r in PUBLISHED] \
      + [sec2] + [[n] + [fmt(v) for v in r] for n, r in ours]

fig, ax = plt.subplots(figsize=(10.5, 0.34 * (len(cells) + 2)), dpi=160)
ax.axis("off")
tbl = ax.table(cellText=cells, colLabels=header, loc="center", cellLoc="center")
tbl.auto_set_font_size(False)
tbl.set_fontsize(8.5)
tbl.scale(1, 1.35)
tbl.auto_set_column_width(col=list(range(len(header))))

n_pub = len(PUBLISHED)
for j in range(len(header)):
    tbl[0, j].set_text_props(weight="bold")
    for sec_row in (1, n_pub + 2):                      # section header rows
        tbl[sec_row, j].set_facecolor("#e8e8e8")
        tbl[sec_row, j].set_text_props(style="italic", ha="left")
for i, (_, r) in enumerate(ours):                       # ours panel
    row = n_pub + 3 + i
    for j in range(len(header)):
        tbl[row, j].set_facecolor("#f3f3f3")
        if j > 0 and r[j - 1] == best_ours[j - 1]:
            tbl[row, j].set_text_props(weight="bold")
tbl[0, 0].set_text_props(ha="left")
for i in range(1, len(cells) + 1):
    tbl[i, 0].set_text_props(ha="left")

fig.suptitle("QVHighlights benchmark: published methods vs this work", fontsize=10.5, y=0.98)
fig.text(0.02, 0.015,
         "† uses audio. HD columns are ≥ Very Good. Published rows: test split "
         "(hidden labels, server-evaluated). Our rows: val split (1549 queries); the released "
         "w/PT checkpoint anchors the val–test gap (val 58.93 vs test 58.8 mAP Avg).",
         fontsize=6.8)
fig.savefig(f"{OUT}/qvh_benchmark_table.png", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- CSV
with open(f"{OUT}/qvh_benchmark_table.csv", "w") as f:
    f.write("split,method," + ",".join(COLS) + "\n")
    for n, r in PUBLISHED:
        f.write("test (published)," + n.replace(" †", " (audio)") + "," +
                ",".join("" if v is None else str(v) for v in r) + "\n")
    for n, r in ours:
        f.write("val (ours)," + n + "," + ",".join(str(v) for v in r) + "\n")

# ---------------------------------------------------------------- LaTeX
def tex_row(name, r, bold_mask=None):
    vals = []
    for j, v in enumerate(r):
        s = fmt(v).replace("–", "--")
        if bold_mask and v is not None and v == bold_mask[j]:
            s = rf"\textbf{{{s}}}"
        vals.append(s)
    return name + " & " + " & ".join(vals) + r" \\"

lines = [
    r"% Generated by make_benchmark_table.py — QVH benchmark (paper Table 3 layout + ours)",
    r"\begin{table}[t]", r"\centering", r"\small",
    r"\begin{tabular}{l cc cc c cc}", r"\toprule",
    r" & \multicolumn{5}{c}{MR} & \multicolumn{2}{c}{HD ($\geq$ Very Good)} \\",
    r"\cmidrule(lr){2-6} \cmidrule(lr){7-8}",
    r"Method & R1@0.5 & R1@0.7 & mAP@0.5 & mAP@0.75 & mAP Avg & mAP & HIT@1 \\",
    r"\midrule",
    r"\multicolumn{8}{l}{\textit{QVHighlights test (published)}} \\",  # TODO: \cite each row
]
lines += [tex_row(n.replace("†", r"$\dagger$"), r) for n, r in PUBLISHED]
lines += [r"\midrule",
          r"\multicolumn{8}{l}{\textit{QVHighlights val (this thesis)}} \\"]
lines += [tex_row(n, r, best_ours) for n, r in ours]
lines += [r"\bottomrule", r"\end{tabular}",
          r"\caption{Comparison on QVHighlights. $\dagger$ uses audio. Published rows are",
          r"test-split results from the SG-DETR paper (Table 3); our rows are evaluated on",
          r"the public val split (test labels are hidden). The released w/PT checkpoint",
          r"anchors the val--test gap (58.93 val vs 58.8 test mAP Avg).}",
          r"\label{tab:qvh-benchmark}", r"\end{table}"]
with open(f"{OUT}/qvh_benchmark_table.tex", "w") as f:
    f.write("\n".join(lines) + "\n")

print("ours rows:")
for n, r in ours:
    print(f"  {n}: {r}")
print("saved qvh_benchmark_table.{png,csv,tex} to", OUT)
