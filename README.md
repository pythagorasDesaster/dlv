# dlv

Turn a Verilog module into an importable Python module — via [Verilator](https://www.veripool.org/verilator/) and [nanobind](https://github.com/wjakob/nanobind).

```console
$ dlv build counter.v --clock clk -o out/
✓ Checking verilator
✓ Reading ports
✓ Generating binding
✓ Running verilator 5.045
✓ Compiling extension
```

## Requirements

- Python ≥ 3.10
- `verilator` ≥ 5.022 in `PATH` (ports are read with `verilator --json-only`)
- `g++` (C++17) in `PATH`

## Install

```console
pip install dlv        # or: uv tool install dlv
```

## Quickstart

`examples/counter.v`:

```verilog
module counter #(parameter WIDTH = 8) (
    input  wire             clk,
    input  wire             rst,
    input  wire             en,
    output reg  [WIDTH-1:0] q
);
    always @(posedge clk) begin
        if (rst)      q <= 0;
        else if (en)  q <= q + 1;
    end
endmodule
```

```console
$ dlv build examples/counter.v --clock clk -o out/
$ cd out && python
```

```python
>>> import counter, numpy as np
>>> counter.proc_ris({"rst": 1, "en": 0})     # reset, one clock
>>> counter.proc_ris({"rst": 0, "en": 1})     # count, one clock
>>> counter.cycle_ris(4)                      # four more clocks
>>> counter.get()
{'q': 5}
>>> counter.step(3, {"en": np.ones(3)})       # clock loop in C++
{'q': array([6, 7, 8], dtype=uint8)}
```

## `dlv build`

```
dlv build FILE.v --clock PORT [-o DIR] [--module M] [--trace] [-v]
```

| Option | Meaning |
| --- | --- |
| `--clock PORT` | Master clock, required. Must be a 1-bit input. |
| `-o DIR` | Output directory (default: current directory). Result: `DIR/<module>.cpython-3xx-….so` |
| `--module M` | Top module. Default: the file name without `.v` — if no module has that name, `--module` is required. |
| `--trace` | Enable FST tracing (`trace_open` / `trace_close`). |
| `-v` | Show Verilator/compiler output (otherwise only shown on failure). |

Build files live in `.dlv/build/<module>/` in the current directory. Ports wider than 64 bits and `inout` ports are not supported (v0.1).

## API of the generated module

The module name is the Verilog module name. `Model()` creates an independent simulation instance; the module-level functions work on a default instance (created on first use) and have the same names.

| Call | Meaning |
| --- | --- |
| `info()` | `{name, inputs: {port: width}, outputs: {port: width}, clock}` |
| `proc_ris(inputs={})` | Set inputs, then one clock period starting with a rising edge |
| `proc_fal(inputs={})` | Same, starting with a falling edge |
| `cycle_ris(n=1)` / `cycle_fal(n=1)` | `n` more clock periods |
| `get()` | `{output: int}` for all outputs |
| `step(n, inputs={})` | `n` rising-edge clock periods in a C++ loop. `inputs` maps names to array-likes of length `n` (or length 1 = constant). Returns `{output: numpy array}` (uint8/16/32/64 by width), sampled after each period. |
| `trace_open(path)` / `trace_close()` | Only with `--trace`: write an FST waveform. Call `trace_close()` to flush. |

Ports up to 64 bits are Python `int`s. The clock cannot be set via `inputs`. Don't mix `_ris` and `_fal` calls on the same instance unless you accept an extra clock edge when switching.

## Shell completion

```console
dlv init [--shell bash|zsh|fish]
```

Installs argcomplete-based completion to `~/.local/share/bash-completion/completions/dlv`, `~/.local/share/zsh/site-functions/_dlv` or `~/.config/fish/completions/dlv.fish` (zsh: the directory must be in `fpath`). `--module` completes module names from `FILE.v`, `--clock` completes its 1-bit inputs.

## Development

```console
uv run pytest      # tests needing verilator are skipped without it
uv build
```

MIT licensed.
