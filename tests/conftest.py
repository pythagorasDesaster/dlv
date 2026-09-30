import shutil

import pytest

from dlv import verilator


def _have_verilator() -> bool:
    if not shutil.which("verilator"):
        return False
    try:
        verilator.check()
    except verilator.DlvError:
        return False
    return True


requires_verilator = pytest.mark.skipif(not _have_verilator(), reason="verilator >= 5.022 not available")
