# dlv – Spezifikation v0.1

Verilog-Modul → per Verilator + nanobind → importierbares Python-Modul.

## CLI
- [x] `pip install dlv`, Einstieg `dlv` (console_scripts)
- [x] argparse + argcomplete, schwere Imports erst nach autocomplete()
- [x] `dlv init` → bash/zsh/fish-Completion nach ~/.local/share/… installieren
- [x] `dlv build FILE.v --clock PORT [-o DIR] [--module M] [--trace] [-v]`
  - [x] Modulname ≠ Dateiname und kein --module → Fehler
  - [x] --clock ist Pflicht (v0.1: Module ohne Master-Clock unzulässig)
  - [x] --clock muss 1-Bit-Input sein, sonst Fehler
  - [x] -o DIR (Default: cwd), Ergebnis: DIR/counter.cpython-3xx-….so
- [x] Completion: --module → Module aus FILE, --clock → 1-Bit-Inputs

## Build-Ausgabe
- [x] Verilator/Compiler via subprocess, Output wird gepuffert
- [x] Output nur im Fehlerfall ausgeben (oder mit -v)
- [x] Hübscher Fortschritt mit `rich`: Schritte mit Spinner → ✓ / ✗
      (Verilator prüfen, Ports lesen, Binding generieren, verilieren, kompilieren)

## Mini-Verilog-Parser (nur Completion/Vorprüfung)
- [x] Regex-Tokenizer + kleiner Automat, Kommentare/Strings/`ifdef grob ignorieren
- [x] ANSI- und Nicht-ANSI-Ports, Breite nur als Text/Best Effort
- [x] Cache nach (pfad, mtime, größe) in .dlv/

## Build-Kette (Quelle der Wahrheit = Verilator)
- [x] `verilator` aus PATH, Version ≥ 5.022 prüfen
- [x] `verilator --json-only` → Ports (Name, Richtung, Breite)
- [x] Ports > 64 Bit → klarer Fehler (v0.1)
- [x] Jinja2-Template → nanobind-Binding (C++)
- [x] `verilator --cc --build` + g++ direkt mit nanobind-Flags → .so

## Binding-API
- [x] `counter.Model()` für mehrere Instanzen
- [x] Modul-Funktionen auf Default-Instanz: info, proc_ris, proc_fal, cycle_ris, cycle_fal, get, step
- [x] info() → {name, inputs:{p:w}, outputs:{p:w}, clock}
- [x] proc_ris(dict) → Inputs setzen, 1 Takt mit führender steigender Flanke
- [x] cycle_ris(n) → n weitere Takte; _fal-Varianten analog
- [x] get() → dict aller Outputs
- [x] step(n, {in: np.array}) → {out: np.array}, Taktschleife in C++
- [x] --trace: m.trace_open("x.fst") / m.trace_close()

## Doku
- [x] README.md: Installation, Voraussetzungen, Quickstart (counter.v), API, Completion

## Qualität
- [x] pytest: Parser gegen Verilator-JSON als Orakel
- [x] Integrationstest: counter.v bauen, importieren, zählen
- [x] Tests ohne Verilator → skip
- [x] kein Code aus dspsim (AGPL)

## Repo & Packaging (festgelegt)
- Lizenz: MIT
- src-Layout: src/dlv/{cli,parser,verilator,build,completion}.py, src/dlv/templates/binding.cpp.j2,
  tests/, examples/counter.v, README.md, SPEC.md, LICENSE, pyproject.toml, .gitignore
- hatchling, reines Wheel (py3-none-any), Templates als Package-Data
- Deps: nanobind, jinja2, argcomplete, rich, numpy; Python ≥ 3.10
- Tooling: uv (venv, pytest, build, publish)
