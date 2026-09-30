# dlv – Spezifikation v0.1

Verilog-Modul → per Verilator + nanobind → importierbares Python-Modul.

## CLI
- [ ] `pip install dlv`, Einstieg `dlv` (console_scripts)
- [ ] argparse + argcomplete, schwere Imports erst nach autocomplete()
- [ ] `dlv init` → bash/zsh/fish-Completion nach ~/.local/share/… installieren
- [ ] `dlv build FILE.v --clock PORT [-o DIR] [--module M] [--trace] [-v]`
  - [ ] Modulname ≠ Dateiname und kein --module → Fehler
  - [ ] --clock ist Pflicht (v0.1: Module ohne Master-Clock unzulässig)
  - [ ] --clock muss 1-Bit-Input sein, sonst Fehler
  - [ ] -o DIR (Default: cwd), Ergebnis: DIR/counter.cpython-3xx-….so
- [ ] Completion: --module → Module aus FILE, --clock → 1-Bit-Inputs

## Build-Ausgabe
- [ ] Verilator/Compiler via subprocess, Output wird gepuffert
- [ ] Output nur im Fehlerfall ausgeben (oder mit -v)
- [ ] Hübscher Fortschritt mit `rich`: Schritte mit Spinner → ✓ / ✗
      (Verilator prüfen, Ports lesen, Binding generieren, verilieren, kompilieren)

## Mini-Verilog-Parser (nur Completion/Vorprüfung)
- [ ] Regex-Tokenizer + kleiner Automat, Kommentare/Strings/`ifdef grob ignorieren
- [ ] ANSI- und Nicht-ANSI-Ports, Breite nur als Text/Best Effort
- [ ] Cache nach (pfad, mtime, größe) in .dlv/

## Build-Kette (Quelle der Wahrheit = Verilator)
- [ ] `verilator` aus PATH, Version ≥ 5.022 prüfen
- [ ] `verilator --json-only` → Ports (Name, Richtung, Breite)
- [ ] Ports > 64 Bit → klarer Fehler (v0.1)
- [ ] Jinja2-Template → nanobind-Binding (C++)
- [ ] `verilator --cc --build` + g++ direkt mit nanobind-Flags → .so

## Binding-API
- [ ] `counter.Model()` für mehrere Instanzen
- [ ] Modul-Funktionen auf Default-Instanz: info, proc_ris, proc_fal, cycle_ris, cycle_fal, get, step
- [ ] info() → {name, inputs:{p:w}, outputs:{p:w}, clock}
- [ ] proc_ris(dict) → Inputs setzen, 1 Takt mit führender steigender Flanke
- [ ] cycle_ris(n) → n weitere Takte; _fal-Varianten analog
- [ ] get() → dict aller Outputs
- [ ] step(n, {in: np.array}) → {out: np.array}, Taktschleife in C++
- [ ] --trace: m.trace_open("x.fst") / m.trace_close()

## Doku
- [ ] README.md: Installation, Voraussetzungen, Quickstart (counter.v), API, Completion

## Qualität
- [ ] pytest: Parser gegen Verilator-JSON als Orakel
- [ ] Integrationstest: counter.v bauen, importieren, zählen
- [ ] Tests ohne Verilator → skip
- [ ] kein Code aus dspsim (AGPL)

## Repo & Packaging (festgelegt)
- Lizenz: MIT
- src-Layout: src/dlv/{cli,parser,verilator,build,completion}.py, src/dlv/templates/binding.cpp.j2,
  tests/, examples/counter.v, README.md, SPEC.md, LICENSE, pyproject.toml, .gitignore
- hatchling, reines Wheel (py3-none-any), Templates als Package-Data
- Deps: nanobind, jinja2, argcomplete, rich, numpy; Python ≥ 3.10
- Tooling: uv (venv, pytest, build, publish)
