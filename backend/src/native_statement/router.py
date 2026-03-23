"""
原生 PDF 流水识别 API 路由

提供独立的 API 接口，与现有流水识别模块完全隔离。
"""
import os
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse

from src.native_statement.parser import parse_native_pdf, is_native_pdf
from src.native_statement.exporter import export_to_excel

router = APIRouter(prefix="/native-statement", tags=["native-statement"])


@router.post("/parse")
async def parse_pdf(file: UploadFile = File(...)):
    """
    解析原生电子版 PDF 流水

    上传 PDF 文件，返回解析后的 JSON 数据（汇总 + 交易列表）。
    仅支持原生电子版 PDF，扫描件将返回错误提示。
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    # 保存上传文件到临时目录
    tmp_dir = tempfile.mkdtemp(prefix="native_stmt_")
    tmp_path = os.path.join(tmp_dir, file.filename)

    try:
        with open(tmp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # 解析
        result = parse_native_pdf(tmp_path)

        if result.get("error") and not result.get("is_native"):
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    finally:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if os.path.exists(tmp_dir):
            os.rmdir(tmp_dir)


@router.post("/parse-to-excel")
async def parse_pdf_to_excel(file: UploadFile = File(...)):
    """
    解析原生电子版 PDF 流水并导出为 Excel

    上传 PDF 文件，返回 Excel 文件下载。
    仅支持原生电子版 PDF，扫描件将返回错误提示。
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    tmp_dir = tempfile.mkdtemp(prefix="native_stmt_")
    tmp_path = os.path.join(tmp_dir, file.filename)

    try:
        with open(tmp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # 解析
        result = parse_native_pdf(tmp_path)

        if result.get("error") and not result.get("is_native"):
            raise HTTPException(status_code=400, detail=result["error"])

        # 导出 Excel
        excel_buffer = export_to_excel(result)

        # 生成下载文件名
        base_name = os.path.splitext(file.filename)[0]
        download_name = f"{base_name}_解析结果.xlsx"

        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{download_name}"},
        )

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if os.path.exists(tmp_dir):
            os.rmdir(tmp_dir)


@router.post("/check")
async def check_pdf_type(file: UploadFile = File(...)):
    """
    检测 PDF 是否为原生电子版

    返回 {"is_native": true/false}
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    tmp_dir = tempfile.mkdtemp(prefix="native_stmt_")
    tmp_path = os.path.join(tmp_dir, file.filename)

    try:
        with open(tmp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        return {"is_native": is_native_pdf(tmp_path), "filename": file.filename}

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if os.path.exists(tmp_dir):
            os.rmdir(tmp_dir)
