"""`dlv init`: install argcomplete-based shell completion for bash, zsh and fish."""

import os
from pathlib import Path

from argcomplete import shellcode

from .verilator import DlvError

_TARGETS = {
    "bash": Path("~/.local/share/bash-completion/completions/dlv"),
    "zsh": Path("~/.local/share/zsh/site-functions/_dlv"),
    "fish": Path("~/.config/fish/completions/dlv.fish"),
}
_HINTS = {
    "bash": "Restart your shell (bash-completion loads it on demand).",
    "zsh": "Make sure ~/.local/share/zsh/site-functions is in your fpath before compinit, then restart zsh.",
    "fish": "Restart fish.",
}


def init(shell: str | None = None) -> Path:
    from .build import console

    shell = shell or Path(os.environ.get("SHELL", "")).name
    if shell not in _TARGETS:
        raise DlvError("cannot detect shell from $SHELL; use --shell bash|zsh|fish")
    path = _TARGETS[shell].expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(shellcode(["dlv"], shell=shell))
    console.print(f"[green]✓[/green] Installed {shell} completion: {path}", soft_wrap=True)
    console.print(_HINTS[shell])
    return path
