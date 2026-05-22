# S3 test scripts (`jockeyassistant` bucket)

Standalone helpers for poking at the AWS S3 bucket without touching the
production video-service / MinIO stack.

## Setup

Add to `.env` (project root):

```env
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=ap-southeast-1     # whatever region you created the bucket in
S3_BUCKET=jockeyassistant
```

Dependencies are already in `.venv` (`boto3`, `python-dotenv`, `fastapi`, `uvicorn`).

## Scripts

| Script | What it does |
|---|---|
| `s3_smoke_test.py` | Upload `SAT table.mp4`, list, download back, presign — verifies creds/bucket end-to-end. |
| `s3_ingest.py`     | Upload any local video(s) with an ffmpeg-generated thumbnail and duration metadata. |
| `s3_browser.py`    | FastAPI on `:8765` that backs the frontend `/s3-test` page. |

### Quick start

```bash
# from project root, with venv python on PATH
VPY=.venv/bin/python3

# 1. smoke test (uploads SAT table.mp4 → s3://jockeyassistant/videos/SAT_table.mp4)
$VPY scripts/s3_smoke_test.py

# 2. populate the bucket with the videos you already have
$VPY scripts/s3_ingest.py --all
#    → uploads *.mp4 from project root and ./samples/ (if present)

# 3. open the test page
$VPY scripts/s3_browser.py   # leave running, listens on :8765
# in another shell:
cd frontend && npm run dev
# visit http://localhost:5173/s3-test
```

## S3 key layout

```
videos/<basename>.mp4   ContentType=video/mp4    metadata: duration-s
thumbs/<basename>.jpg   ContentType=image/jpeg   (single ffmpeg frame at ~1s)
```

## Finding more math / sport test videos

You already have `SAT table.mp4`, `tennis.mp4`, `football.mp4` at the project
root. For additional CC-licensed clips:

- **Math:** 3Blue1Brown channel on YouTube ships under CC-BY (download
  manually). Khan Academy lessons are CC-BY-NC-SA. Numberphile videos are
  YouTube-licensed (no redistribution) — use only as personal test fixtures.
- **Sport:** Wikimedia Commons has hundreds of CC-BY/CC0 sport clips —
  search e.g. <https://commons.wikimedia.org/wiki/Category:Videos_of_sports>.
  Pixabay and Pexels both offer royalty-free MP4 downloads (no API key needed
  for one-off downloads).
- **Generic test clips:** <https://samplelib.com/sample-mp4.html> is fine for
  pipeline smoke-tests.

Drop new clips into `./samples/` then re-run `python scripts/s3_ingest.py --all`.
