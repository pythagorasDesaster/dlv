import os
import subprocess
import sys

import pytest

from dlv.cli import main


@pytest.mark.parametrize("shell,rel", [
    ("bash", ".local/share/bash-completion/completions/dlv"),
    ("zsh", ".local/share/zsh/site-functions/_dlv"),
    ("fish", ".config/fish/completions/dlv.fish"),
])
def test_init(shell, rel, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert main(["init", "--shell", shell]) == 0
    assert "dlv" in (tmp_path / rel).read_text()


def complete(line, cwd):
    out = cwd / "comp.out"
    env = {**os.environ, "_ARGCOMPLETE": "1", "_ARGCOMPLETE_IFS": "\n", "COMP_LINE": line,
           "COMP_POINT": str(len(line)), "_ARGCOMPLETE_SHELL": "bash", "COMP_TYPE": "9",
           "_ARGCOMPLETE_STDOUT_FILENAME": str(out)}
    subprocess.run([sys.executable, "-m", "dlv.cli"], cwd=cwd, env=env, capture_output=True)
    return out.read_text().split("\n")


def test_clock_and_module_completion(tmp_path):
    (tmp_path / "x.v").write_text("module x(input clk, input [3:0] d, input rst, output q); endmodule\nmodule y(input a); endmodule")
    out = complete("dlv build x.v --clock ", tmp_path)
    assert {"clk", "rst"} <= set(out) and "d" not in out
    assert {"x", "y"} <= set(complete("dlv build x.v --module ", tmp_path))
