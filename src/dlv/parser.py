"""Mini Verilog parser: only for completion and pre-checks, best effort.

Verilator (--json-only) stays the source of truth for ports.
"""

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

_STRIP = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"', re.S)
_TOKEN = re.compile(
    r"`?[A-Za-z_][\w$]*|\d*'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]+|\d+|\\\S+|[^\s\w]", re.S
)
_DIRS = {"input", "output", "inout"}
_NET_WORDS = {
    "wire", "reg", "logic", "signed", "unsigned", "tri", "wand", "wor",
    "supply0", "supply1", "var", "bit", "integer",
}
_PARAM_WORDS = {"parameter", "localparam"}


@dataclass
class Port:
    name: str
    direction: str
    range: str | None = None  # text such as "WIDTH-1:0"
    width: int | None = None  # best effort


@dataclass
class Module:
    name: str
    ports: list[Port] = field(default_factory=list)
    params: dict[str, int | None] = field(default_factory=dict)


def _strip(text: str) -> str:
    text = _STRIP.sub(lambda m: "\n" * m.group().count("\n"), text)
    # `ifdef & co.: keep all branches, drop the directive lines themselves
    return re.sub(r"^[ \t]*`(?:ifn?def|elsif|else|endif|define|include|undef|timescale)[^\n]*$", "", text, flags=re.M)


def _eval(expr: str, params: dict) -> int | None:
    expr = re.sub(r"(\d*)'[sS]?[dD]([0-9_]+)", lambda m: m.group(2).replace("_", ""), expr)
    expr = re.sub(r"(\d*)'[sS]?[hH]([0-9a-fA-F_]+)", lambda m: str(int(m.group(2).replace("_", ""), 16)), expr)
    expr = re.sub(r"(\d*)'[sS]?[bB]([01_]+)", lambda m: str(int(m.group(2).replace("_", ""), 2)), expr)
    expr = expr.replace("$clog2", "_clog2").replace("/", "//")
    names = set(re.findall(r"[A-Za-z_]\w*", expr)) - {"_clog2"}
    if any(params.get(n) is None for n in names) or not re.fullmatch(r"[\w\s+\-*/()%<>&|^~]*", expr):
        return None
    try:
        return int(eval(expr, {"__builtins__": {}}, {**params, "_clog2": lambda v: max(v - 1, 0).bit_length()}))
    except Exception:
        return None


def _width(rng: str | None, params: dict) -> int | None:
    if rng is None:
        return 1
    hi, _, lo = rng.partition(":")
    h, l = _eval(hi, params), _eval(lo, params)
    return None if h is None or l is None else abs(h - l) + 1


def _split_top(tokens: list[str], sep: str = ",") -> list[list[str]]:
    out, cur, depth = [], [], 0
    for t in tokens:
        if t in "([{":
            depth += 1
        elif t in ")]}":
            depth -= 1
        if t == sep and depth == 0:
            out.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        out.append(cur)
    return out


def _range(tokens: list[str]) -> tuple[str | None, list[str]]:
    """Pop a leading [a:b] from tokens."""
    if tokens and tokens[0] == "[":
        end = tokens.index("]")
        return "".join(tokens[1:end]), tokens[end + 1:]
    return None, tokens


def _parse_params(tokens: list[str], mod: Module) -> None:
    for item in _split_top(tokens):
        item = [t for t in item if t not in _PARAM_WORDS | _NET_WORDS]
        _, item = _range(item)
        if "=" in item:
            i = item.index("=")
            if i:
                mod.params[item[i - 1]] = _eval("".join(item[i + 1:]), mod.params)


def _parse_decl(tokens: list[str], last: Port | None) -> Port | None:
    """One comma-separated item of an ANSI port list; inherits direction/range from the previous item."""
    if tokens and tokens[0] in _DIRS:
        d = tokens[0]
        rest = [t for t in tokens[1:] if t not in _NET_WORDS]
        rng, rest = _range(rest)
        return Port(rest[-1], d, rng)
    if last and len(tokens) == 1:
        return Port(tokens[0], last.direction, last.range)
    return None


def parse_text(text: str) -> list[Module]:
    toks = _TOKEN.findall(_strip(text))
    modules: list[Module] = []
    i = 0
    while i < len(toks):
        if toks[i] not in ("module", "macromodule") or i + 1 >= len(toks):
            i += 1
            continue
        mod = Module(toks[i + 1])
        i += 2
        if i < len(toks) and toks[i] == "#":  # parameter list
            j = _matching(toks, i + 1)
            _parse_params(toks[i + 2:j], mod)
            i = j + 1
        header: list[str] = []
        if i < len(toks) and toks[i] == "(":
            j = _matching(toks, i)
            header = toks[i + 1:j]
            i = j + 1
        end = i
        while end < len(toks) and toks[end] != "endmodule":
            end += 1
        body = toks[i:end]
        i = end
        _ports(mod, header, body)
        for p in mod.ports:
            p.width = _width(p.range, mod.params)
        modules.append(mod)
    return modules


def _matching(toks: list[str], start: int) -> int:
    depth = 0
    for j in range(start, len(toks)):
        if toks[j] == "(":
            depth += 1
        elif toks[j] == ")":
            depth -= 1
            if depth == 0:
                return j
    return len(toks) - 1


def _ports(mod: Module, header: list[str], body: list[str]) -> None:
    items = _split_top(header)
    ansi = any(it and it[0] in _DIRS for it in items)
    if ansi:
        last = None
        for it in items:
            last = _parse_decl(it, last)
            if last:
                mod.ports.append(last)
        return
    # non-ANSI: header only lists names, directions are declared in the body
    names = [it[0] for it in items if it]
    for stmt in _split_top(body, ";"):
        if stmt and stmt[0] in _PARAM_WORDS:
            _parse_params(stmt[1:], mod)
        if not stmt or stmt[0] not in _DIRS:
            continue
        d = stmt[0]
        rest = [t for t in stmt[1:] if t not in _NET_WORDS]
        rng, rest = _range(rest)
        for it in _split_top(rest):
            if it and it[-1] in names:
                mod.ports.append(Port(it[-1], d, rng))
    order = {n: k for k, n in enumerate(names)}
    mod.ports.sort(key=lambda p: order[p.name])


def parse_file(path: str | Path, cache_dir: str | Path | None = ".dlv") -> list[Module]:
    """Parse a file; results are cached by (path, mtime, size) in cache_dir/parser.json."""
    path = Path(path).resolve()
    st = path.stat()
    key = f"{path}|{st.st_mtime_ns}|{st.st_size}"
    cache_file = Path(cache_dir) / "parser.json" if cache_dir else None
    cache: dict = {}
    if cache_file and cache_file.exists():
        try:
            cache = json.loads(cache_file.read_text())
        except (OSError, ValueError):
            cache = {}
    if key in cache:
        return [Module(m["name"], [Port(**p) for p in m["ports"]], m["params"]) for m in cache[key]]
    mods = parse_text(path.read_text(errors="replace"))
    if cache_file:
        try:
            cache = {k: v for k, v in cache.items() if not k.startswith(f"{path}|")}
            cache[key] = [asdict(m) for m in mods]
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(cache))
        except OSError:
            pass
    return mods
