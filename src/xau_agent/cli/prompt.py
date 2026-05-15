"""Approval prompt. Returns user decision for the current proposal."""
from __future__ import annotations

from typing import Literal

from rich.prompt import Prompt

Decision = Literal["YES", "NO", "SKIP"]


def ask_approval(default: Decision = "NO") -> Decision:
    """Block until user types y/n/s. Default on Enter = NO."""
    raw = Prompt.ask(
        "[bold]Approve order?[/bold]  [green]y[/green]es / [red]n[/red]o / [yellow]s[/yellow]kip",
        choices=["y", "n", "s"],
        default={"YES": "y", "NO": "n", "SKIP": "s"}[default],
        show_choices=False,
    )
    return {"y": "YES", "n": "NO", "s": "SKIP"}[raw]
