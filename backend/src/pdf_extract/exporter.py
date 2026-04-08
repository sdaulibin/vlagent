"""
数据导出模块
支持导出为 CSV 和 XLSX 格式
"""
import json
import tempfile
from typing import Any, Dict, List, Tuple

import pandas as pd


def export_csv(data: List[Dict[str, Any]]) -> str:
    """
    导出为 CSV 文件

    Args:
        data: 提取结果列表，每项包含 filename 和 data

    Returns:
        临时文件路径
    """
    rows = _prepare_rows(data)
    df = pd.DataFrame(rows)

    fd, path = tempfile.mkstemp(suffix=".csv")
    df.to_csv(path, index=False, encoding='utf-8-sig')
    return path


def export_xlsx(data: List[Dict[str, Any]]) -> str:
    """
    导出为 XLSX 文件

    Args:
        data: 提取结果列表，每项包含 filename 和 data

    Returns:
        临时文件路径
    """
    rows = _prepare_rows(data)
    df = pd.DataFrame(rows)

    fd, path = tempfile.mkstemp(suffix=".xlsx")
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='提取结果')

        worksheet = writer.sheets['提取结果']
        for idx, col in enumerate(df.columns):
            max_length = max(len(str(col)), df[col].astype(str).map(len).max())
            worksheet.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 50)

    return path


def _prepare_rows(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    将提取结果展开为适合导出的行列表
    """
    result = []
    for entry in data:
        filename = entry.get("filename", "")
        entry_data = entry.get("data", {})

        object_arrays = {}
        normal_data = {}

        for k, v in entry_data.items():
            if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                object_arrays[k] = v
            else:
                normal_data[k] = v

        flat_data = _flatten_dict(normal_data)
        object_array_data = {}
        for array_name, array_items in object_arrays.items():
            object_array_data.update(_flatten_object_array(array_name, array_items))

        all_fields = {**flat_data, **object_array_data}

        array_fields = {}
        scalar_fields = {}
        for k, v in all_fields.items():
            if isinstance(v, list) and len(v) > 0:
                array_fields[k] = v
            else:
                scalar_fields[k] = v

        if not array_fields:
            row = scalar_fields.copy()
            row["文件名"] = filename
            result.append(row)
        else:
            max_len = max(len(v) for v in array_fields.values())
            for i in range(max_len):
                row = scalar_fields.copy()
                for field_name, values in array_fields.items():
                    row[field_name] = values[i] if i < len(values) else ""
                row["文件名"] = filename
                result.append(row)

    return result


def _flatten_dict(data: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
    items = []
    for k, v in data.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def _flatten_object_array(array_name: str, array_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not array_data:
        return {}

    all_fields = set()
    for item in array_data:
        if isinstance(item, dict):
            all_fields.update(item.keys())

    result = {}
    for field in all_fields:
        column_name = f"{array_name}{field}"
        result[column_name] = [item.get(field, "") if isinstance(item, dict) else "" for item in array_data]

    return result
