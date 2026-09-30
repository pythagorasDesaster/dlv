"""Build pipeline: Verilator -> nanobind binding -> shared library."""

import shutil
import sysconfig
from contextlib import contextmanager
from pathlib import Path

from rich.console import Console
from rich.markup import escape

from . import verilator
from .verilator import DlvError, VPort

TEMPLATES = Path(__file__).parent / "templates"
console = Console(highlight=False)


@contextmanager
def step(label: str):
    """Spinner while running, then ✓ / ✗."""
    with console.status(label):
        try:
            yield
        except BaseException:
            console.print(f"[red]✗[/red] {escape(label)}")
            raise
    console.print(f"[green]✓[/green] {escape(label)}")


def sh(cmd: list[str], verbose: bool, cwd: Path | None = None) -> None:
    """Run a command with buffered output; print it only on failure or with -v."""
    r = verilator.run([str(c) for c in cmd], cwd=cwd)
    out = (r.stdout + r.stderr).strip()
    if verbose and out:
        console.print(escape(out))
    if r.returncode != 0:
        raise DlvError(f"{cmd[0]} failed (exit {r.returncode})" + ("" if verbose else f":\n{out}"))


def ctype(width: int) -> str:
    return "uint8_t" if width <= 8 else "uint16_t" if width <= 16 else "uint32_t" if width <= 32 else "uint64_t"


def pick_module(file: Path, module: str | None) -> str:
    from .parser import parse_file

    mods = [m.name for m in parse_file(file)]
    if module:
        return module
    if file.stem not in mods:
        hint = f" (modules in file: {', '.join(mods)})" if mods else ""
        raise DlvError(f"module name differs from file name '{file.name}'; pass --module{hint}")
    return file.stem


def check_ports(ports: list[VPort], clock: str) -> VPort:
    by_name = {p.name: p for p in ports}
    clk = by_name.get(clock)
    if clk is None or clk.direction != "input":
        raise DlvError(f"--clock {clock}: not an input port (inputs: {', '.join(p.name for p in ports if p.direction == 'input')})")
    if clk.width != 1:
        raise DlvError(f"--clock {clock}: must be a 1-bit input, but is {clk.width} bits wide")
    for p in ports:
        if p.width > 64:
            raise DlvError(f"port '{p.name}' is {p.width} bits wide; ports > 64 bits are not supported")
        if p.direction == "inout":
            raise DlvError(f"port '{p.name}': inout ports are not supported")
    return clk


def render(top: str, ports: list[VPort], clock: str, trace: bool) -> str:
    from jinja2 import Environment, FileSystemLoader

    def view(p: VPort) -> dict:
        return {"name": p.name, "width": p.width, "ctype": ctype(p.width), "mask": hex((1 << p.width) - 1)}

    env = Environment(loader=FileSystemLoader(TEMPLATES), keep_trailing_newline=True)
    return env.get_template("binding.cpp.j2").render(
        top=top,
        clock=clock,
        trace=trace,
        inputs=[view(p) for p in ports if p.direction == "input" and p.name != clock],
        outputs=[view(p) for p in ports if p.direction == "output"],
    )


def nanobind_object(work: Path, cxxflags: list[str], verbose: bool) -> Path:
    """nanobind runtime, compiled once per (nanobind version, python) and cached."""
    import nanobind

    tag = f"{nanobind.__version__}-{sysconfig.get_config_var('SOABI') or 'py'}"
    obj = work.parent / f"_nanobind-{tag}" / "nb_combined.o"
    if not obj.exists():
        obj.parent.mkdir(parents=True, exist_ok=True)
        src = Path(nanobind.source_dir()) / "nb_combined.cpp"
        robin = Path(nanobind.include_dir()).parent / "ext" / "robin_map" / "include"
        sh(["g++", *cxxflags, "-I", nanobind.include_dir(), "-I", robin, "-c", src, "-o", obj], verbose)
    return obj


def build(file: Path, clock: str | None, out: Path, module: str | None = None, trace: bool = False, verbose: bool = False) -> Path:
    import nanobind

    if not clock:
        raise DlvError("--clock is required (modules without a master clock are not supported)")
    file = file.resolve()
    if not file.exists():
        raise DlvError(f"file not found: {file}")
    with step("Checking verilator"):
        version = verilator.check()
        if not shutil.which("g++"):
            raise DlvError("g++ not found in PATH")
    top = pick_module(file, module)
    with step("Reading ports"):
        ports = verilator.ports(file, top)
    check_ports(ports, clock)
    work = Path(".dlv/build").resolve() / top
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    with step("Generating binding"):
        (work / "binding.cpp").write_text(render(top, ports, clock, trace))
    with step(f"Running verilator {version}"):
        sh(
            ["verilator", "--cc", "--build", "-j", "0", "--Mdir", work, "--top-module", top,
             "-Wno-fatal", "-CFLAGS", "-fPIC -O2", *(["--trace-fst"] if trace else []), file],
            verbose,
        )
    with step("Compiling extension"):
        cxxflags = ["-std=c++17", "-O2", "-fPIC", "-fvisibility=hidden", "-DNDEBUG",
                    "-I", sysconfig.get_paths()["include"]]
        nb_obj = nanobind_object(work, cxxflags, verbose)
        vroot = verilator.root() / "include"
        target = out.resolve() / f"{top}{sysconfig.get_config_var('EXT_SUFFIX')}"
        out.mkdir(parents=True, exist_ok=True)
        sh(
            ["g++", *cxxflags, "-shared", "-I", nanobind.include_dir(), "-I", work, "-I", vroot,
             "-I", vroot / "vltstd", work / "binding.cpp", nb_obj, work / f"V{top}__ALL.a",
             work / "libverilated.a", "-pthread", "-lz", "-o", target],
            verbose,
        )
    console.print(f"Built [bold]{escape(str(target))}[/bold]", soft_wrap=True)
    return target
