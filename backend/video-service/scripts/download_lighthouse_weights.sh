#!/usr/bin/env bash
#
# Download Lighthouse pretrained checkpoints + backbone weights into /models/lighthouse.
#
# CG-DETR (visual MR, CLIP+SlowFast features, trained on QVHighlights) and
# QD-DETR (audio MR, CLAP features, trained on Clotho-Moment) are the
# pretrained heads. SlowFast and PANN are the upstream feature extractors that
# CG-DETR / QD-DETR call internally.
#
# Run from the host: `bash scripts/download_lighthouse_weights.sh` then mount
# `./models/lighthouse:/models/lighthouse:ro` into the video-service container.
set -euo pipefail

DEST="${1:-./models/lighthouse}"
mkdir -p "${DEST}"
cd "${DEST}"

echo "Lighthouse checkpoints will be written to: $(pwd)"

fetch() {
  local url="$1"
  local name="$2"
  if [[ -f "${name}" ]]; then
    echo "  exists: ${name}"
    return
  fi
  echo "  fetching: ${name}"
  curl -fL -o "${name}.tmp" "${url}"
  mv "${name}.tmp" "${name}"
}

# Backbone — SlowFast 8x8 R50 (Kinetics-400). Used by CG-DETR's video encoder.
fetch \
  "https://dl.fbaipublicfiles.com/pyslowfast/model_zoo/kinetics400/SLOWFAST_8x8_R50.pkl" \
  "SLOWFAST_8x8_R50.pkl"

# Backbone — PANN Cnn14 (AudioSet). Optional for visual-only MR; required if
# the future audio-PANN moment-retrieval head is enabled.
fetch \
  "https://zenodo.org/record/3987831/files/Cnn14_mAP%3D0.431.pth" \
  "Cnn14_mAP=0.431.pth"

# QD-DETR (CLAP, Clotho-Moment) head checkpoint lives on Zenodo. NB the
# upstream filename has a HYPHEN (clotho-moment), but the lighthouse loader
# expects an UNDERSCORE — we rename on save. Was originally typo'd as
# underscore-everywhere and silently 404'd; fixed 2026-05-25.
fetch \
  "https://zenodo.org/records/13961029/files/clap_qd_detr_clotho-moment.ckpt?download=1" \
  "clap_qd_detr_clotho_moment.ckpt"

CG_DETR_TARGET="clip_slowfast_cg_detr_qvhighlight.ckpt"
if [[ ! -f "${CG_DETR_TARGET}" ]]; then
  echo "  fetching: ${CG_DETR_TARGET}"
  # Source: original CG-DETR repo's Google Drive (wjun0830/CGDETR README ->
  # Model Zoo -> QVHighlights). The folder contains 6 checkpoint snapshots
  # (~144 MB each); we only need model_best.ckpt — gdown --folder grabs all,
  # we keep one and drop the rest. ~860 MB transfer instead of the multi-GB
  # results.zip that Lighthouse hosts (which bundles every model variant).
  #
  # The file is byte-identical to what Lighthouse repackages as
  # results/cg_detr/qvhighlight/clip_slowfast/best.ckpt — Lighthouse just
  # wraps the upstream weights with their unified loader, doesn't retrain.
  command -v gdown >/dev/null 2>&1 \
    || { echo "ERROR: gdown not in PATH — was install_deps skipped?"; exit 1; }
  tmpdir=$(mktemp -d)
  ( cd "${tmpdir}" \
    && gdown --folder \
        "https://drive.google.com/drive/folders/1_hEqXbvDv4AyEn5unyn_kE784ruqrzEJ" \
        -O qvhighlight )
  if [[ ! -f "${tmpdir}/qvhighlight/model_best.ckpt" ]]; then
    rm -rf "${tmpdir}"
    echo "ERROR: gdown finished but model_best.ckpt not in folder — Drive may be rate-limiting"
    exit 1
  fi
  mv "${tmpdir}/qvhighlight/model_best.ckpt" "${CG_DETR_TARGET}"
  rm -rf "${tmpdir}"
else
  echo "  exists: ${CG_DETR_TARGET}"
fi

echo "Lighthouse weights ready in: $(pwd)"
ls -lh
