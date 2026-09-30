"""Verilator access: version check and port extraction (source of truth)."""

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

MIN_VERSION = (5, 22)


class DlvError(Exception):
    """User-facing error: printed as one line, no traceback."""


@dataclass
class VPort:
    name: str
    direction: str  # "input" | "output" | "inout"
    width: int


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def check() -> str:
    """Return the verilator executable's version string, or raise DlvError."""
    exe = shutil.which("verilator")
    if not exe:
        raise DlvError("verilator not found in PATH (need >= 5.022)")
    out = run([exe, "--version"]).stdout
    m = re.search(r"Verilator (\d+)\.(\d+)", out)
    if not m:
        raise DlvError(f"cannot parse verilator version from: {out.strip()!r}")
    if (int(m[1]), int(m[2])) < MIN_VERSION:
        raise DlvError(f"verilator {m[1]}.{m[2]} is too old (need >= 5.022)")
    return f"{m[1]}.{m[2]}"


def root() -> Path:
    return Path(run(["verilator", "--getenv", "VERILATOR_ROOT"]).stdout.strip())


def ports(file: Path, top: str) -> list[VPort]:
    """Ports of module `top` in `file` as reported by `verilator --json-only`."""
    with tempfile.TemporaryDirectory() as tmp:
        r = run(["verilator", "--json-only", "--Mdir", tmp, "--top-module", top, str(file)])
        if r.returncode != 0:
            raise DlvError(f"verilator failed:\n{(r.stdout + r.stderr).strip()}")
        tree = next(Path(tmp).glob("*.tree.json"), None)
        if tree is None:
            raise DlvError("verilator produced no JSON output")
        return _ports_from_json(json.loads(tree.read_text()), top)


def _ports_from_json(tree: dict, top: str) -> list[VPort]:
    dtypes: dict[str, dict] = {}

    def collect(n):
        if isinstance(n, dict):
            if "addr" in n and str(n.get("type", "")).endswith("DTYPE"):
                dtypes[n["addr"]] = n
            for v in n.values():
                collect(v)
        elif isinstance(n, list):
            for v in n:
                collect(v)

    collect(tree)
    mod = next((m for m in tree["modulesp"] if m.get("name") == top), None)
    if mod is None:
        raise DlvError(f"module '{top}' not found by verilator")
    out = []
    for v in mod["stmtsp"]:
        if v.get("type") != "VAR" or v.get("direction") not in ("INPUT", "OUTPUT", "INOUT"):
            continue
        out.append(VPort(v["name"], v["direction"].lower(), _width(dtypes.get(v["dtypep"]), v["name"])))
    return out


def _width(dt: dict | None, name: str) -> int:
    if dt is None or dt["type"] != "BASICDTYPE":
        raise DlvError(f"port '{name}': unsupported type (only plain logic/bit vectors)")
    if "range" not in dt:
        return 1
    hi, lo = map(int, dt["range"].split(":"))
    return abs(hi - lo) + 1
