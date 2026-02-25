"""
询证函单文件内容提取测试

用法:
    cd backend
    uv run python tests/test_single_confirmation.py
"""
import os
import sys
import json
import time
import traceback

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.pdf.pdf_utils import split_pdf_to_images
from src.confirmation_letter.service import (
    extract_fields_from_images,
    _validate_and_normalize_fields,
    ALL_FIELDS,
)

# ========== 配置 ==========
PDF_PATH = "/Users/binginx/Desktop/2026年/星辰/运营管理部/50样本/1.pdf"
DPI = 200
# ==========================

# 字段中文名映射
FIELD_LABELS = {
    "confirmation_no": "函证编号",
    "accounting_firm": "事务所名称",
    "reply_address": "回函地址",
    "contact_person": "联系人",
    "phone": "电话",
    "postal_code": "邮编",
    "debit_account": "扣费账号",
    "cutoff_date": "截止日期",
    "start_date": "起始日期",
    "end_date": "终止日期",
    "seal_date": "印章日期",
    "seal_name": "印章名称",
    "signature_name": "落款名称",
}


def recognize_single_pdf(pdf_path: str) -> dict:
    """识别单个 PDF 询证函"""
    filename = os.path.basename(pdf_path)
    print(f"正在处理: {filename}")

    start = time.time()
    try:
        # 1. PDF 转图片
        tmp_dir = os.path.join(os.path.dirname(pdf_path), "_tmp_images")
        os.makedirs(tmp_dir, exist_ok=True)

        image_paths = split_pdf_to_images(pdf_path, tmp_dir, dpi=DPI)
        if not image_paths:
            print("❌ PDF 转图片失败")
            return {}

        print(f"共 {len(image_paths)} 页")

        # 2. 所有页面一次性提交 AI
        fields = extract_fields_from_images(image_paths)
        merged_text = fields.pop("raw_text", "")

        # 3. 后处理
        normalized = _validate_and_normalize_fields(fields, merged_text)

        # 4. 清理临时图片
        for p in image_paths:
            if os.path.exists(p):
                os.remove(p)

        duration = round(time.time() - start, 1)
        print(f"\n✅ 识别完成  耗时: {duration}s\n")

        # 格式化输出
        print("-" * 40)
        for key, label in FIELD_LABELS.items():
            value = normalized.get(key, "")
            print(f"  {label}: {value}")
        print("-" * 40)

        # 输出原始 JSON
        print(f"\n原始 JSON:")
        print(json.dumps(normalized, ensure_ascii=False, indent=2))

        return normalized

    except Exception as e:
        duration = round(time.time() - start, 1)
        print(f"\n❌ 识别失败 ({duration}s): {e}")
        traceback.print_exc()
        return {}


if __name__ == "__main__":
    # 支持命令行参数传入 PDF 路径，否则使用默认路径
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else PDF_PATH

    if not os.path.exists(pdf_path):
        print(f"❌ 文件不存在: {pdf_path}")
        sys.exit(1)

    recognize_single_pdf(pdf_path)
