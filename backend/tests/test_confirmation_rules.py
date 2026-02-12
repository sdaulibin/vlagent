import sys
from pathlib import Path

# Add backend root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.confirmation_letter.service import (  # noqa: E402
    _parse_confirmation_no,
    _normalize_date,
    _normalize_phone,
    _normalize_postal_code,
    _check_format,
)


def test_confirmation_no_priority():
    text = """
    索引号：IDX-001
    编号：NO-123
    询证函编号：QZH-2024-888/1
    函证编号：HZ-2024-0009
    """
    assert _parse_confirmation_no(text) == "HZ-2024-0009"


def test_confirmation_no_strip_page_suffix():
    text = "询证函编号：QZH-2024-888/1"
    assert _parse_confirmation_no(text) == "QZH-2024-888"


def test_normalize_date():
    assert _normalize_date("截至2024年9月3日") == "2024-09-03"
    assert _normalize_date("2024/12/31") == "2024-12-31"
    assert _normalize_date("无效日期") == ""


def test_normalize_phone_and_postal():
    assert _normalize_phone("联系电话：138 0013 8000") == "13800138000"
    assert _normalize_phone("电话：0531-88886666") == "0531-88886666"
    assert _normalize_postal_code("邮编：250001") == "250001"
    assert _normalize_postal_code("邮编：ABC") == ""


def test_format_check_result():
    text = "银行询证函 回函地址 联系人 电话 邮编 截至2024年9月3日"
    result = _check_format(text)
    assert result["format_type"] in {"format_1", "format_2", "capital_verification"}
    assert "format_check_passed" in result
    assert "format_mismatches" in result
