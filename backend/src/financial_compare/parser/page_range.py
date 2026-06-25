"""Compare 前 parse 阶段的页码范围参数。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SidePageRange:
    start: int = 1
    end: int | None = None

    def clamp(self, page_count: int) -> tuple[int, int]:
        if page_count < 1:
            raise ValueError("PDF 页数为 0")
        start = max(1, min(self.start, page_count))
        end = self.end if self.end is not None else page_count
        end = max(start, min(end, page_count))
        return start, end


@dataclass(frozen=True)
class PageRange:
    a: SidePageRange
    b: SidePageRange
    specified: bool = True

    @classmethod
    def full(cls) -> PageRange:
        side = SidePageRange()
        return cls(a=side, b=side, specified=False)

    @classmethod
    def from_sides(
        cls,
        *,
        start_a: int = 1,
        end_a: int | None = None,
        start_b: int = 1,
        end_b: int | None = None,
    ) -> PageRange:
        for label, value in (("start_a", start_a), ("start_b", start_b)):
            if value < 1:
                raise ValueError(f"{label} 必须是正整数: {value}")
        for label, value in (("end_a", end_a), ("end_b", end_b)):
            if value is not None and value < 1:
                raise ValueError(f"{label} 必须是正整数: {value}")
        return cls(
            a=SidePageRange(start=start_a, end=end_a),
            b=SidePageRange(start=start_b, end=end_b),
            specified=True,
        )

    @classmethod
    def from_cli(
        cls,
        page_start: str | None,
        page_end: str | None,
    ) -> PageRange:
        if not page_start and not page_end:
            return cls.full()
        start_a, start_b = _parse_pair_ints(page_start, default_single=1)
        end_a, end_b = _parse_pair_ints(page_end, default_single=None)
        return cls(
            a=SidePageRange(start=start_a, end=end_a),
            b=SidePageRange(start=start_b, end=end_b),
            specified=True,
        )

    def for_side(self, side: str) -> SidePageRange:
        return self.a if side == "a" else self.b

    def swap_sides(self) -> PageRange:
        """交换 A/B 侧页码（与 normalize_docx_pdf_paths 的文件交换保持一致）。"""
        return PageRange(a=self.b, b=self.a, specified=self.specified)


def _parse_pair_ints(raw: str | None, *, default_single: int | None) -> tuple[int, int]:
    if raw is None or not str(raw).strip():
        if default_single is None:
            return default_single, default_single  # type: ignore[return-value]
        return default_single, default_single
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    if not parts:
        if default_single is None:
            return default_single, default_single  # type: ignore[return-value]
        return default_single, default_single
    if len(parts) == 1:
        value = _parse_positive_int(parts[0], label="页码")
        return value, value
    if len(parts) == 2:
        return (
            _parse_positive_int(parts[0], label="页码"),
            _parse_positive_int(parts[1], label="页码"),
        )
    raise ValueError(f"页码参数最多两个值（A,B），收到: {raw!r}")


def _parse_positive_int(text: str, *, label: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise ValueError(f"{label}必须是正整数: {text!r}") from exc
    if value < 1:
        raise ValueError(f"{label}必须是正整数: {value}")
    return value


def normalize_docx_pdf_paths(
    path_a: str | Path,
    path_b: str | Path,
) -> tuple[Path, Path, bool]:
    """混合类型时保证 A=docx、B=pdf；返回 (docx_path, pdf_path, swapped)。"""
    from pathlib import Path

    pa, pb = Path(path_a), Path(path_b)
    ext_a, ext_b = pa.suffix.lower(), pb.suffix.lower()
    if ext_a == ".docx" and ext_b == ".pdf":
        return pa, pb, False
    if ext_a == ".pdf" and ext_b == ".docx":
        return pb, pa, True
    raise ValueError(
        f"normalize_docx_pdf_paths 仅用于 docx+pdf 组合，收到: {pa.name}, {pb.name}"
    )
