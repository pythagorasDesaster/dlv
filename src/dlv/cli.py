# PYTHON_ARGCOMPLETE_OK
"""dlv command line. Heavy imports happen only after argcomplete."""

import argparse
import sys
from pathlib import Path


def _modules(parsed_args) -> list:
    from .parser import parse_file

    try:
        return parse_file(parsed_args.file)
    except (OSError, AttributeError):
        return []


def complete_module(prefix, parsed_args, **kw):
    return [m.name for m in _modules(parsed_args)]


def complete_clock(prefix, parsed_args, **kw):
    mods = _modules(parsed_args)
    name = parsed_args.module or Path(parsed_args.file).stem
    mod = next((m for m in mods if m.name == name), mods[0] if len(mods) == 1 else None)
    return [p.name for p in mod.ports if p.direction == "input" and p.width == 1] if mod else []


def make_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="dlv", description="Verilog module -> importable Python module (Verilator + nanobind)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build a Python module from a Verilog file")
    b.add_argument("file", metavar="FILE.v", help="Verilog source file")
    b.add_argument("--clock", metavar="PORT", help="master clock input (1 bit, required)").completer = complete_clock
    b.add_argument("-o", "--output", metavar="DIR", default=".", help="output directory (default: cwd)")
    b.add_argument("--module", metavar="M", help="top module (default: file name)").completer = complete_module
    b.add_argument("--trace", action="store_true", help="enable FST tracing (trace_open/trace_close)")
    b.add_argument("-v", "--verbose", action="store_true", help="show tool output")
    i = sub.add_parser("init", help="install shell completion")
    i.add_argument("--shell", choices=["bash", "zsh", "fish"], help="default: from $SHELL")
    return ap


def main(argv: list[str] | None = None) -> int:
    import argcomplete

    ap = make_parser()
    argcomplete.autocomplete(ap)
    args = ap.parse_args(argv)

    from .verilator import DlvError

    try:
        if args.cmd == "build":
            from .build import build

            build(Path(args.file), args.clock, Path(args.output), args.module, args.trace, args.verbose)
        else:
            from .completion import init

            init(args.shell)
    except DlvError as e:
        from rich.console import Console
        from rich.markup import escape

        Console(stderr=True, highlight=False).print(f"[red]error:[/red] {escape(str(e))}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
