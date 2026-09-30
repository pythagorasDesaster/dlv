import importlib
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from dlv.cli import main
from tests.conftest import requires_verilator

EXAMPLE = Path(__file__).parent.parent / "examples" / "counter.v"

pytestmark = requires_verilator


@pytest.fixture(scope="session")
def workdir(tmp_path_factory):
    return tmp_path_factory.mktemp("dlv")  # shared so the nanobind object is compiled once


@pytest.fixture(scope="session")
def counter(workdir):
    import os

    old = os.getcwd()
    os.chdir(workdir)
    try:
        assert main(["build", str(EXAMPLE), "--clock", "clk", "--trace", "-o", "out"]) == 0
    finally:
        os.chdir(old)
    sys.path.insert(0, str(workdir / "out"))
    mod = importlib.import_module("counter")
    yield mod
    sys.path.remove(str(workdir / "out"))


def test_info(counter):
    assert counter.info() == {
        "name": "counter", "inputs": {"rst": 1, "en": 1}, "outputs": {"q": 8}, "clock": "clk"
    }


def test_count_and_reset(counter):
    m = counter.Model()
    m.proc_ris({"rst": 1, "en": 0})
    assert m.get() == {"q": 0}
    m.proc_ris({"rst": 0, "en": 1})
    assert m.get() == {"q": 1}
    m.cycle_ris(4)
    assert m.get() == {"q": 5}
    m.proc_ris({"rst": 1})
    assert m.get() == {"q": 0}
    assert type(m.get()["q"]) is int


def test_falling_variants(counter):
    m = counter.Model()
    m.proc_fal({"rst": 1})
    m.proc_fal({"rst": 0, "en": 1})
    m.cycle_fal(3)
    assert m.get()["q"] == 4  # reset, then 1 + 3 periods (a falling-first period ends high, so it still sees one rising edge)


def test_instances_independent(counter):
    a, b = counter.Model(), counter.Model()
    a.proc_ris({"rst": 1})
    a.proc_ris({"rst": 0, "en": 1})
    a.cycle_ris(2)
    b.proc_ris({"rst": 1})
    assert (a.get()["q"], b.get()["q"]) == (3, 0)


def test_default_instance(counter):
    counter.proc_ris({"rst": 1, "en": 0})
    counter.proc_ris({"rst": 0, "en": 1})
    counter.cycle_ris(2)
    assert counter.get() == {"q": 3}


def test_step_numpy(counter):
    m = counter.Model()
    out = m.step(6, {"rst": np.array([1, 0, 0, 0, 1, 0]), "en": np.ones(6, dtype=np.int32)})
    assert out["q"].dtype == np.uint8
    assert out["q"].tolist() == [0, 1, 2, 3, 0, 1]
    assert m.step(3, {"en": 1})["q"].tolist() == [2, 3, 4]  # scalar broadcast, rst stays 0
    assert m.step(0)["q"].shape == (0,)


def test_wraparound(counter):
    m = counter.Model()
    out = m.step(300, {"rst": np.r_[1, np.zeros(299)], "en": 1})["q"]
    assert out[255] == 255 and out[256] == 0


def test_input_errors(counter):
    m = counter.Model()
    with pytest.raises(ValueError):
        m.proc_ris({"clk": 1})
    with pytest.raises(KeyError):
        m.proc_ris({"nope": 1})
    with pytest.raises(ValueError):
        m.step(3, {"en": np.ones(2)})


def test_trace(counter, workdir):
    f = workdir / "t.fst"
    m = counter.Model()
    m.trace_open(str(f))
    m.proc_ris({"rst": 1})
    m.cycle_ris(3)
    m.trace_close()
    assert f.exists() and f.stat().st_size > 0


def test_no_trace_build_has_no_trace_api(workdir):
    subprocess.run(
        [sys.executable, "-c",
         f"from dlv.cli import main; raise SystemExit(main(['build', {str(EXAMPLE)!r}, '--clock', 'clk', '-o', 'out2']))"],
        cwd=workdir, check=True, capture_output=True,
    )
    r = subprocess.run(
        [sys.executable, "-c", "import counter; print(hasattr(counter, 'trace_open'), counter.Model().step(1)['q'])"],
        cwd=workdir / "out2", capture_output=True, text=True, check=True,
    )
    assert r.stdout.split()[0] == "False"


# --- error cases: no traceback, exit code 1 ---------------------------------

def run_err(capfd, args, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["build", *args]) == 1
    err = capfd.readouterr().err
    assert "Traceback" not in err
    return err


def test_module_differs_from_filename(capfd, tmp_path, monkeypatch):
    f = tmp_path / "foo.v"
    f.write_text("module bar(input clk, output q); assign q = clk; endmodule")
    err = run_err(capfd, [str(f), "--clock", "clk"], tmp_path, monkeypatch)
    assert "--module" in err


def test_module_flag_selects_module(capfd, tmp_path, monkeypatch):
    f = tmp_path / "foo.v"
    f.write_text("module bar(input clk, output q); assign q = clk; endmodule")
    err = run_err(capfd, [str(f), "--clock", "nope", "--module", "bar"], tmp_path, monkeypatch)
    assert "not an input" in err  # got past module selection


def test_clock_missing(capfd, tmp_path, monkeypatch):
    err = run_err(capfd, [str(EXAMPLE)], tmp_path, monkeypatch)
    assert "--clock" in err


def test_clock_not_1bit_input(capfd, tmp_path, monkeypatch):
    f = tmp_path / "m.v"
    f.write_text("module m(input [1:0] clk, input c, output q); assign q = c; endmodule")
    assert "1-bit" in run_err(capfd, [str(f), "--clock", "clk"], tmp_path, monkeypatch)
    assert "not an input" in run_err(capfd, [str(f), "--clock", "q"], tmp_path, monkeypatch)


def test_port_wider_than_64(capfd, tmp_path, monkeypatch):
    f = tmp_path / "m.v"
    f.write_text("module m(input clk, input [64:0] a, output [64:0] q); assign q = a; endmodule")
    assert "64 bits" in run_err(capfd, [str(f), "--clock", "clk"], tmp_path, monkeypatch)


def test_verilator_missing(capfd, tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    assert "verilator not found" in run_err(capfd, [str(EXAMPLE), "--clock", "clk"], tmp_path, monkeypatch)


def test_verilator_too_old(capfd, tmp_path, monkeypatch):
    fake = tmp_path / "bin" / "verilator"
    fake.parent.mkdir()
    fake.write_text("#!/bin/sh\necho 'Verilator 5.020 2024-01-01'\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake.parent))
    assert "too old" in run_err(capfd, [str(EXAMPLE), "--clock", "clk"], tmp_path, monkeypatch)
