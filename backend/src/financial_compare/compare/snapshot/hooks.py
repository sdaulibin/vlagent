"""快照钩子：默认 noop，FileSnapshotHooks 写入任务目录。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from financial_compare.compare.snapshot.store import TaskSnapshotStore


class SnapshotHooks(Protocol):
    def on_task_started(self, *, sources_sha: dict[str, str]) -> None: ...

    def on_phase_started(self, *, phase: int) -> None: ...

    def on_title_paired(
        self,
        *,
        path_a: str,
        path_b: str,
        is_match: bool,
        parent_path_a: str,
        parent_path_b: str,
        a_index: int,
        b_index: int,
        reason: str | None = None,
    ) -> None: ...

    def on_title_tail(
        self,
        *,
        side: str,
        parent_path_a: str,
        parent_path_b: str,
        a_index: int | None,
        b_index: int | None,
        path: str,
        reason: str,
    ) -> None: ...

    def on_text_diff(
        self,
        *,
        scope_path_a: str,
        scope_path_b: str,
        payload: dict[str, Any],
        phase: int = 1,
        kind: str = "text",
    ) -> str | None: ...

    def on_table_diffs(
        self,
        *,
        scope_path_a: str,
        scope_path_b: str,
        payloads: list[dict[str, Any]],
        phase: int = 1,
        kind: str = "table",
    ) -> list[str]: ...

    def on_phase_completed(self, *, phase: int, checkpoint_name: str) -> None: ...


@dataclass
class NoopSnapshotHooks:
    def on_task_started(self, *, sources_sha: dict[str, str]) -> None:
        return None

    def on_phase_started(self, *, phase: int) -> None:
        return None

    def on_title_paired(
        self,
        *,
        path_a: str,
        path_b: str,
        is_match: bool,
        parent_path_a: str,
        parent_path_b: str,
        a_index: int,
        b_index: int,
        reason: str | None = None,
    ) -> None:
        return None

    def on_title_tail(
        self,
        *,
        side: str,
        parent_path_a: str,
        parent_path_b: str,
        a_index: int | None,
        b_index: int | None,
        path: str,
        reason: str,
    ) -> None:
        return None

    def on_text_diff(
        self,
        *,
        scope_path_a: str,
        scope_path_b: str,
        payload: dict[str, Any],
        phase: int = 1,
        kind: str = "text",
    ) -> str | None:
        return None

    def on_table_diffs(
        self,
        *,
        scope_path_a: str,
        scope_path_b: str,
        payloads: list[dict[str, Any]],
        phase: int = 1,
        kind: str = "table",
    ) -> list[str]:
        return []

    def on_phase_completed(self, *, phase: int, checkpoint_name: str) -> None:
        return None


@dataclass
class FileSnapshotHooks:
    store: TaskSnapshotStore

    def on_task_started(self, *, sources_sha: dict[str, str]) -> None:
        self.store.append_event(
            op="TASK_STARTED",
            phase=1,
            payload={"sources_sha": sources_sha},
        )

    def on_phase_started(self, *, phase: int) -> None:
        self.store.append_event(
            op="PHASE_STARTED",
            phase=phase,
            payload={},
        )

    def on_title_paired(
        self,
        *,
        path_a: str,
        path_b: str,
        is_match: bool,
        parent_path_a: str,
        parent_path_b: str,
        a_index: int,
        b_index: int,
        reason: str | None = None,
    ) -> None:
        body: dict[str, Any] = {
            "path_a": path_a,
            "path_b": path_b,
            "is_match": is_match,
            "parent_path_a": parent_path_a,
            "parent_path_b": parent_path_b,
            "a_index": a_index,
            "b_index": b_index,
        }
        if reason:
            body["reason"] = reason
        self.store.append_event(op="TITLE_PAIRED", phase=1, payload=body)
        self.store.record_title_paired(
            parent_path_a=parent_path_a,
            parent_path_b=parent_path_b,
            a_index=a_index,
            b_index=b_index,
            is_match=is_match,
        )

    def on_title_tail(
        self,
        *,
        side: str,
        parent_path_a: str,
        parent_path_b: str,
        a_index: int | None,
        b_index: int | None,
        path: str,
        reason: str,
    ) -> None:
        self.store.append_event(
            op="TITLE_TAIL",
            phase=1,
            payload={
                "side": side,
                "parent_path_a": parent_path_a,
                "parent_path_b": parent_path_b,
                "a_index": a_index,
                "b_index": b_index,
                "path": path,
                "reason": reason,
            },
        )

    def on_text_diff(
        self,
        *,
        scope_path_a: str,
        scope_path_b: str,
        payload: dict[str, Any],
        phase: int = 1,
        kind: str = "text",
    ) -> str | None:
        diff_id = self.store.append_diff(
            phase=phase,
            kind=kind,
            scope={"path_a": scope_path_a, "path_b": scope_path_b},
            loc_a=payload.get("loc_a"),
            loc_b=payload.get("loc_b"),
            payload=payload,
        )
        return diff_id

    def on_table_diffs(
        self,
        *,
        scope_path_a: str,
        scope_path_b: str,
        payloads: list[dict[str, Any]],
        phase: int = 1,
        kind: str = "table",
    ) -> list[str]:
        ids: list[str] = []
        scope = {"path_a": scope_path_a, "path_b": scope_path_b}
        for item in payloads:
            diff_id = self.store.append_diff(
                phase=phase,
                kind=kind,
                scope=scope,
                loc_a=item.get("loc_a"),
                loc_b=item.get("loc_b"),
                payload=item,
            )
            ids.append(diff_id)
        return ids

    def on_phase_completed(self, *, phase: int, checkpoint_name: str) -> None:
        self.store.append_event(
            op="PHASE_COMPLETED",
            phase=phase,
            payload={"checkpoint": checkpoint_name},
        )
