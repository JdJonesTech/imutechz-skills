import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

FIX = ROOT / "tests" / "fixtures"
OUT = ROOT / "tests" / "_out"


@pytest.fixture
def smoke_project(tmp_path):
    """A copy of the fictional smoke project in a temp dir."""
    dst = tmp_path / "smoke"
    shutil.copytree(FIX / "smoke", dst)
    return dst
