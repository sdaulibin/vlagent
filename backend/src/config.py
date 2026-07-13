"""
全局配置管理 - 基于 pydantic-settings
"""
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""
    
    # AI Model Configuration (Qwen VL - 视觉模型)
    # OPENAI_KEY: str = Field(..., description="Required. Read from environment variable OPENAI_KEY")
    # OPENAI_URL: str = "http://10.1.82.113:30208/v1"
    # MODEL_LOCAL: str = "d3vcf7gre7tl90toeog0"
    
    # AI Model Configuration (Qwen3.5 - 纯文本模型)
    QWEN35_KEY: str = Field(default="", description="Qwen3.5 API Key")
    QWEN35_URL: str = "http://10.1.84.77/v1"
    QWEN35_MODEL: str = "Qwen3.5-35B"
    
    # App Configuration
    UPLOAD_DIR: str = "upload"
    DOWNLOAD_DIR: str = "download"
    RECOGNITION_TIMEOUT: int = 1800  # 自动停止识别任务的超时时间（秒）30分钟

    # 各模块上传目录（默认在 UPLOAD_DIR 下的子目录）
    UPLOAD_DIR_BANK_STATEMENT: str = Field(
        default="", description="银行流水上传目录（默认 upload/bank_statement）"
    )
    UPLOAD_DIR_CONFIRMATION: str = Field(
        default="", description="询证函上传目录（默认 upload/confirmation）"
    )
    UPLOAD_DIR_FORMAT_COMPARE: str = Field(
        default="", description="格式比对上传目录（默认 upload/format_compare）"
    )
    UPLOAD_DIR_DOCUMENT: str = Field(
        default="", description="文档比对上传目录（默认 upload/documents）"
    )
    UPLOAD_DIR_INVOICE: str = Field(
        default="", description="发票识别上传目录（默认 upload/invoice）"
    )
    UPLOAD_DIR_CREDENTIAL: str = Field(
        default="", description="凭证识别上传目录（默认 upload/credentials）"
    )
    UPLOAD_DIR_PDF_EXTRACT: str = Field(
        default="", description="PDF提取上传目录（默认 upload/pdf_extract）"
    )
    UPLOAD_DIR_CREDIT_COMPARISON: str = Field(
        default="", description="信用金额对账上传目录（默认 upload/credit_comparison）"
    )
    CREDIT_CONVERTED_DIR: str = Field(
        default="", description="信用金额对账 doc 转换产物目录（默认 upload/credit_comparison/_converted）"
    )
    CREDIT_PREVIEW_DIR: str = Field(
        default="", description="信用金额对账预览产物目录（默认 upload/credit_comparison/_previews）"
    )

    # Image Platform (SunECM)
    ECM_ENABLED: bool = False
    ECM_CACHE_IP: str = "10.238.145.107"
    ECM_CACHE_PORT: int = 8022
    ECM_MODEL_CODE: str = "RP_RB"
    ECM_DOC_PART: str = "RP_RB_PART"
    ECM_SERVER_NAME: str = "SunECMDM"
    ECM_GROUP_NAME: str = "group107"
    ECM_USERNAME: str = "ibd"
    ECM_PASSWORD: str = ""

    # JWT Authentication
    JWT_SECRET: str = Field(default="", description="Shared secret for JWT token verification (HS256)")
    JWT_ALGORITHM: str = "HS256"

    # Permission: 无权限记录时是否默认开放所有模块（生产环境应设为 False）
    PERMISSION_DEFAULT_OPEN: bool = Field(default=True, description="无权限记录时是否默认开放所有模块")

    # Database
    DATABASE_URL: str = Field(..., description="Required. Read from environment variable DATABASE_URL")
    DATABASE_ECHO: bool = False

    # Upstream Database (ioa)
    DATABASE_UPSTREAM_URL: str = Field(default="", description="上游数据库连接 URL（ioa 库）")
    SYNC_INTERVAL_MINUTES: int = Field(default=5, description="上游数据同步间隔（分钟）")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

# 解析各模块上传目录（未配置时使用默认路径）
import os as _os

_PROJECT_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))


def _resolve_upload_dir(custom: str, default_subdir: str) -> str:
    if custom:
        return custom
    return _os.path.join(_PROJECT_ROOT, settings.UPLOAD_DIR, default_subdir)


UPLOAD_DIR_BANK_STATEMENT = _resolve_upload_dir(settings.UPLOAD_DIR_BANK_STATEMENT, "bank_statement")
UPLOAD_DIR_CONFIRMATION = _resolve_upload_dir(settings.UPLOAD_DIR_CONFIRMATION, "confirmation")
UPLOAD_DIR_FORMAT_COMPARE = _resolve_upload_dir(settings.UPLOAD_DIR_FORMAT_COMPARE, "format_compare")
UPLOAD_DIR_DOCUMENT = _resolve_upload_dir(settings.UPLOAD_DIR_DOCUMENT, "documents")
UPLOAD_DIR_INVOICE = _resolve_upload_dir(settings.UPLOAD_DIR_INVOICE, "invoice")
UPLOAD_DIR_CREDENTIAL = _resolve_upload_dir(settings.UPLOAD_DIR_CREDENTIAL, "credentials")
UPLOAD_DIR_PDF_EXTRACT = _resolve_upload_dir(settings.UPLOAD_DIR_PDF_EXTRACT, "pdf_extract")

# 信用金额对账模块：上传目录、转换产物目录、预览产物目录
UPLOAD_DIR_CREDIT_COMPARISON = _resolve_upload_dir(settings.UPLOAD_DIR_CREDIT_COMPARISON, "credit_comparison")
CREDIT_CONVERTED_DIR = (
    settings.CREDIT_CONVERTED_DIR
    or _os.path.join(UPLOAD_DIR_CREDIT_COMPARISON, "_converted")
)
CREDIT_PREVIEW_DIR = (
    settings.CREDIT_PREVIEW_DIR
    or _os.path.join(UPLOAD_DIR_CREDIT_COMPARISON, "_previews")
)

# 向后兼容的模块级变量 (Qwen VL)
# OPENAI_KEY = settings.OPENAI_KEY
# OPENAI_URL = settings.OPENAI_URL
# MODEL_LOCAL = settings.MODEL_LOCAL

# Qwen3.5 纯文本模型
QWEN35_KEY = settings.QWEN35_KEY
QWEN35_URL = settings.QWEN35_URL
QWEN35_MODEL = settings.QWEN35_MODEL
UPLOAD_DIR = settings.UPLOAD_DIR
DOWNLOAD_DIR = settings.DOWNLOAD_DIR
RECOGNITION_TIMEOUT = settings.RECOGNITION_TIMEOUT

# 其他模型常量（不通过环境变量配置）
MODEL_QWEN_VLMAX = "qwen-vl-max"
MODEL_QWEN3_VLPLUS = "qwen3-vl-plus"
MODEL_QWEN_VLMAX_LATEST = "qwen-vl-max-latest"
MODEL_QWEN_VLMAX_0402 = "qwen-vl-max-2025-04-02"
MODEL_QWEN_VLMAX_0408 = "qwen-vl-max-2025-04-08"
MODEL_QWEN_VLMAX_0813 = "qwen-vl-max-2025-08-13"
MODEL_QWEN_VL72B = "qwen2.5-vl-72b-instruct"
MODEL_QWEN_32B = "qwen2.5-32b-instruct"
MODEL_QWEN_72B = "qwen2.5-72b-instruct"
MODEL_QWEN_7B = "qwen2.5-7b-instruct"
MODEL_QWENVL_7B = "qwen2.5-vl-7b-instruct"
MODEL_QWEN_OCR_LATEST = "qwen-vl-ocr-latest"
MODEL_QWEN_OCR = "qwen-vl-ocr"
MODEL_QVQ = "qvq-max"
MODEL_OMNI = "qwen-omni-turbo"
MODEL_QWEN_MAX = "qwen3-max-2025-09-23"
MODEL_QWEN_8B = "qwen3-8b"
MODEL_QWEN_FLASH = "qwen-flash"
