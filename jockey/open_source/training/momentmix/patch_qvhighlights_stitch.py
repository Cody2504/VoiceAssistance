"""Add offline-MomentMix stitching to sg-detr's src/dataset/qvhighlights.py.

Requires the online-momentmix patches (patch_qvhighlights.py + fix_callsite.py)
to be applied first — it anchors on the helpers they introduced.

Rows produced by gen_qvh_mmix.py carry `org_clip_ids_order` =
[[vid, [clip_start, clip_end]], ...]; the video feature is rebuilt by
concatenating RAW (pre-norm, pre-TEF) slices of the referenced feature files,
then normalization + TEF are re-applied.

Run on the pod:  python patch_qvhighlights_stitch.py /workspace/sg-detr
"""
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else "/workspace/sg-detr"
PATH = f"{REPO}/src/dataset/qvhighlights.py"
src = open(PATH).read()

if "_load_stitched_video_feat" in src:
    print("already patched — nothing to do")
    sys.exit(0)

assert "_load_raw_video_feat" in src, "online momentmix patch must be applied first"

# --- 1. stitching loader next to the raw/finalize helpers --------------------
old = '''    def _finalize_video_feat(self, v_feat: torch.Tensor) -> torch.Tensor:'''
assert old in src, "_finalize_video_feat anchor not found"
src = src.replace(old, '''    def _load_stitched_video_feat(self, org_clip_ids_order) -> torch.Tensor:
        """Rebuild a MomentMix video from raw clip slices (offline variant).

        Args:
            org_clip_ids_order: [[vid, [clip_start, clip_end]], ...] recipe.

        Returns:
            torch.Tensor: raw stitched features (Lv, D).
        """
        parts = [self._load_raw_video_feat(vid)[s:e] for vid, (s, e) in org_clip_ids_order]
        return torch.cat(parts, dim=0)[: self.max_video_length]

    def _finalize_video_feat(self, v_feat: torch.Tensor) -> torch.Tensor:''', 1)

# --- 2. __getitem__ branch ----------------------------------------------------
old = '''        if (
            self.momentmix_p > 0
            and self.audio_feat_dir is None
            and meta.get("relevant_clip_ids")
            and self._mmix_rng.random() < self.momentmix_p
        ):'''
assert old in src, "__getitem__ online-momentmix anchor not found"
src = src.replace(old, '''        if meta.get("org_clip_ids_order"):
            video_emb = self._finalize_video_feat(
                self._load_stitched_video_feat(meta["org_clip_ids_order"])
            )
        elif (
            self.momentmix_p > 0
            and self.audio_feat_dir is None
            and meta.get("relevant_clip_ids")
            and self._mmix_rng.random() < self.momentmix_p
        ):''', 1)

open(PATH, "w").write(src)
print("patched", PATH)
