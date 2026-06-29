"""Update the qvhighlights.py apply_momentmix call to the windows-first signature."""
import sys

PATH = (sys.argv[1] if len(sys.argv) > 1 else "/workspace/sg-detr") + "/src/dataset/qvhighlights.py"
src = open(PATH).read()

old = """            raw, new_ids, new_sal, new_windows = apply_momentmix(
                raw,
                meta["relevant_clip_ids"],
                meta["saliency_scores"],
                donor_raw,
                float(self.clip_len),
                self.momentmix_eps_cut,
                self._mmix_rng,
            )"""
new = """            raw, new_ids, new_sal, new_windows = apply_momentmix(
                raw,
                meta["relevant_windows"],
                meta["relevant_clip_ids"],
                meta["saliency_scores"],
                donor_raw,
                float(self.clip_len),
                self.momentmix_eps_cut,
                self._mmix_rng,
            )"""
if new in src:
    print("already fixed")
    sys.exit(0)
assert old in src, "call-site anchor not found"
open(PATH, "w").write(src.replace(old, new, 1))
print("call site fixed:", PATH)
