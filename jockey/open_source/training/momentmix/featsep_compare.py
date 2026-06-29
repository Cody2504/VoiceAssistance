"""Matched w2s-vs-w1s featsep: same videos, same moments, same query text (512-d).
For each GT moment in videos present in BOTH dirs, compute query-clip AUC (GT clips
vs background) at 2s-clip and 1s-clip granularity. Stratify by moment length.

Run in fevenv: fevenv/bin/python featsep_compare.py
"""
import json, os, glob
from collections import defaultdict
import torch
from transformers import BertTokenizer

ANN = "/workspace/data/qvhighlights/annotation/highlight_val_release.jsonl"
W2 = "/workspace/qvh_out_w2/video"
W1 = "/workspace/qvh_out_w1/video"
dev = "cuda" if torch.cuda.is_available() else "cpu"
tok = BertTokenizer.from_pretrained("bert-large-uncased")
tmodel = torch.jit.load("/workspace/fe_weights/text_encoder.pt", map_location=dev).eval()


def encode(text):
    t = tok(text, padding="max_length", truncation=True, max_length=32, return_tensors="pt").to(dev)
    with torch.no_grad():
        _, allt, _ = tmodel(t.input_ids, t.attention_mask)
    return torch.nn.functional.normalize(allt[t.attention_mask.bool()].mean(0), dim=0).cpu()


def auc_for(V, q, dur, w):
    Vn = torch.nn.functional.normalize(V.float(), dim=-1)
    rel = (Vn @ q).numpy()
    L = len(rel); cd = dur / L
    s, e = w
    gi = list(range(max(0, int(s / cd)), min(L, max(int(round(e / cd)), int(s / cd) + 1))))
    if not gi or len(gi) >= L:
        return None
    bg = [i for i in range(L) if i not in set(gi)]
    gr, br = rel[gi], rel[bg]
    return ((gr[:, None] > br[None, :]).sum() + 0.5 * (gr[:, None] == br[None, :]).sum()) / (len(gr) * len(br))


def lenbin(d):
    for t, n in [(2, "2s"), (4, "4s"), (6, "6s"), (8, "8s"), (10, "10s"), (20, "10-20s"), (30, "20-30s"), (60, "30-60s")]:
        if d <= t:
            return n
    return "60s+"


ORDER = ["2s", "4s", "6s", "8s", "10s", "10-20s", "20-30s", "30-60s", "60s+"]
both = {os.path.basename(f)[:-3] for f in glob.glob(W2 + "/*.pt")} & {os.path.basename(f)[:-3] for f in glob.glob(W1 + "/*.pt")}
st = defaultdict(lambda: dict(n=0, w2=0.0, w1=0.0))
qcache = {}
nv = 0
for line in open(ANN):
    g = json.loads(line)
    if g["vid"] not in both:
        continue
    V2 = torch.load(os.path.join(W2, g["vid"] + ".pt"), map_location="cpu")
    V1 = torch.load(os.path.join(W1, g["vid"] + ".pt"), map_location="cpu")
    if g["qid"] not in qcache:
        qcache[g["qid"]] = encode(g["query"])
    q = qcache[g["qid"]]; nv += 1
    for w in g["relevant_windows"]:
        a2 = auc_for(V2, q, g["duration"], w)
        a1 = auc_for(V1, q, g["duration"], w)
        if a2 is None or a1 is None:
            continue
        x = st[lenbin(w[1] - w[0])]; x["n"] += 1; x["w2"] += a2; x["w1"] += a1
print(f"=== MATCHED w2s vs w1s ({len(both)} videos, {nv} query-videos) ===")
print("len-bin    n   AUC_w2s  AUC_w1s   delta(w1-w2)")
for b in ORDER:
    x = st[b]
    if x["n"]:
        print("%-8s %4d   %5.3f    %5.3f    %+.3f" % (b, x["n"], x["w2"] / x["n"], x["w1"] / x["n"], (x["w1"] - x["w2"]) / x["n"]))
