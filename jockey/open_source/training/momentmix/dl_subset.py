"""Download a subset of QVHighlights val videos via yt-dlp (segment + 30fps).

QVH vid = '{ytid}_{start}_{end}' -> download [start,end] of the youtube video,
re-encode to 30fps, save as {out}/{vid}.mp4. Prioritizes videos that contain a
short (<=6s) GT moment so the 2s-bin has samples. Skips unavailable (link-rot).

Usage: python dl_subset.py <out_dir> <target_n> [vid1 vid2 ...]
  if explicit vids given, downloads exactly those; else auto-selects.
"""
import json, os, re, subprocess, sys

ANN = "/workspace/data/qvhighlights/annotation/highlight_val_release.jsonl"
OUT = sys.argv[1]
TARGET = int(sys.argv[2])
EXPLICIT = sys.argv[3:]
os.makedirs(OUT, exist_ok=True)
PY = "/workspace/tvenv/bin/python"  # has yt-dlp


def candidates():
    seen, out = set(), []
    for line in open(ANN):
        v = json.loads(line)
        vid = v["vid"]
        if vid in seen:
            continue
        seen.add(vid)
        has_short = any((w[1] - w[0]) <= 6 for w in v.get("relevant_windows", []))
        out.append((vid, has_short))
    # short-containing first
    out.sort(key=lambda x: not x[1])
    return [v for v, _ in out]


def parse(vid):
    m = re.match(r"(.+)_(\d+\.?\d*)_(\d+\.?\d*)$", vid)
    return m.group(1), float(m.group(2)), float(m.group(3))


def download(vid):
    ytid, s, e = parse(vid)
    tmp = os.path.join(OUT, f"_tmp_{vid}")
    final = os.path.join(OUT, f"{vid}.mp4")
    if os.path.exists(final):
        return True
    r = subprocess.run(
        [PY, "-m", "yt_dlp", "-q", "--no-warnings", "-f", "best[height<=360][ext=mp4]/best[height<=360]/worst",
         "--download-sections", f"*{s}-{e}", "-o", tmp + ".%(ext)s",
         f"https://www.youtube.com/watch?v={ytid}"],
        capture_output=True, timeout=180,
    )
    dl = next((os.path.join(OUT, f) for f in os.listdir(OUT) if f.startswith(f"_tmp_{vid}")), None)
    if dl is None or not os.path.exists(dl):
        return False
    # re-encode to 30fps (keep audio for the extractor's audio path)
    rr = subprocess.run(["ffmpeg", "-y", "-i", dl, "-r", "30", "-loglevel", "error", final],
                        capture_output=True, timeout=180)
    os.remove(dl)
    return os.path.exists(final) and os.path.getsize(final) > 0


vids = EXPLICIT if EXPLICIT else candidates()
got = []
for vid in vids:
    if len(got) >= TARGET:
        break
    try:
        ok = download(vid)
    except Exception as e:
        ok = False
    print(("OK   " if ok else "FAIL ") + vid, flush=True)
    if ok:
        got.append(vid)
print(f"DOWNLOADED {len(got)}/{TARGET}: {' '.join(got)}")
