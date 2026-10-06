"""Load the PseudoFilter pipeline (Afzaal et al.) from the unmodified upstream file.

`unsw_improvement_2.py` is a Colab export that holds several experiments one after
another. Its last section ("Improved AOC-IDS - Final Version (v9)") is the paper's
PseudoFilter + MixupAug + LiteAE pipeline. We execute that section as it is, under a
module name other than __main__, so its own main block does not run. The file is
read, never written.
"""
import hashlib
import os
import types

# Defaults: next to the repository checkout (the same defaults as setup.sh).
_OUTSIDE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPSTREAM = os.environ.get("UPSTREAM", os.path.join(_OUTSIDE, "g1_upstream"))
DATA = os.environ.get("DATA", os.path.join(_OUTSIDE, "unsw_raw"))
PIPELINE_FILE = os.path.join(UPSTREAM, "AOC-IDS-Pipeline", "unsw_improvement_2.py")
PIPELINE_SHA256 = "16b6a333001ecf13467ab118fb3e66c4c2251c9db3e3799a5950e408d0543eeb"
SECTION_MARKER = "Improved AOC-IDS — Final Version (v9)"


def load_pseudofilter(data_dir=DATA):
    raw = open(PIPELINE_FILE, "rb").read()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != PIPELINE_SHA256:
        raise RuntimeError(f"{PIPELINE_FILE} differs from the pinned commit ({digest})")
    src = raw.decode("utf-8")
    start = src.index(SECTION_MARKER)
    start = src.rindex('"""', 0, start)  # include the section's opening docstring
    mod = types.ModuleType("pseudofilter_v9")
    exec(compile(src[start:], PIPELINE_FILE, "exec"), mod.__dict__)
    # The Colab paths are the only setting we change, and only on the class at run time.
    mod.Config.TRAIN_PATH = os.path.join(data_dir, "UNSW_NB15_training-set.csv")
    mod.Config.TEST_PATH = os.path.join(data_dir, "UNSW_NB15_testing-set.csv")
    return mod
