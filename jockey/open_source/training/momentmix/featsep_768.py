"""featsep in the re-extracted IV2-1B regime: cosine(query_text, video_clip) AUC of
GT clips vs background, stratified by moment length. Encodes text on the fly with
the matching text_encoder.pt so dims align (768). Run in fevenv (transformers+jit).

Usage: fevenv/bin/python featsep_768.py <video_feat_dir> [tag]
  video_feat_dir holds {vid}.pt of shape (L, D); only vids present are scored.
"""
import json, sys, os, glob
from collections import defaultdict
import torch
from transformers import BertTokenizer

ANN = "/workspace/data/qvhighlights/annotation/highlight_val_release.jsonl"
TXT_CKPT = "/workspace/fe_weights/text_encoder.pt"
VDIR = sys.argv[1]
TAG = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(VDIR.rstrip("/"))
dev = "cuda" if torch.cuda.is_available() else "cpu"

tok = BertTokenizer.from_pretrained("bert-large-uncased")
tmodel = torch.jit.load(TXT_CKPT, map_location=dev).eval()


def encode(text):
    t = tok(text, padding="max_length", truncation=True, max_length=32, return_tensors="pt").to(dev)
    with torch.no_grad():
        _, all_t, _ = tmodel(t.input_ids, t.attention_mask)
    feat = all_t[t.attention_mask.bool()]              # (ntok, D)
    return torch.nn.functional.normalize(feat.mean(0), dim=0).cpu()


def lenbin(d):
    for t, n in [(2, "2s"), (4, "4s"), (6, "6s"), (8, "8s"), (10, "10s"), (20, "10-20s"), (30, "20-30s"), (60, "30-60s")]:
        if d <= t:
            return n
    return "60s+"


ORDER = ["2s", "4s", "6s", "8s", "10s", "10-20s", "20-30s", "30-60s", "60s+"]
have = {os.path.basename(f)[:-3] for f in glob.glob(VDIR + "/*.pt")}
st = defaultdict(lambda: dict(n=0, auc=0.0, con=0.0))
qcache = {}
nvid = 0
for line in open(ANN):
    g = json.loads(line)
    vid = g["vid"]
    if vid not in have:
        continue
    V = torch.load(os.path.join(VDIR, vid + ".pt"), map_location="cpu").float()
    Vn = torch.nn.functional.normalize(V, dim=-1)
    qid = g["qid"]
    if qid not in qcache:
        qcache[qid] = encode(g["query"])
    rel = (Vn @ qcache[qid]).numpy()
    L = len(rel); cd = g["duration"] / L
    nvid += 1
    for w in g["relevant_windows"]:
        s, e = w; d = e - s
        gi = list(range(max(0, int(s / cd)), min(L, int(round(e / cd)) or 1)))
        if not gi or len(gi) >= L:
            continue
        bg = [i for i in range(L) if i not in set(gi)]
        gr = rel[gi]; br = rel[bg]
        auc = ((gr[:, None] > br[None, :]).sum() + 0.5 * (gr[:, None] == br[None, :]).sum()) / (len(gr) * len(br))
        x = st[lenbin(d)]; x["n"] += 1; x["auc"] += auc; x["con"] += gr.mean() - br.mean()
print(f"=== {TAG}: featsep AUC by moment length ({nvid} videos scored) ===")
print("len-bin    n   rawCosAUC  contrast")
for b in ORDER:
    x = st[b]
    if x["n"]:
        print("%-8s %4d   %5.3f     %+.4f" % (b, x["n"], x["auc"] / x["n"], x["con"] / x["n"]))
