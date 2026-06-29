"""Fake tool layer for deterministic, network-free eval runs."""
from contextlib import contextmanager
from typing import Any

import main.app.core.nodes.tool_executor as te_mod
from main.app.core.tools import TOOLS_BY_NAME as _REAL_TOOLS_BY_NAME


class FakeTool:
    """Minimal stand-in: tool_executor only ever calls `.ainvoke(args)`."""

    def __init__(self, name: str, output: Any):
        self.name = name
        self._output = output

    async def ainvoke(self, _args: dict) -> Any:
        return self._output


def build_fake_registry(fake_outputs: dict) -> dict:
    """One FakeTool per known tool name; canned output where the golden supplies
    it, else a harmless empty result so the graph still reaches reflect."""
    return {
        name: FakeTool(name, fake_outputs.get(name, {"shots": []}))
        for name in _REAL_TOOLS_BY_NAME
    }


@contextmanager
def inject_fake_tools(fake_outputs: dict):
    """Swap tool_executor's TOOLS_BY_NAME for fakes; routing is left untouched."""
    original = te_mod.TOOLS_BY_NAME
    te_mod.TOOLS_BY_NAME = build_fake_registry(fake_outputs)
    try:
        yield
    finally:
        te_mod.TOOLS_BY_NAME = original
