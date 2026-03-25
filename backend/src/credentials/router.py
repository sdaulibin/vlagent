from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
import tempfile
import shutil
import os

from src.credentials.service import process_credential
from src.credentials.schemas import (
    CredentialExtractionResponse,
    IdCardResponse,
    ElectronicSealResponse,
    BankCardResponse,
    ElectronicCredentialResponse,
    OnlineBankingAppResponse,
    NoticeOfIllegalActivityResponse
)
from src.credentials.prompts import PROMPT_MAPPING

router = APIRouter(prefix="/credentials", tags=["credentials"])

@router.post("/extract", response_model=CredentialExtractionResponse)
async def extract_credential(
    file: UploadFile = File(...),
    credential_type: str = Form(..., description=f"支持的类型: {', '.join(PROMPT_MAPPING.keys())}")
):
    """
    提取凭证类文件(图片/PDF)的结构化信息。
    """
    if credential_type not in PROMPT_MAPPING:
        raise HTTPException(status_code=400, detail=f"不受支持的类型: {credential_type}")

    # 使用临时文件保存上传的文件
    ext = os.path.splitext(file.filename)[-1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        result = process_credential(tmp_path, credential_type)
        return CredentialExtractionResponse(
            credential_type=result["credential_type"],
            extracted_data=result["extracted_data"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
