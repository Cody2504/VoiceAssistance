#!/usr/bin/env python3
"""End-to-end test harness for the VoiceAssistance stack.

Exercises the whole product against a live deployment (laptop docker stack +
vast.ai GPU pod, fronted by the local nginx gateway and Cloudflare tunnels):

  Phase A  ingestion pipeline   upload multi-category media -> poll to ready -> KG backfill
  Phase B  feature endpoints    every video-service + index/KG endpoint
  Phase C  Video Agent/Chatbot  SSE chat stream, one prompt per agent tool (13), + scope/lang/budget/negative
  Phase D  teardown + report    pass/fail matrix -> E2E_RESULTS_<date>.md, optional cleanup

Topology (see scripts/e2e_config.example.json):
  - auth / chat / conversations  -> gateway   (http://localhost:8085)  [agent-service is laptop-only]
  - video upload + endpoints      -> video_base (http://127.0.0.1:11101 via SSH forward, dodges CF 504)

Usage:
  python scripts/e2e_test.py                      # all phases, config from scripts/e2e_config.json
  python scripts/e2e_test.py --phases A,B
  python scripts/e2e_test.py --phases C --reuse-results   # reuse video/index ids from a prior A run
  python scripts/e2e_test.py --keep               # don't delete uploaded videos/index at the end

Dependencies: httpx  (pip install httpx)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

try:
    import httpx
except ImportError:
    sys.exit("e2e_test: missing dependency 'httpx' — run: pip install httpx")

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "scripts" / ".e2e_state.json"  # carries ids between phase runs

# Vietnamese-specific characters, for the multilingual reflect check.
_VN_CHARS = set("ăâđêôơưĂÂĐÊÔƠƯàáảãạèéẻẽẹìíỉĩịòóỏõọùúủũụỳýỷỹỵ")


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------
@dataclass
class Config:
    gateway_base: str = "http://localhost:8085"
    video_base: str = "http://127.0.0.1:11101"
    video_public_base: str = "https://video.voiceassistant.uk"
    email: str = "e2e@voiceassistant.uk"
    password: str = "e2e-test-pass-123"
    media_root: str = "video"
    media: dict[str, int] = field(default_factory=lambda: {"cooking": 3, "basketball": 2, "nature": 2})
    ingest_timeout_s: int = 900
    poll_interval_s: int = 10
    pod_ssh: str = "ssh -p 31709 root@120.238.149.205"
    backfill_kg: bool = True

    @classmethod
    def load(cls, path: Path | None) -> "Config":
        data: dict[str, Any] = {}
        if path and path.exists():
            data = json.loads(path.read_text())
        data.pop("_comment", None)
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


# ---------------------------------------------------------------------------
# result recording
# ---------------------------------------------------------------------------
@dataclass
class Result:
    phase: str
    name: str
    ok: bool
    detail: str = ""


class Recorder:
    def __init__(self) -> None:
        self.results: list[Result] = []

    def record(self, phase: str, name: str, ok: bool, detail: str = "") -> bool:
        self.results.append(Result(phase, name, ok, detail))
        mark = "\033[32mPASS\033[0m" if ok else "\033[31mFAIL\033[0m"
        line = f"  [{mark}] {phase} · {name}"
        if detail:
            line += f"  — {detail}"
        print(line, flush=True)
        return ok

    def section(self, title: str) -> None:
        print(f"\n\033[1m=== {title} ===\033[0m", flush=True)

    def summary(self) -> tuple[int, int]:
        passed = sum(1 for r in self.results if r.ok)
        return passed, len(self.results)

    def write_markdown(self, path: Path) -> None:
        passed, total = self.summary()
        lines = [
            f"# E2E Results — {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
            "",
            f"**{passed}/{total} checks passed.**",
            "",
            "| Phase | Check | Result | Detail |",
            "|---|---|---|---|",
        ]
        for r in self.results:
            detail = r.detail.replace("|", "\\|").replace("\n", " ")[:200]
            lines.append(f"| {r.phase} | {r.name} | {'✅' if r.ok else '❌'} | {detail} |")
        path.write_text("\n".join(lines) + "\n")
        print(f"\nWrote {path}")


# ---------------------------------------------------------------------------
# HTTP client wrapper
# ---------------------------------------------------------------------------
class Api:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.token: str | None = None
        self.client = httpx.Client(timeout=httpx.Timeout(60.0, read=120.0))

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def request(self, method: str, base: str, path: str, **kw) -> httpx.Response:
        kw.setdefault("headers", {}).update(self._headers())
        return self.client.request(method, base + path, **kw)

    # convenience
    def gw(self, method: str, path: str, **kw) -> httpx.Response:
        return self.request(method, self.cfg.gateway_base, path, **kw)

    def vid(self, method: str, path: str, **kw) -> httpx.Response:
        return self.request(method, self.cfg.video_base, path, **kw)

    @staticmethod
    def data(resp: httpx.Response) -> Any:
        """Unwrap the {success, data, message} envelope; raise on failure."""
        resp.raise_for_status()
        body = resp.json()
        if isinstance(body, dict) and "data" in body:
            if body.get("success") is False:
                raise RuntimeError(f"api error: {body.get('message')}")
            return body["data"]
        return body

    # ---- auth ----
    def login_or_register(self) -> str:
        r = self.gw("POST", "/api/v1/auth/login",
                    json={"email": self.cfg.email, "password": self.cfg.password})
        if r.status_code == 401:
            r = self.gw("POST", "/api/v1/auth/register",
                        json={"email": self.cfg.email, "password": self.cfg.password})
        d = self.data(r)
        self.token = d["tokens"]["access_token"]
        return self.token

    # ---- SSE chat ----
    def chat_stream(self, message: str, *, conversation_id: str | None = None,
                    video_id: str | None = None, video_ids: list[str] | None = None,
                    index_id: str | None = None) -> Iterator[tuple[str, dict]]:
        """Yield (event_name, data_dict) tuples from the agent SSE stream."""
        payload = {
            "conversation_id": conversation_id,
            "video_id": video_id,
            "video_ids": video_ids,
            "index_id": index_id,
            "message": message,
        }
        with self.client.stream("POST", self.cfg.gateway_base + "/api/v1/chat/stream",
                                json=payload, headers=self._headers(),
                                timeout=httpx.Timeout(60.0, read=180.0)) as r:
            r.raise_for_status()
            event = None
            for raw in r.iter_lines():
                line = raw.decode() if isinstance(raw, bytes) else raw
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    body = line[5:].strip()
                    try:
                        data = json.loads(body)
                    except json.JSONDecodeError:
                        data = {"raw": body}
                    if event:
                        yield event, data
                elif line == "":
                    event = None


@dataclass
class ChatRun:
    conversation_id: str | None = None
    message_id: str | None = None
    tools_fired: list[str] = field(default_factory=list)
    tool_results: list = field(default_factory=list)
    final_text: str = ""
    events: list[str] = field(default_factory=list)
    error: str | None = None

    def tool_succeeded(self) -> bool:
        """True if at least one tool returned a non-error result."""
        for res in self.tool_results:
            if isinstance(res, dict):
                if res.get("error") or res.get("status") == "error" or "detail" in res:
                    continue
                return True
            elif res:
                return True
        return False


_ERR_PHRASES = ("issue connecting", "connection error", "unable to access", "unable to retrieve",
                "couldn't", "could not", "gặp lỗi", "không thể")


def run_chat(api: Api, message: str, **scope) -> ChatRun:
    run = ChatRun()
    try:
        for event, data in api.chat_stream(message, **scope):
            run.events.append(event)
            if event == "tool_call":
                run.tools_fired.append(data.get("tool", "?"))
            elif event == "tool_result":
                run.tool_results.append(data.get("result"))
            elif event == "message":
                run.final_text += data.get("delta", "")
            elif event == "end":
                run.conversation_id = data.get("conversation_id")
                run.message_id = data.get("message_id")
    except Exception as e:  # noqa: BLE001
        run.error = f"{type(e).__name__}: {e}"
    return run


# ---------------------------------------------------------------------------
# state shared between phases
# ---------------------------------------------------------------------------
def load_state() -> dict:
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def pick_media(cfg: Config) -> list[Path]:
    root = ROOT / cfg.media_root
    chosen: list[Path] = []
    for category, n in cfg.media.items():
        cat_dir = root / category
        if not cat_dir.is_dir():
            print(f"  (warning) media category dir missing: {cat_dir}")
            continue
        clips = sorted(cat_dir.glob("*.mp4"))[:n]
        chosen.extend(clips)
    return chosen


# ---------------------------------------------------------------------------
# Phase A — ingestion pipeline
# ---------------------------------------------------------------------------
def phase_a(api: Api, cfg: Config, rec: Recorder, state: dict) -> None:
    rec.section("Phase A — ingestion pipeline")

    # 1. auth
    try:
        api.login_or_register()
        rec.record("A", "auth login/register", True, f"token … {api.token[-6:]}")
    except Exception as e:  # noqa: BLE001
        rec.record("A", "auth login/register", False, str(e))
        return

    # 2. create index
    try:
        idx = api.data(api.vid("POST", "/api/v1/indexes",
                               json={"title": "e2e", "description": "e2e run", "language": "auto"}))
        index_id = idx["id"]
        state["index_id"] = index_id
        rec.record("A", "create index", True, index_id)
    except Exception as e:  # noqa: BLE001
        rec.record("A", "create index", False, str(e))
        index_id = None

    # 3. upload media
    media = pick_media(cfg)
    if not media:
        rec.record("A", "select media", False, "no media files found")
        return
    rec.record("A", "select media", True, f"{len(media)} files: " + ", ".join(p.parent.name + '/' + p.name for p in media))

    video_ids: list[str] = []
    for p in media:
        try:
            with p.open("rb") as fh:
                r = api.vid("POST", "/api/v1/videos",
                            files={"file": (p.name, fh, "video/mp4")},
                            timeout=httpx.Timeout(60.0, read=300.0))
            d = api.data(r)
            video_ids.append(d["id"])
            # endpoint declares 202 but returns a JSONResponse (default 200), so accept either
            ok = r.status_code in (200, 202) and d["status"] == "queued"
            rec.record("A", f"upload {p.parent.name}/{p.name}", ok, f"id={d['id']} status={d['status']}")
        except Exception as e:  # noqa: BLE001
            rec.record("A", f"upload {p.parent.name}/{p.name}", False, str(e))
    state["video_ids"] = video_ids

    # 4. add to index
    if index_id:
        for vid in video_ids:
            try:
                api.data(api.vid("POST", f"/api/v1/indexes/{index_id}/videos", json={"video_id": vid}))
            except Exception as e:  # noqa: BLE001
                rec.record("A", f"add {vid[:8]} to index", False, str(e))
        rec.record("A", "add videos to index", True, f"{len(video_ids)} added")

    # 5. poll to ready (serial; WORKER_COUNT=1)
    ready: list[str] = []
    deadline = time.time() + cfg.ingest_timeout_s * max(1, len(video_ids))
    pending = set(video_ids)
    t0 = time.time()
    while pending and time.time() < deadline:
        for vid in list(pending):
            try:
                v = api.data(api.vid("GET", f"/api/v1/videos/{vid}"))
            except Exception:  # noqa: BLE001
                continue
            if v["status"] == "ready":
                pending.discard(vid)
                ready.append(vid)
                # 6. metadata assertions
                meta_ok = bool(v.get("duration_s")) and bool(v.get("shot_count")) and bool(v.get("global_summary"))
                rec.record("A", f"ingest {vid[:8]}", True,
                           f"{int(time.time()-t0)}s dur={v.get('duration_s')} shots={v.get('shot_count')} mod={v.get('modality')}")
                rec.record("A", f"metadata {vid[:8]}", meta_ok,
                           "" if meta_ok else f"missing: dur={v.get('duration_s')} shots={v.get('shot_count')} summary={bool(v.get('global_summary'))}")
            elif v["status"] == "error":
                pending.discard(vid)
                rec.record("A", f"ingest {vid[:8]}", False, f"status=error: {v.get('error')}")
        if pending:
            time.sleep(cfg.poll_interval_s)
    for vid in pending:
        rec.record("A", f"ingest {vid[:8]}", False, "timeout waiting for ready")

    state["ready_video_ids"] = ready
    save_state(state)

    # 7. KG backfill (needs pod SSH; populates jockey_entities for the index)
    if cfg.backfill_kg and index_id and ready:
        # `main` package lives in backend/video-service; cm_shared lives in backend (PYTHONPATH).
        # interpreter differs by pod image: generic-Ubuntu -> system /usr/bin/python3 (PEP-668),
        # vast pytorch image -> /venv/main. Pick whichever can import torch.
        cmd = (f"{cfg.pod_ssh} 'cd /workspace/VoiceAssistance/backend/video-service && "
               f"PYTHONPATH=/workspace/VoiceAssistance/backend "
               f"$( for p in /usr/bin/python3 /venv/main/bin/python; do "
               f'"$p" -c "import torch" >/dev/null 2>&1 && echo "$p" && break; done ) '
               f"-m main.scripts.backfill_kg --index {index_id}'")
        rc = os.system(cmd)
        rec.record("A", "KG backfill", rc == 0, f"exit={rc} (cmd: backfill_kg --index {index_id})")


# ---------------------------------------------------------------------------
# Phase B — feature endpoint matrix
# ---------------------------------------------------------------------------
def _check(rec: Recorder, name: str, fn, *expect_keys: str) -> Any:
    try:
        d = fn()
        if expect_keys:
            missing = [k for k in expect_keys if isinstance(d, dict) and k not in d]
            rec.record("B", name, not missing, "" if not missing else f"missing keys {missing}")
        else:
            rec.record("B", name, True, "")
        return d
    except Exception as e:  # noqa: BLE001
        rec.record("B", name, False, str(e))
        return None


def phase_b(api: Api, cfg: Config, rec: Recorder, state: dict) -> None:
    rec.section("Phase B — feature endpoint matrix")
    if not api.token:
        api.login_or_register()
    ready = state.get("ready_video_ids") or state.get("video_ids") or []
    index_id = state.get("index_id")
    if not ready:
        rec.record("B", "preconditions", False, "no ready videos in state — run Phase A first")
        return
    vid = ready[0]

    _check(rec, "corpus search", lambda: api.data(api.vid("POST", "/api/v1/videos/search",
           json={"query": "person preparing food", "top_n": 5, "group_by": "video"})), "shots")
    _check(rec, "single-video search", lambda: api.data(api.vid("POST", f"/api/v1/videos/{vid}/search",
           json={"query": "main activity"})), "shots")
    _check(rec, "ground", lambda: api.data(api.vid("POST", f"/api/v1/videos/{vid}/ground",
           json={"query": "the key action happening"})), "moments")
    _check(rec, "highlights", lambda: api.data(api.vid("GET", f"/api/v1/videos/{vid}/highlights?top_k=5")), "moments")
    _check(rec, "segments", lambda: api.data(api.vid("GET", f"/api/v1/videos/{vid}/segments")), "segments")
    _check(rec, "custom segment", lambda: api.data(api.vid("POST", f"/api/v1/videos/{vid}/segment",
           json={"definitions": [{"id": "d1", "description": "moments where a person is speaking"}]})), "tracks")
    _check(rec, "sounds", lambda: api.data(api.vid("GET", f"/api/v1/videos/{vid}/sounds")), "shots")
    _check(rec, "moderate", lambda: api.data(api.vid("GET", f"/api/v1/videos/{vid}/moderate?threshold=0.5")), "summary")
    _check(rec, "similar", lambda: api.data(api.vid("GET", f"/api/v1/videos/{vid}/similar?top_k=5")), "results")
    _check(rec, "qa", lambda: api.data(api.vid("POST", f"/api/v1/videos/{vid}/qa",
           json={"question": "What is this video about?"})), "answer")
    _check(rec, "edit", lambda: api.data(api.vid("POST", f"/api/v1/videos/{vid}/edit",
           json={"clips": [{"t_start": 0.0, "t_end": 2.0}]})), "url")

    # stream + thumb presigned urls actually resolve
    def _presigned_resolves(path: str) -> bool:
        d = api.data(api.vid("GET", path))
        url = d["url"]
        head = httpx.get(url, timeout=30.0)
        return head.status_code in (200, 206)
    _check(rec, "stream url resolves", lambda: _presigned_resolves(f"/api/v1/videos/{vid}/stream"))
    _check(rec, "thumb url resolves", lambda: _presigned_resolves(f"/api/v1/videos/{vid}/thumb/0"))

    # index + KG endpoints
    if index_id:
        _check(rec, "index search", lambda: api.data(api.vid("POST", f"/api/v1/indexes/{index_id}/search",
               json={"query": "main topic", "video_ids": [], "top_n": 5, "group_by": "video"})), "shots")
        concepts = _check(rec, "concept search", lambda: api.data(api.vid("POST",
                   f"/api/v1/indexes/{index_id}/concepts/search",
                   json={"query": "main concept", "top_k": 5})), "concepts")
        eid = None
        if isinstance(concepts, dict) and concepts.get("concepts"):
            eid = concepts["concepts"][0]["entity_id"]
        if eid:
            _check(rec, "entity mentions", lambda: api.data(api.vid("GET",
                   f"/api/v1/indexes/{index_id}/entities/{eid}/mentions?limit=20")), "mentions")
            _check(rec, "entity relations", lambda: api.data(api.vid("GET",
                   f"/api/v1/indexes/{index_id}/entities/{eid}/related?direction=both&top_k=10")), "related")
        else:
            rec.record("B", "entity mentions/relations", False, "no entities found (KG backfill may be empty)")


# ---------------------------------------------------------------------------
# Phase C — Video Agent / Chatbot
# ---------------------------------------------------------------------------
def phase_c(api: Api, cfg: Config, rec: Recorder, state: dict) -> None:
    rec.section("Phase C — Video Agent / Chatbot (SSE)")
    if not api.token:
        api.login_or_register()
    ready = state.get("ready_video_ids") or state.get("video_ids") or []
    index_id = state.get("index_id")
    if not ready:
        rec.record("C", "preconditions", False, "no ready videos in state — run Phase A first")
        return
    vid = ready[0]

    # (scenario, kwargs, expected_tool)
    scenarios: list[tuple[str, dict, str]] = [
        ("find videos about preparing food",                  {},                       "search_corpus"),
        ("which video covers the main activity?",             {"index_id": index_id},   "search_index"),
        ("find the part about the main action in this video", {"video_id": vid},        "search_video_local"),
        ("summarize this video",                              {"video_id": vid},        "ask_video_local"),
        ("find the moment where the key action happens",      {"video_id": vid},        "ground_video"),
        ("show me the top 5 highlights",                      {"video_id": vid},        "get_highlights"),
        ("find videos like this one",                         {"video_id": vid},        "find_similar"),
        ("is there anything inappropriate in this video?",    {"video_id": vid},        "moderate_video"),
        ("when is there music or notable sound?",             {"video_id": vid},        "find_sounds"),
        ("make a clip from 0:00 to 0:03",                     {"video_id": vid},        "combine_clips"),
        ("what concepts are covered in this collection?",     {"index_id": index_id},   "find_index_concepts"),
        ("where is the main concept mentioned?",              {"index_id": index_id},   "find_concept_mentions"),
        ("what is related to the main concept?",              {"index_id": index_id},   "find_concept_relations"),
    ]
    tools_seen: set[str] = set()
    first_convo: str | None = None
    for msg, scope, expected_tool in scenarios:
        if "index_id" in scope and not index_id:
            rec.record("C", f"tool:{expected_tool}", False, "no index_id in state")
            continue
        run = run_chat(api, msg, **scope)
        tools_seen.update(run.tools_fired)
        first_convo = first_convo or run.conversation_id
        answer_errored = any(p in run.final_text.lower() for p in _ERR_PHRASES)
        ok = (run.error is None and "end" in run.events and bool(run.final_text.strip())
              and expected_tool in run.tools_fired and run.tool_succeeded() and not answer_errored)
        detail = (run.error or
                  f"tools={run.tools_fired} tool_ok={run.tool_succeeded()} answer='{run.final_text.strip()[:60]}'")
        rec.record("C", f"tool:{expected_tool}", ok, detail)

    # coverage: every tool fired at least once across scenarios
    expected_tools = {s[2] for s in scenarios}
    missing = expected_tools - tools_seen
    rec.record("C", "tool coverage (13)", not missing, "" if not missing else f"never fired: {sorted(missing)}")

    # multi-turn (history node)
    if first_convo:
        run = run_chat(api, "and what about the first part specifically?",
                       conversation_id=first_convo, video_id=vid)
        rec.record("C", "multi-turn follow-up", run.error is None and bool(run.final_text.strip()),
                   run.error or f"answer='{run.final_text.strip()[:60]}'")

    # multilingual (Vietnamese in -> Vietnamese out)
    run = run_chat(api, "Tóm tắt video này bằng tiếng Việt", video_id=vid)
    is_vn = any(c in _VN_CHARS for c in run.final_text)
    rec.record("C", "multilingual VN", run.error is None and is_vn,
               run.error or f"vn_chars={is_vn} answer='{run.final_text.strip()[:60]}'")

    # router budget (vague multi-step prompt must still terminate within max steps)
    run = run_chat(api, "tell me everything interesting across all of this", index_id=index_id, video_id=vid)
    rec.record("C", "router budget terminates", run.error is None and "end" in run.events,
               run.error or f"tool_calls={len(run.tools_fired)}")

    # negative: bad conversation_id -> 404
    try:
        list(api.chat_stream("hello", conversation_id="00000000-0000-0000-0000-000000000000"))
        rec.record("C", "negative bad conversation_id", False, "expected 404")
    except httpx.HTTPStatusError as e:
        rec.record("C", "negative bad conversation_id", e.response.status_code == 404,
                   f"status={e.response.status_code}")
    except Exception as e:  # noqa: BLE001
        rec.record("C", "negative bad conversation_id", False, str(e))

    # conversation persisted
    if first_convo:
        try:
            convo = api.data(api.gw("GET", f"/api/v1/conversations/{first_convo}"))
            msgs = convo.get("messages", [])
            roles = {m["role"] for m in msgs}
            rec.record("C", "conversation persisted", {"user", "assistant"} <= roles,
                       f"{len(msgs)} messages, roles={roles}")
        except Exception as e:  # noqa: BLE001
            rec.record("C", "conversation persisted", False, str(e))


# ---------------------------------------------------------------------------
# Phase D — teardown + report
# ---------------------------------------------------------------------------
def phase_d(api: Api, cfg: Config, rec: Recorder, state: dict, keep: bool) -> None:
    rec.section("Phase D — teardown + report")
    if keep:
        rec.record("D", "cleanup skipped (--keep)", True, "")
        return
    if not api.token:
        api.login_or_register()
    for vid in state.get("video_ids", []):
        try:
            r = api.vid("DELETE", f"/api/v1/videos/{vid}")
            rec.record("D", f"delete video {vid[:8]}", r.status_code == 204, f"status={r.status_code}")
        except Exception as e:  # noqa: BLE001
            rec.record("D", f"delete video {vid[:8]}", False, str(e))
    if state.get("index_id"):
        try:
            r = api.vid("DELETE", f"/api/v1/indexes/{state['index_id']}")
            rec.record("D", "delete index", r.status_code == 204, f"status={r.status_code}")
        except Exception as e:  # noqa: BLE001
            rec.record("D", "delete index", False, str(e))
    if STATE_FILE.exists():
        STATE_FILE.unlink()


# ---------------------------------------------------------------------------
# preconditions
# ---------------------------------------------------------------------------
def check_preconditions(api: Api, cfg: Config, rec: Recorder, phases: set[str]) -> bool:
    rec.section("Preconditions")
    ok = True
    try:
        r = httpx.get(cfg.gateway_base + "/health", timeout=10.0)
        ok &= rec.record("pre", "gateway /health", r.status_code == 200, f"status={r.status_code}")
    except Exception as e:  # noqa: BLE001
        ok &= rec.record("pre", "gateway /health", False, str(e))
    try:
        r = httpx.get(cfg.video_base + "/health", timeout=10.0)
        ok &= rec.record("pre", "video-service /health (tunnel)", r.status_code == 200, f"status={r.status_code}")
    except Exception as e:  # noqa: BLE001
        ok &= rec.record("pre", "video-service /health (tunnel)", False,
                         f"{e} — is the SSH forward to {cfg.video_base} up?")
    if "A" in phases:
        media = pick_media(cfg)
        ok &= rec.record("pre", "test media present", bool(media), f"{len(media)} files under {cfg.media_root}/")
    return ok


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="VoiceAssistance E2E harness")
    ap.add_argument("--config", default=str(ROOT / "scripts" / "e2e_config.json"))
    ap.add_argument("--phases", default="A,B,C,D")
    ap.add_argument("--gateway")
    ap.add_argument("--video-base")
    ap.add_argument("--media-root")
    ap.add_argument("--keep", action="store_true", help="don't delete uploaded videos/index")
    ap.add_argument("--no-precheck", action="store_true")
    args = ap.parse_args()

    cfg = Config.load(Path(args.config))
    if args.gateway:
        cfg.gateway_base = args.gateway
    if args.video_base:
        cfg.video_base = args.video_base
    if args.media_root:
        cfg.media_root = args.media_root

    phases = {p.strip().upper() for p in args.phases.split(",") if p.strip()}
    rec = Recorder()
    api = Api(cfg)
    state = load_state()

    print(f"gateway={cfg.gateway_base}  video_base={cfg.video_base}  phases={sorted(phases)}")

    if not args.no_precheck:
        if not check_preconditions(api, cfg, rec, phases):
            print("\n\033[31mPreconditions failed — aborting.\033[0m Use --no-precheck to force.")
            rec.write_markdown(ROOT / f"E2E_RESULTS_{datetime.now().strftime('%Y-%m-%d')}.md")
            return 2

    if "A" in phases:
        phase_a(api, cfg, rec, state)
    if "B" in phases:
        phase_b(api, cfg, rec, state)
    if "C" in phases:
        phase_c(api, cfg, rec, state)
    if "D" in phases:
        phase_d(api, cfg, rec, state, keep=args.keep)

    passed, total = rec.summary()
    rec.write_markdown(ROOT / f"E2E_RESULTS_{datetime.now().strftime('%Y-%m-%d')}.md")
    print(f"\n\033[1m{passed}/{total} checks passed.\033[0m")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
