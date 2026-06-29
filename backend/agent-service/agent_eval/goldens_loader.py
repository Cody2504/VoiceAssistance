"""Golden dataset model + YAML loader."""
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ExpectedTool:
    name: str
    args: dict = field(default_factory=dict)


@dataclass
class Golden:
    id: str
    query: str
    expected_tools: list[ExpectedTool]
    video_id: str | None = None
    video_ids: list[str] | None = None
    index_id: str | None = None
    image: str | None = None
    fake_outputs: dict = field(default_factory=dict)
    reference_answer: str | None = None

    @property
    def primary_tool(self) -> str:
        return self.expected_tools[0].name if self.expected_tools else "(none)"


def _parse_case(raw: dict) -> Golden:
    ctx = raw.get("context") or {}
    tools = [ExpectedTool(name=t["name"], args=t.get("args") or {}) for t in (raw.get("expected_tools") or [])]
    return Golden(
        id=raw["id"],
        query=raw["query"],
        expected_tools=tools,
        video_id=ctx.get("video_id"),
        video_ids=ctx.get("video_ids"),
        index_id=ctx.get("index_id"),
        image=ctx.get("image"),
        fake_outputs=raw.get("fake_outputs") or {},
        reference_answer=raw.get("reference_answer"),
    )


def load_goldens(directory, tools: set[str] | None = None) -> list[Golden]:
    directory = Path(directory)
    out: list[Golden] = []
    for path in sorted(directory.glob("*.yaml")):
        docs = yaml.safe_load(path.read_text()) or []
        for raw in docs:
            g = _parse_case(raw)
            if tools is None or g.primary_tool in tools:
                out.append(g)
    return out
