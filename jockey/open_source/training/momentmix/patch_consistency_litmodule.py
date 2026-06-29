"""Wire the cross-view consistency loss into sg-detr's runner.

Requires patch_consistency_dataset.py to be applied first.

Edits (all gated by `model.runner.consistency_weight`, default 0.0 =
bit-identical behavior when off):
 - collate.py `move_inputs_to_device`: thread `video_feat_orig` (+its mask)
   and `cons_map` through the whitelist as src_vid_orig/src_vid_orig_mask/cons_map.
 - litmodule.py: new __init__ kwarg `consistency_weight`; pop the extra keys in
   `_process_batch` before the student forward; `_consistency_loss` method
   (eval-mode no-grad teacher forward on the original view of augmented rows,
   MSE between per-clip `local_saliency_scores` at mapped positions); add to
   total_loss and log `train/loss_consistency`.
 - configs/model/default.yaml: `runner.consistency_weight: 0.0`.

Run on the pod:  python patch_consistency_litmodule.py /workspace/sg-detr
"""
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else "/workspace/sg-detr"

# --- 1. move_inputs_to_device ------------------------------------------------
CPATH = f"{REPO}/src/dataset/collate.py"
csrc = open(CPATH).read()
if "src_vid_orig" in csrc:
    print("collate move_inputs_to_device already patched — skipping")
else:
    old = '''    if "audio_feat" in batched_model_inputs:
        model_inputs["src_aud"] = batched_model_inputs["audio_feat"][0].to(device, non_blocking=non_blocking)'''
    assert old in csrc, "move_inputs_to_device audio anchor not found"
    csrc = csrc.replace(old, old + '''

    if "video_feat_orig" in batched_model_inputs:
        model_inputs["src_vid_orig"] = batched_model_inputs["video_feat_orig"][0].to(device, non_blocking=non_blocking)
        model_inputs["src_vid_orig_mask"] = batched_model_inputs["video_feat_orig"][1].to(
            device, non_blocking=non_blocking,
        )
        model_inputs["cons_map"] = batched_model_inputs["cons_map"]''', 1)
    open(CPATH, "w").write(csrc)
    print("patched", CPATH)

# --- 2. litmodule -------------------------------------------------------------
PATH = f"{REPO}/src/litmodule.py"
src = open(PATH).read()
if "consistency_weight" in src:
    print("litmodule.py already patched — nothing to do")
    sys.exit(0)

old = """        checkpoint_path: Optional[str] = None,
        check_train_every_n_epoch: int = 5,
    ) -> None:"""
assert old in src, "__init__ signature anchor not found"
src = src.replace(old, """        checkpoint_path: Optional[str] = None,
        check_train_every_n_epoch: int = 5,
        consistency_weight: float = 0.0,
    ) -> None:""", 1)

old = """        self.check_train_every_n_epoch = check_train_every_n_epoch
        self.model = model"""
assert old in src, "__init__ body anchor not found"
src = src.replace(old, """        self.check_train_every_n_epoch = check_train_every_n_epoch
        self.consistency_weight = consistency_weight
        self.model = model""", 1)

old = """        batch, targets = move_inputs_to_device(batch, self.device, non_blocking=True)
        outputs = self.model(targets=targets, meta=meta, **batch)"""
assert old in src, "_process_batch anchor not found"
src = src.replace(old, """        batch, targets = move_inputs_to_device(batch, self.device, non_blocking=True)
        src_vid_orig = batch.pop("src_vid_orig", None)
        src_vid_orig_mask = batch.pop("src_vid_orig_mask", None)
        cons_map = batch.pop("cons_map", None)
        outputs = self.model(targets=targets, meta=meta, **batch)""", 1)

old = """            self.train_matching_metrics.update(matching)"""
assert old in src, "train-branch anchor not found"
src = src.replace(old, """            self.train_matching_metrics.update(matching)

            if self.consistency_weight > 0 and src_vid_orig is not None:
                cons_loss = self._consistency_loss(
                    batch, outputs, src_vid_orig, src_vid_orig_mask, cons_map,
                )
                if cons_loss is not None:
                    self.log(
                        f"{prefix}/loss_consistency",
                        cons_loss,
                        on_step=False,
                        on_epoch=True,
                        sync_dist=True,
                        batch_size=self.model.batch_size,
                    )
                    total_loss = total_loss + self.consistency_weight * cons_loss""", 1)

old = """    def training_step(self, batch, batch_idx: int) -> Tensor:"""
assert old in src, "training_step anchor not found"
src = src.replace(old, '''    def _consistency_loss(  # noqa: WPS210
        self,
        batch: Dict[str, Any],
        outputs: Dict[str, Any],
        src_vid_orig: Tensor,
        src_vid_orig_mask: Tensor,
        cons_map: List[Any],
    ) -> Optional[Tensor]:
        """Cross-view consistency (plan 2026-06-12, Part 1).

        Augmented (MomentMix) rows contain clips that also exist in the
        original video. A no-grad eval-mode teacher forward on the original
        view provides per-clip local-saliency targets; the student (mixed
        view) is penalized (MSE) for predicting differently on those clips.

        Args:
            batch (Dict[str, Any]): model kwargs of the student forward.
            outputs (Dict[str, Any]): student outputs.
            src_vid_orig (Tensor): original-view video features (B, L, D).
            src_vid_orig_mask (Tensor): original-view mask (B, L).
            cons_map (List[Any]): per-row [(ms, me, ss, se), ...] clip ranges.

        Returns:
            Optional[Tensor]: scalar loss, or None when no pairs in batch.
        """
        idx = [i for i, row_map in enumerate(cons_map) if row_map]
        if not idx:
            return None
        sel = torch.tensor(idx, device=self.device)
        teacher_inputs = {
            "src_txt": batch["src_txt"][sel],
            "src_txt_mask": batch["src_txt_mask"][sel],
            "src_vid": src_vid_orig[sel],
            "src_vid_mask": src_vid_orig_mask[sel],
            "vid": [batch["vid"][i] for i in idx],
            "qid": [batch["qid"][i] for i in idx],
        }
        if "src_aud" in batch:
            teacher_inputs["src_aud"] = batch["src_aud"][sel]
        was_training = self.model.training
        self.model.eval()
        with torch.no_grad():
            teacher_outputs = self.model(targets=None, meta=None, **teacher_inputs)
        if was_training:
            self.model.train()

        student_sal = outputs["local_saliency_scores"]
        teacher_sal = teacher_outputs["local_saliency_scores"]
        total = src_vid_orig.new_zeros(())
        n_pairs = 0
        for row, i in enumerate(idx):
            for ms, me, ss, se in cons_map[i]:
                n = min(me - ms, se - ss, student_sal.shape[1] - ms, teacher_sal.shape[1] - ss)
                if n <= 0:
                    continue
                diff = student_sal[i, ms:ms + n] - teacher_sal[row, ss:ss + n].detach()
                total = total + (diff ** 2).sum()
                n_pairs += n
        if n_pairs == 0:
            return None
        return total / n_pairs

    def training_step(self, batch, batch_idx: int) -> Tensor:''', 1)

open(PATH, "w").write(src)
print("patched", PATH)

# --- 3. runner config ----------------------------------------------------------
YPATH = f"{REPO}/configs/model/default.yaml"
ysrc = open(YPATH).read()
if "consistency_weight" in ysrc:
    print("model/default.yaml already patched — skipping")
else:
    old = "  check_train_every_n_epoch: ${model.check_train_every_n_epoch}\n"
    assert old in ysrc, "runner config anchor not found"
    ysrc = ysrc.replace(old, old + "  consistency_weight: 0.0\n", 1)
    open(YPATH, "w").write(ysrc)
    print("patched", YPATH)
