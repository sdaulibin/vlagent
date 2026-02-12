"""
全局配置管理 - 基于 pydantic-settings
"""
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""
    
    # AI Model Configuration
    OPENAI_KEY: str = Field(..., description="Required. Read from environment variable OPENAI_KEY")
    OPENAI_URL: str = "http://10.1.82.113:30208/v1"
    MODEL_LOCAL: str = "d3vcf7gre7tl90toeog0"
    
    # App Configuration
    RES_DIR: str = "res"
    RECOGNITION_TIMEOUT: int = 1800  # 自动停止识别任务的超时时间（秒）30分钟
    
    # Database
    DATABASE_URL: str = Field(..., description="Required. Read from environment variable DATABASE_URL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

# 向后兼容的模块级变量
OPENAI_KEY = settings.OPENAI_KEY
OPENAI_URL = settings.OPENAI_URL
MODEL_LOCAL = settings.MODEL_LOCAL
RES_DIR = settings.RES_DIR
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
