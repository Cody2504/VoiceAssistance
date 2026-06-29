"""Expose Lightning checkpoint resume in sg-detr's train CLI.

Adds optional `resume_from` config key: `+resume_from=/path/to/last.ckpt`
continues a run (optimizer/scheduler/epoch restored). Absent -> unchanged.

Run on the pod:  python patch_train_resume.py /workspace/sg-detr
"""
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else "/workspace/sg-detr"
PATH = f"{REPO}/src/cli/train.py"
src = open(PATH).read()

GOOD = '    trainer.fit(model=model, datamodule=datamodule, ckpt_path=config.get("resume_from", None))'
BAD = '    trainer.fit(model=model, datamodule=datamodule, ckpt_path=cfg.get("resume_from", None))'

if GOOD in src:
    print("already patched — nothing to do")
    sys.exit(0)
if BAD in src:  # repair the earlier broken patch (cfg -> config)
    src = src.replace(BAD, GOOD, 1)
else:
    old = "    trainer.fit(model=model, datamodule=datamodule)"
    assert old in src, "trainer.fit anchor not found"
    src = src.replace(old, GOOD, 1)
open(PATH, "w").write(src)
print("patched", PATH)
