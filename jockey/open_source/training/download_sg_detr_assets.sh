#!/usr/bin/env bash
#
# Download SG-DETR pretrained checkpoints + InternVideo2-1b (InterVidV2-1b)
# pre-extracted features into a local assets dir.
#
# WHY: SG-DETR (WACV 2026, github.com/ai-forever/sg-detr) ships everything we
# need to (a) reproduce its SOTA numbers without re-running the ~150k-clip
# InterVid-MR pretraining, and (b) get ready-made InternVideo2-1b features for
# QVHighlights / Charades / TACoS so we can train our R2-adapter / CG-DETR
# baseline on the SAME backbone features SG-DETR uses. The "w/ PT" checkpoints
# are the pretraining-boosted ones; the plain ones are train-from-scratch.
#
# All URLs verified public (HTTP 200) on 2026-06-03. If a download fails with a
# Drive quota error, retry later — Google rate-limits anonymous folder pulls.
#
# Usage:
#   bash download_sg_detr_assets.sh [DEST]          # default DEST=./assets/sg_detr
#   ASSETS=ckpt   bash download_sg_detr_assets.sh   # checkpoints only
#   ASSETS=feats  bash download_sg_detr_assets.sh   # features only
#   ASSETS=qvh    bash download_sg_detr_assets.sh   # QVHighlights ckpt+feats only (smallest)
#
# Requires: gdown (`pip install gdown`). Large: full feature set is multi-GB —
# the features/ dir is gitignored, so this never bloats the repo.
set -euo pipefail

DEST="${1:-./assets/sg_detr}"
ASSETS="${ASSETS:-all}"          # all | ckpt | feats | qvh | weights
mkdir -p "${DEST}/checkpoints" "${DEST}/features" "${DEST}/fe_weights"

command -v gdown >/dev/null 2>&1 \
  || { echo "ERROR: gdown not in PATH. Run: pip install gdown" >&2; exit 1; }

echo "SG-DETR assets → $(cd "${DEST}" && pwd)   (mode: ${ASSETS})"

# ---- file (single .ckpt / .npz) by Drive file-id --------------------------
fetch_file() {
  local id="$1" out="$2"
  if [[ -f "${out}" ]]; then echo "  exists: ${out##*/}"; return; fi
  echo "  fetching file: ${out##*/}"
  gdown --id "${id}" -O "${out}.tmp" && mv "${out}.tmp" "${out}"
}
# ---- folder by Drive folder-id --------------------------------------------
fetch_folder() {
  local id="$1" out="$2"
  if [[ -d "${out}" ]] && [[ -n "$(ls -A "${out}" 2>/dev/null)" ]]; then
    echo "  exists: ${out##*/}/ (non-empty)"; return; fi
  echo "  fetching folder: ${out##*/}/"
  gdown --folder "https://drive.google.com/drive/folders/${id}" -O "${out}"
}

CK="${DEST}/checkpoints"
FT="${DEST}/features"

# === Pretrained checkpoints (Model Zoo) ====================================
if [[ "${ASSETS}" == "all" || "${ASSETS}" == "ckpt" || "${ASSETS}" == "qvh" ]]; then
  echo "-- checkpoints --"
  # QVHighlights (the head we baseline against; "w/ PT" is the SOTA ceiling).
  fetch_file "1BbPEV13fnyzFJqNdP3GtgJ3TsbGDLuVT" "${CK}/sgdetr_qvhighlights.ckpt"
  fetch_file "1KFuLQHPvoCExCDG-P7VByd5fOtFQ3x8S" "${CK}/sgdetr_qvhighlights_pt.ckpt"
  if [[ "${ASSETS}" != "qvh" ]]; then
    fetch_file "1KShUx5GmYncHLvhUw4Hc6XAencm-OSZ7" "${CK}/sgdetr_charades.ckpt"
    fetch_file "1-fUDhgj408m0INlZS4ILEh1bb27T2v5y" "${CK}/sgdetr_charades_pt.ckpt"
    fetch_file "1YZA-CG2tJLRSki5KUfuuikJ7nXsJ-ByY" "${CK}/sgdetr_tacos.ckpt"
    fetch_file "1HdZ-4mP28qfAiBFporLXY7JLpkneQkZp" "${CK}/sgdetr_tacos_pt.ckpt"
  fi
fi

# === Pre-extracted InternVideo2-1b features (Datasets) =====================
if [[ "${ASSETS}" == "all" || "${ASSETS}" == "feats" || "${ASSETS}" == "qvh" ]]; then
  echo "-- InternVideo2-1b features --"
  # QVHighlights features come as a single file; the rest are folders.
  fetch_file   "15R0uunpaq7JhSSSZv5GPUiv409GvlGLU" "${FT}/iv2_1b_qvhighlights.tar"
  if [[ "${ASSETS}" != "qvh" ]]; then
    fetch_folder "13hVI7Ce2rXANHw3P-ai5L7Btq2Sxewh4" "${FT}/iv2_1b_charades"
    fetch_folder "1tuLZq67v8rMAtiYv5V2B3otdhwuasPN-" "${FT}/iv2_1b_tacos"
    fetch_folder "1iQSeSwPCtg_KbDE_Z_fgnPQ_n8JHQQi7" "${FT}/iv2_1b_tvsum"
    fetch_folder "1G2cpX5MY-m_oBx4R0V1XdrNBDoG5fRB1" "${FT}/iv2_1b_youtubehl"
    # InterVid-MR pretraining features (~150k clips, LARGE — only needed to
    # reproduce the "w/ PT" results from scratch; skip if you use the *_pt.ckpt).
    if [[ "${ASSETS}" == "all" ]]; then
      fetch_folder "1R2mJd-AXiTHepLAimCr0zO9g7fr0JBny" "${FT}/iv2_1b_intervid_mr_pretrain"
    fi
  fi
fi

# === Feature-extractor weights (traced video/audio encoders) ===============
# Needed only to extract features from YOUR OWN videos via backend=sgdetr.
# Separate Drive folder (features-extractor/README.md). Contains the TorchScript
# video_encoder.pt the _SGDetrEncoder loads via torch.jit.load.
if [[ "${ASSETS}" == "all" || "${ASSETS}" == "weights" ]]; then
  echo "-- feature-extractor weights (video/audio encoders) --"
  fetch_folder "1YnKJV0vju1Hfx6l2b4rraeTLhRY7uJp9" "${DEST}/fe_weights"
  echo "  -> set IV2_SGDETR_VIDEO_CKPT to the video_encoder.pt under ${DEST}/fe_weights"
fi

echo "Done. Tree:"
find "${DEST}" -maxdepth 2 -type f | sed 's/^/  /' | head -40
echo
echo "Next: untar iv2_1b_qvhighlights.tar, then point training at FEATURES_DIR=${FT}."
echo "To EVALUATE SG-DETR's checkpoint instead of training: load *_pt.ckpt in the"
echo "sg-detr repo's eval (inference fits a single 24GB GPU)."
