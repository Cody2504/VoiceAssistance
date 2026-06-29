"""Add the cross-view consistency second view to sg-detr's dataset + collate.

Requires the stitch patch (patch_qvhighlights_stitch.py) to be applied first.

Adds (gated by new dataset kwarg `emit_consistency_view`, default False =
bit-identical behavior when off):
 - qvhighlights.py: for EVERY sample emit `video_feat_orig` (original-video
   view, fpn-padded like the main view) and `cons_map` (mixed->source clip
   ranges from org_clip_ids_order; [] for unaugmented rows).
 - collate.py: `cons_map` passes through as a plain list (video_feat_orig uses
   the default pad_sequences_1d branch untouched).
 - copies consistency_map.py into src/dataset/.

Run on the pod:  python patch_consistency_dataset.py /workspace/sg-detr
"""
import os
import shutil
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else "/workspace/sg-detr"
HERE = os.path.dirname(os.path.abspath(__file__))

# --- 0. ship the mapping module ----------------------------------------------
shutil.copy(os.path.join(HERE, "consistency_map.py"), f"{REPO}/src/dataset/consistency_map.py")

PATH = f"{REPO}/src/dataset/qvhighlights.py"
src = open(PATH).read()

if "emit_consistency_view" in src:
    print("qvhighlights.py already patched — skipping")
else:
    assert "_load_stitched_video_feat" in src, "stitch patch must be applied first"

    # --- 1. import -----------------------------------------------------------
    old = "from src.dataset.momentmix import apply_momentmix\n"
    assert old in src, "momentmix import anchor not found"
    src = src.replace(old, old + "from src.dataset.consistency_map import build_consistency_map\n", 1)

    # --- 2. __init__ kwarg ----------------------------------------------------
    old = """        momentmix_seed: Optional[int] = None,
    ):"""
    assert old in src, "__init__ signature anchor not found"
    src = src.replace(old, """        momentmix_seed: Optional[int] = None,
        emit_consistency_view: bool = False,
    ):""", 1)

    old = """        if self.momentmix_p > 0:
            logger.info(f"MomentMix ON (p={self.momentmix_p}, eps_cut={momentmix_eps_cut}) for {data_path}")"""
    assert old in src, "__init__ body anchor not found"
    src = src.replace(old, old + """

        # cross-view consistency (Part 1, plan 2026-06-12): emit the original
        # view + mixed->source map so the runner can run a teacher forward.
        self.emit_consistency_view = emit_consistency_view""", 1)

    # --- 3. __getitem__: second view before fpn padding ------------------------
    old = """        audio_emb = self.get_audio_feat_by_vid(meta["vid"])
        video_emb, audio_emb = self.add_fpn_padding(video_emb, audio_emb)"""
    assert old in src, "__getitem__ fpn-padding anchor not found"
    src = src.replace(old, """        audio_emb = self.get_audio_feat_by_vid(meta["vid"])
        if self.emit_consistency_view:
            if meta.get("org_clip_ids_order"):
                orig_emb = self.get_video_feat_by_vid(meta["vid"])
                cons_map = build_consistency_map(meta["org_clip_ids_order"], meta["vid"])
            else:
                orig_emb, cons_map = video_emb, []
            orig_emb, _ = self.add_fpn_padding(orig_emb, None)
            model_inputs["video_feat_orig"] = orig_emb
            model_inputs["cons_map"] = cons_map
        video_emb, audio_emb = self.add_fpn_padding(video_emb, audio_emb)""", 1)

    open(PATH, "w").write(src)
    print("patched", PATH)

# --- 4. collate passthrough ---------------------------------------------------
CPATH = f"{REPO}/src/dataset/collate.py"
csrc = open(CPATH).read()
if "cons_map" in csrc:
    print("collate.py already patched — skipping")
else:
    old = '''        if key in {"qid", "vid"}:'''
    assert old in csrc, "collate qid/vid anchor not found"
    csrc = csrc.replace(old, '''        if key in {"qid", "vid", "cons_map"}:''', 1)
    open(CPATH, "w").write(csrc)
    print("patched", CPATH)
