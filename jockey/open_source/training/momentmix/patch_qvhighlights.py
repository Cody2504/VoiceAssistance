"""Apply the MomentMix hook to sg-detr's src/dataset/qvhighlights.py.

Three precise edits (each asserted before applying; idempotent):
 1. imports: copy + os.path.basename + the momentmix module
 2. __init__: accept momentmix_p / momentmix_eps_cut / momentmix_seed kwargs,
    enable ONLY when the annotation filename contains 'train'
 3. __getitem__: augmentation branch that deep-copies meta, mixes the RAW
    (pre-norm, pre-TEF) features with a random donor video, rewrites the
    labels, then re-applies normalization + TEF.

Run on the pod:  python patch_qvhighlights.py /workspace/sg-detr
"""
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else "/workspace/sg-detr"
PATH = f"{REPO}/src/dataset/qvhighlights.py"
src = open(PATH).read()

if "momentmix" in src:
    print("already patched — nothing to do")
    sys.exit(0)

# --- 1. imports -------------------------------------------------------------
old = '"""QVHighlights dataset."""\n\nimport random\n'
assert old in src, "import anchor not found"
src = src.replace(old, '"""QVHighlights dataset."""\n\nimport copy\nimport os\nimport random\n', 1)

old = "from src.utils.tensor_utils import l2_normalize_np_array, l2_normalize_tensor\n"
assert old in src, "tensor_utils import anchor not found"
src = src.replace(old, old + "from src.dataset.momentmix import apply_momentmix\n", 1)

# --- 2. __init__ ------------------------------------------------------------
old = """        clip_len: int = 2,
        max_windows: int = 10,
    ):"""
assert old in src, "__init__ signature anchor not found"
src = src.replace(old, """        clip_len: int = 2,
        max_windows: int = 10,
        momentmix_p: float = 0.0,
        momentmix_eps_cut: float = 0.5,
        momentmix_seed: Optional[int] = None,
    ):""", 1)

old = """        self.max_windows = max_windows
        self.shrink_rates = [1, 2, 4]"""
assert old in src, "__init__ body anchor not found"
src = src.replace(old, """        self.max_windows = max_windows
        self.shrink_rates = [1, 2, 4]

        # MomentMix (WACV 2026, arXiv:2412.20816) — online variant; train split only.
        self.momentmix_p = momentmix_p if "train" in os.path.basename(data_path) else 0.0
        self.momentmix_eps_cut = momentmix_eps_cut
        self._mmix_rng = random.Random(momentmix_seed)
        if self.momentmix_p > 0:
            logger.info(f"MomentMix ON (p={self.momentmix_p}, eps_cut={momentmix_eps_cut}) for {data_path}")""", 1)

# --- 3. raw loader + __getitem__ hook ----------------------------------------
old = """        feature_path = join(self.video_feat_dir, f"{vid}.pt")
        v_feat = torch.load(feature_path)
        v_feat = v_feat[: self.max_video_length].type(torch.float32)
        if self.normalize_video:
            v_feat = l2_normalize_tensor(v_feat)
        if self.use_tef:
            return self.add_tef_features(v_feat)
        return v_feat"""
assert old in src, "get_video_feat_by_vid body anchor not found"
src = src.replace(old, """        return self._finalize_video_feat(self._load_raw_video_feat(vid))

    def _load_raw_video_feat(self, vid: int) -> torch.Tensor:
        \"\"\"Raw truncated float32 features — no normalization, no TEF.

        Args:
            vid (int): index of the video.

        Returns:
            torch.Tensor: raw features (Lv, D).
        \"\"\"
        feature_path = join(self.video_feat_dir, f"{vid}.pt")
        v_feat = torch.load(feature_path)
        return v_feat[: self.max_video_length].type(torch.float32)

    def _finalize_video_feat(self, v_feat: torch.Tensor) -> torch.Tensor:
        \"\"\"Apply normalization + TEF on (possibly augmented) raw features.

        Args:
            v_feat (torch.Tensor): raw features.

        Returns:
            torch.Tensor: finalized features.
        \"\"\"
        if self.normalize_video:
            v_feat = l2_normalize_tensor(v_feat)
        if self.use_tef:
            return self.add_tef_features(v_feat)
        return v_feat""", 1)

old = """        meta = self.data[index]
        model_inputs: Dict[str, Any] = {}
        model_inputs["query_feat"] = self.get_query_feat_by_qid(meta["qid"])
        video_emb = self.get_video_feat_by_vid(meta["vid"])"""
assert old in src, "__getitem__ anchor not found"
src = src.replace(old, """        meta = self.data[index]
        model_inputs: Dict[str, Any] = {}
        model_inputs["query_feat"] = self.get_query_feat_by_qid(meta["qid"])
        if (
            self.momentmix_p > 0
            and self.audio_feat_dir is None
            and meta.get("relevant_clip_ids")
            and self._mmix_rng.random() < self.momentmix_p
        ):
            meta = copy.deepcopy(meta)
            raw = self._load_raw_video_feat(meta["vid"])
            donor_meta = self.data[self._mmix_rng.randrange(len(self.data))]
            donor_raw = self._load_raw_video_feat(donor_meta["vid"])
            raw, new_ids, new_sal, new_windows = apply_momentmix(
                raw,
                meta["relevant_clip_ids"],
                meta["saliency_scores"],
                donor_raw,
                float(self.clip_len),
                self.momentmix_eps_cut,
                self._mmix_rng,
            )
            if new_windows:
                meta["relevant_clip_ids"] = new_ids
                meta["saliency_scores"] = new_sal
                meta["relevant_windows"] = new_windows
            video_emb = self._finalize_video_feat(raw)
        else:
            video_emb = self.get_video_feat_by_vid(meta["vid"])""", 1)

open(PATH, "w").write(src)
print("patched", PATH)
