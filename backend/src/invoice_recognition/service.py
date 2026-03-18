"""
发票识别核心服务
处理 PDF -> 拆分图片 -> 调用 AI 提取信息 -> 保存到数据库
"""
import os
import json
import shutil
import tempfile
import re
from datetime import datetime
from typing import Any, List

from services.pdf.pdf_utils import split_pdf_to_images
from services.core.request_ai import request_qwen35
from src.config import MODEL_LOCAL
from src.json_repair import fix_json
from sqlmodel.ext.asyncio.session import AsyncSession
from src.invoice_recognition.models import InvoiceFile, InvoiceResult

INVOICE_EXTRACTION_PROMPT = """
Role: 电子发票信息提取专家

Task: 从发票扫描图片中精确提取以下字段信息。

## 待提取字段及识别规则：

1. **invoice_type (发票类型)**
   - 提取图片中的发票类型全称，常见如：电子发票（增值税专用发票）、增值税普通发票、全电发票等。
   - 保持原文原样提取。如果不包含发票类型，返回空字符串。

2. **invoice_no (发票号码)**
   - 提取发票上的「发票号码」。如果不存在则返回空字符串。

3. **invoice_date (开票日期)**
   - 提取发票上的「开票日期」，格式尽量统一为 YYYY-MM-DD，如 2024-05-12。如果不存在返回空字符串。

4. **buyer_name (购买方名称)**
   - 提取购买方（抬头）名称。

5. **buyer_tax_id (购买方统一社会信用代码/纳税人识别号)**
   - 提取购买方的纳税人识别号或统一社会信用代码。

6. **seller_name (销售方名称)**
   - 提取销售方名称。

7. **seller_tax_id (销售方统一社会信用代码/纳税人识别号)**
   - 提取销售方的纳税人识别号或统一社会信用代码。

8. **invoice_amount (发票金额)**
   - 提取发票上的「价税合计（小写）」金额数值。
   - 仅返回数字和可能存在的小数点，例如：42889.40，不要带"¥"符号或其他中文字符。
   - 如果不存在价税合计，请返回空字符串。

## 输出要求：
- 返回 JSON 格式
- 无法识别的字段返回空字符串 ""
- raw_text 字段要求输出整张发票所有的原文文字，保持原文大概顺序
- 仅输出 JSON，无需任何额外解释

## JSON Schema:
{
    "invoice_type": "",
    "invoice_no": "",
    "invoice_date": "",
    "buyer_name": "",
    "buyer_tax_id": "",
    "seller_name": "",
    "seller_tax_id": "",
    "invoice_amount": "",
    "raw_text": ""
}
"""

def _normalize_amount(value: str) -> str:
    """清理金额，提取数字部分"""
    if not value:
        return ""
    # 去除开头的 ¥ 或人民币符号，去除非数字和格式化字符等
    cleaned = value.strip().replace("¥", "").replace(",", "").replace(" ", "").replace("￥", "")
    # 提取所有包含数字和小数点的部分
    match = re.search(r"(\d+(\.\d+)?)", cleaned)
    if match:
        return match.group(1)
    return ""

import time

def _extract_invoice_info(image_path: str) -> dict:
    """对单张发票图片调用 AI 提取数据"""
    start_time = time.time()
    response = request_qwen35(
        question=INVOICE_EXTRACTION_PROMPT,
        file_base=image_path,
        show_request=False
    ).strip()
    duration = time.time() - start_time
    
    try:
        data = json.loads(fix_json(response))
        # 后处理
        data["invoice_amount"] = _normalize_amount(data.get("invoice_amount", ""))
        return dict(
            invoice_type=(data.get("invoice_type", "") or "").strip(),
            invoice_no=(data.get("invoice_no", "") or "").strip(),
            invoice_date=(data.get("invoice_date", "") or "").strip(),
            buyer_name=(data.get("buyer_name", "") or "").strip(),
            buyer_tax_id=(data.get("buyer_tax_id", "") or "").strip(),
            seller_name=(data.get("seller_name", "") or "").strip(),
            seller_tax_id=(data.get("seller_tax_id", "") or "").strip(),
            invoice_amount=data["invoice_amount"],
            raw_text=data.get("raw_text", ""),
            duration=round(duration, 2),
            error_msg=None
        )
    except Exception as e:
        print(f"JSON 解析失败: {e}, 原始响应: {response[:200]}")
        return dict(
            invoice_type="", invoice_no="", invoice_date="",
            buyer_name="", buyer_tax_id="", seller_name="", seller_tax_id="",
            invoice_amount="", raw_text="", 
            duration=round(duration, 2), error_msg=f"解析失败: {str(e)}"
        )

async def process_invoice_recognitions(db: AsyncSession, file_record: InvoiceFile):
    """
    后台任务处理整个发票 PDF 的拆分、识别并批量存入明细
    """
    tmp_dir = tempfile.mkdtemp(prefix="invoice_")
    start_time = datetime.utcnow()
    
    try:
        # 更新状态为 processing
        file_record.status = "processing"
        db.add(file_record)
        await db.commit()
        
        # 判断文件类型：图片直接识别，PDF 先拆分为图片
        file_ext = os.path.splitext(file_record.file_path)[1].lower()
        is_image = file_ext in ('.jpg', '.jpeg', '.png')
        
        if is_image:
            # 图片文件直接作为单页处理
            image_paths = [file_record.file_path]
        else:
            # PDF 拆分为图片
            image_paths = split_pdf_to_images(file_record.file_path, tmp_dir, dpi=200)
            if not image_paths:
                raise ValueError("PDF 转换图片失败，未产生文件。")
            
        file_record.page_count = len(image_paths)
        
        # 2. 对每页单独识别
        for i, img_path in enumerate(image_paths):
            print(f"  后台任务: 正在分析第 {i + 1}/{len(image_paths)} 页发票...")
            page_data = _extract_invoice_info(img_path)
            
            print(f"  后台任务 => [第 {i + 1} 页] 类型: {page_data.get('invoice_type')}, 金额: {page_data.get('invoice_amount')}, 耗时: {page_data.get('duration')}s")
            
            result_record = InvoiceResult(
                file_id=file_record.id,
                page_number=i + 1,
                invoice_type=page_data.get("invoice_type"),
                invoice_no=page_data.get("invoice_no"),
                invoice_date=page_data.get("invoice_date"),
                buyer_name=page_data.get("buyer_name"),
                buyer_tax_id=page_data.get("buyer_tax_id"),
                seller_name=page_data.get("seller_name"),
                seller_tax_id=page_data.get("seller_tax_id"),
                invoice_amount=page_data.get("invoice_amount"),
                raw_text=page_data.get("raw_text"),
                error_msg=page_data.get("error_msg")
            )
            db.add(result_record)
            
        file_record.status = "done"
        
    except Exception as e:
        print(f"Invoice Process Error: {e}")
        file_record.status = "failed"
        file_record.error_msg = str(e)
    finally:
        end_time = datetime.utcnow()
        file_record.recognition_duration = (end_time - start_time).total_seconds()
        db.add(file_record)
        await db.commit()
        
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
