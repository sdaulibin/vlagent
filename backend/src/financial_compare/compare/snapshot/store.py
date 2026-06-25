"""任务目录读写：meta / sources / phase*.events.jsonl / diffs.jsonl / checkpoint。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from financial_compare.compare.models.node import RemainderPool
from financial_compare.compare.snapshot.remainder_serde import remainder_pool_from_dict, remainder_pool_to_dict
from financial_compare.document.types import StructuredDocument
from financial_compare.parser.io.serde import PARSED_VERSION

SCHEMA_VERSION = 2


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _format_coord(v: float) -> int | float:
    r = round(float(v), 2)
    return int(r) if r == int(r) else r


def _normalize_loc(loc: dict[str, Any] | None) -> dict[str, Any] | None:
    if loc is None:
        return None
    out = dict(loc)
    bbox = out.get("bbox")
    if isinstance(bbox, list) and len(bbox) >= 4:
        out["bbox"] = [_format_coord(b) for b in bbox[:4]]
    return out


def _compact_diff_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k not in ("loc_a", "loc_b")}


@dataclass(frozen=True)
class TitleStepKey:
    parent_path_a: str
    parent_path_b: str
    a_index: int
    b_index: int


@dataclass
class TaskSnapshotStore:
    task_dir: Path
    task_id: str
    _event_seq: int = 0
    _diff_seq: int = 0
    _written_diff_ids: set[str] = field(default_factory=set)
    title_index: dict[TitleStepKey, bool] = field(default_factory=dict)

    @classmethod
    def open(cls, tasks_root: Path, task_id: str, *, create: bool = True) -> TaskSnapshotStore:
        task_dir = tasks_root / task_id
        if create:
            task_dir.mkdir(parents=True, exist_ok=True)
        store = cls(task_dir=task_dir, task_id=task_id)
        store._load_sequences()
        return store

    @property
    def meta_path(self) -> Path:
        return self.task_dir / "meta.json"

    @property
    def sources_path(self) -> Path:
        return self.task_dir / "sources.json"

    def phase_events_path(self, phase: int) -> Path:
        return self.task_dir / f"phase{phase}.events.jsonl"

    @property
    def diffs_path(self) -> Path:
        return self.task_dir / "diffs.jsonl"

    def phase_checkpoint_path(self, phase: int) -> Path:
        return self.task_dir / f"phase{phase}.checkpoint.json"

    def read_meta(self) -> dict[str, Any] | None:
        if not self.meta_path.exists():
            return None
        return json.loads(self.meta_path.read_text(encoding="utf-8"))

    def write_meta(self, body: dict[str, Any]) -> None:
        body = dict(body)
        prev = self.read_meta() or {}
        body.setdefault("schema_version", SCHEMA_VERSION)
        body.setdefault("task_id", self.task_id)
        body.setdefault("created_at", prev.get("created_at") or _utc_now_iso())
        body["updated_at"] = _utc_now_iso()
        self.meta_path.write_text(
            json.dumps(body, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def init_sources(
        self,
        *,
        path_a: Path,
        path_b: Path,
        parsed_version: int = PARSED_VERSION,
        code_ref: str | None = None,
    ) -> dict[str, str]:
        sha_a = file_sha256(path_a)
        sha_b = file_sha256(path_b)
        body: dict[str, Any] = {
            "doc_a": {
                "path": str(path_a),
                "sha256": sha_a,
                "parsed_version": parsed_version,
            },
            "doc_b": {
                "path": str(path_b),
                "sha256": sha_b,
                "parsed_version": parsed_version,
            },
        }
        if code_ref:
            body["code_ref"] = code_ref
        self.sources_path.write_text(
            json.dumps(body, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {"a": sha_a, "b": sha_b}

    def validate_sources(self, path_a: Path, path_b: Path) -> None:
        if not self.sources_path.exists():
            return
        saved = json.loads(self.sources_path.read_text(encoding="utf-8"))
        for key, path in (("a", path_a), ("b", path_b)):
            side = saved.get(f"doc_{key}", {})
            expected = side.get("sha256")
            if expected and file_sha256(path) != expected:
                raise ValueError(f"sources.json doc_{key} sha256 与当前 parsed 不一致")
            expected_ver = side.get("parsed_version")
            if expected_ver is not None and int(expected_ver) != PARSED_VERSION:
                raise ValueError(
                    f"sources.json doc_{key} parsed_version={expected_ver!r} "
                    f"与当前 {PARSED_VERSION} 不一致；请重新导出 parsed.json"
                )
        from financial_compare.parser.io.serde import validate_parsed_json_file

        validate_parsed_json_file(path_a)
        validate_parsed_json_file(path_b)

    def append_event(self, *, op: str, phase: int, payload: dict[str, Any]) -> str:
        self._event_seq += 1
        event_id = f"evt-{self._event_seq:06d}"
        row = {
            "event_id": event_id,
            "op": op,
            "phase": phase,
            **payload,
        }
        with self.phase_events_path(phase).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return event_id

    def append_diff(
        self,
        *,
        phase: int,
        kind: str,
        scope: dict[str, str],
        loc_a: dict[str, Any] | None,
        loc_b: dict[str, Any] | None,
        payload: dict[str, Any],
    ) -> str:
        self._diff_seq += 1
        diff_id = f"d-{self._diff_seq:05d}"
        if diff_id in self._written_diff_ids:
            return diff_id
        row = {
            "diff_id": diff_id,
            "phase": phase,
            "kind": kind,
            "scope": scope,
            "loc_a": _normalize_loc(loc_a),
            "loc_b": _normalize_loc(loc_b),
            "payload": _compact_diff_payload(payload),
        }
        with self.diffs_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        self._written_diff_ids.add(diff_id)
        return diff_id

    def read_sources_sha(self) -> dict[str, str] | None:
        if not self.sources_path.exists():
            return None
        saved = json.loads(self.sources_path.read_text(encoding="utf-8"))
        return {
            "a": saved.get("doc_a", {}).get("sha256", ""),
            "b": saved.get("doc_b", {}).get("sha256", ""),
        }

    def write_phase_checkpoint(
        self,
        phase: int,
        *,
        pool: RemainderPool,
        last_event_id: str | None = None,
        sources_sha: dict[str, str] | None = None,
        resume: dict[str, Any] | None = None,
        stats: dict[str, Any] | None = None,
    ) -> None:
        body: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "phase": phase,
            "last_event_id": last_event_id or self.last_event_id() or "",
            "remainder_pool": remainder_pool_to_dict(pool.remainder_a, pool.remainder_b),
        }
        if sources_sha:
            body["sources_sha"] = sources_sha
        if resume:
            body["resume"] = resume
        stats_out = dict(stats or {})
        if self.diffs_path.exists():
            stats_out["diffs_count"] = sum(1 for _ in self.diffs_path.open(encoding="utf-8"))
        stats_out.setdefault("remainder_a", len(pool.remainder_a))
        stats_out.setdefault("remainder_b", len(pool.remainder_b))
        body["stats"] = stats_out
        path = self.phase_checkpoint_path(phase)
        path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def write_phase1_checkpoint(self, **kwargs: Any) -> None:
        self.write_phase_checkpoint(1, **kwargs)

    def load_phase_remainder_pool(
        self,
        phase: int,
        *,
        doc_a: StructuredDocument,
        doc_b: StructuredDocument,
    ) -> RemainderPool:
        path = self.phase_checkpoint_path(phase)
        if not path.exists():
            raise FileNotFoundError(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        saved_schema = int(data.get("schema_version", 1))
        if saved_schema != SCHEMA_VERSION:
            raise ValueError(
                f"{path.name} schema_version={saved_schema} 与当前 {SCHEMA_VERSION} 不一致；"
                f"请重新跑 compare 生成新 checkpoint"
            )
        pool_dict = data.get("remainder_pool", {})
        ra, rb = remainder_pool_from_dict(pool_dict, doc_a=doc_a, doc_b=doc_b)
        return RemainderPool(remainder_a=ra, remainder_b=rb)

    def load_phase1_remainder_pool(
        self,
        *,
        doc_a: StructuredDocument,
        doc_b: StructuredDocument,
    ) -> RemainderPool:
        return self.load_phase_remainder_pool(1, doc_a=doc_a, doc_b=doc_b)

    def phase_completed_in_events(self, phase: int) -> bool:
        for path in self._event_file_paths_for_phase(phase):
            with path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    if row.get("op") == "PHASE_COMPLETED" and int(row.get("phase", 0)) == phase:
                        return True
        return False

    def load_title_index_from_events(self) -> None:
        """从 phase1.events.jsonl 构建 TITLE_PAIRED 索引。"""
        self.title_index.clear()
        for path in self._event_file_paths_for_phase(1):
            with path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    if row.get("op") != "TITLE_PAIRED":
                        continue
                    key = TitleStepKey(
                        parent_path_a=str(row["parent_path_a"]),
                        parent_path_b=str(row["parent_path_b"]),
                        a_index=int(row["a_index"]),
                        b_index=int(row["b_index"]),
                    )
                    self.title_index[key] = bool(row.get("is_match", False))
                    self._bump_event_seq_from_row(row)

    def lookup_title_match(
        self,
        *,
        parent_path_a: str,
        parent_path_b: str,
        a_index: int,
        b_index: int,
    ) -> bool | None:
        key = TitleStepKey(parent_path_a, parent_path_b, a_index, b_index)
        if key not in self.title_index:
            return None
        return self.title_index[key]

    def record_title_paired(
        self,
        *,
        parent_path_a: str,
        parent_path_b: str,
        a_index: int,
        b_index: int,
        is_match: bool,
    ) -> None:
        key = TitleStepKey(parent_path_a, parent_path_b, a_index, b_index)
        self.title_index[key] = is_match

    def last_event_id(self) -> str | None:
        if self._event_seq <= 0:
            return None
        return f"evt-{self._event_seq:06d}"

    def _event_file_paths_for_phase(self, phase: int) -> list[Path]:
        phase_path = self.phase_events_path(phase)
        if phase_path.exists():
            return [phase_path]
        return []

    def _all_event_file_paths(self) -> list[Path]:
        return sorted(self.task_dir.glob("phase*.events.jsonl"))

    def _bump_event_seq_from_row(self, row: dict[str, Any]) -> None:
        eid = row.get("event_id", "")
        if not isinstance(eid, str) or not eid.startswith("evt-"):
            return
        try:
            n = int(eid.split("-", 1)[1])
        except ValueError:
            return
        self._event_seq = max(self._event_seq, n)

    def _load_sequences(self) -> None:
        for path in self._all_event_file_paths():
            with path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    self._bump_event_seq_from_row(json.loads(line))
        if self.diffs_path.exists():
            with self.diffs_path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    did = row.get("diff_id")
                    if isinstance(did, str):
                        self._written_diff_ids.add(did)
                        if did.startswith("d-"):
                            try:
                                self._diff_seq = max(self._diff_seq, int(did.split("-", 1)[1]))
                            except ValueError:
                                pass
