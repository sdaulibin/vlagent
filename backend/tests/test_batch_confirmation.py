"""
询证函批量识别测试脚本

批量处理指定目录下的 PDF 询证函文件，识别 12 项关键字段，并导出为 Excel。

用法:
    cd backend
    uv run python tests/test_batch_confirmation.py
"""
import os
import sys
import json
import time
import traceback
from datetime import datetime

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.pdf.pdf_utils import split_pdf_to_images
from services.core.request_ai import request_stream
from src.config import MODEL_LOCAL
from src.json_repair import fix_json

# ========== 配置 ==========
INPUT_DIR = "/Users/binginx/Desktop/2026年/星辰/运营管理部/50样本"
OUTPUT_DIR = INPUT_DIR  # Excel 输出到同目录
MAX_WORKERS = 1  # 串行处理，避免 AI 服务过载
DPI = 200
# ==========================

FIELD_EXTRACTION_PROMPT = """
Role: 银行询证函信息提取专家

Task: 从银行询证函扫描图片中精确提取以下 12 项字段信息。

## 待提取字段及识别规则：

1. **confirmation_no (函证编号)** - 关键字优先级：函证编号 > 询证函编号 > 编号 > NO. > 索引号，通常在右上角或左上角，不包含页码后缀
2. **accounting_firm (事务所名称)** - 关键字：「本公司聘请的」「会计师事务所」，提取事务所全称
3. **reply_address (回函地址)** - 关键字：回函地址、收件地址、回函请寄、回函邮寄地址
4. **contact_person (联系人)** - 关键字：联系人、收件人、回函快递收件人
5. **phone (电话)** - 关键字：电话、联系电话、收件手机号、收件电话
6. **postal_code (邮编)** - 6位数字格式
7. **debit_account (扣费账号)** - 银行账号格式
8. **cutoff_date (截止日期)** - 日期格式，如 2024年12月31日
9. **start_date (起始日期)** - 区间起始日期
10. **end_date (终止日期)** - 区间终止日期
11. **seal_date (印章日期)** - 印章中的日期
12. **seal_name (印章名称)** - 印章中的单位名称

## 输出要求：
- 返回 JSON 格式
- 无法识别的字段返回空字符串 ""
- 日期格式统一为 YYYY-MM-DD
- 仅输出 JSON，无需解释

## JSON Schema:
{
    "confirmation_no": "",
    "accounting_firm": "",
    "reply_address": "",
    "contact_person": "",
    "phone": "",
    "postal_code": "",
    "debit_account": "",
    "cutoff_date": "",
    "start_date": "",
    "end_date": "",
    "seal_date": "",
    "seal_name": ""
}
"""

# 字段中文名映射
FIELD_LABELS = {
    "filename": "文件名",
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
    "status": "识别状态",
    "duration_s": "耗时(秒)",
    "error": "错误信息",
}

FIELD_KEYS = list(FIELD_LABELS.keys())


def recognize_single_pdf(pdf_path: str) -> dict:
    """识别单个 PDF 询证函"""
    filename = os.path.basename(pdf_path)
    result = {"filename": filename, "status": "failed", "error": "", "duration_s": 0}

    start = time.time()
    try:
        # 1. PDF 转图片（仅第一页）
        tmp_dir = os.path.join(os.path.dirname(pdf_path), "_tmp_images")
        os.makedirs(tmp_dir, exist_ok=True)

        image_paths = split_pdf_to_images(pdf_path, tmp_dir, dpi=DPI)
        if not image_paths:
            result["error"] = "PDF 转图片失败"
            return result

        first_page = image_paths[0]

        # 2. AI 识别
        response = request_stream(
            question=FIELD_EXTRACTION_PROMPT,
            file_base=first_page,
            model=MODEL_LOCAL,
            show_request=False,
        ).strip()

        # 3. 解析 JSON
        data = json.loads(fix_json(response))
        result.update(data)
        result["status"] = "success"

        # 4. 清理临时图片
        for p in image_paths:
            if os.path.exists(p):
                os.remove(p)

    except Exception as e:
        result["error"] = str(e)
        traceback.print_exc()

    result["duration_s"] = round(time.time() - start, 1)
    return result


def export_to_excel(results: list, output_path: str):
    """导出识别结果到 Excel"""
    try:
        import openpyxl
    except ImportError:
        print("正在安装 openpyxl...")
        os.system(f"{sys.executable} -m pip install openpyxl")
        import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "询证函识别结果"

    # 表头
    headers = [FIELD_LABELS[k] for k in FIELD_KEYS]
    ws.append(headers)

    # 设置表头样式
    from openpyxl.styles import Font, PatternFill, Alignment
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")
    for col_idx, cell in enumerate(ws[1], 1):
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    # 数据行
    for r in results:
        row = [r.get(k, "") for k in FIELD_KEYS]
        ws.append(row)

    # 自动列宽
    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            val = str(cell.value) if cell.value else ""
            max_len = max(max_len, len(val.encode("utf-8")))
        ws.column_dimensions[col_letter].width = min(max_len + 4, 50)

    wb.save(output_path)
    print(f"\n✅ Excel 已导出: {output_path}")


def main():
    print("=" * 60)
    print("  银行询证函批量识别测试")
    print(f"  输入目录: {INPUT_DIR}")
    print(f"  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 扫描 PDF 文件
    pdf_files = sorted([
        os.path.join(INPUT_DIR, f)
        for f in os.listdir(INPUT_DIR)
        if f.lower().endswith(".pdf")
    ])

    total = len(pdf_files)
    print(f"\n找到 {total} 个 PDF 文件\n")

    if total == 0:
        print("没有找到 PDF 文件，退出。")
        return

    # 逐个处理
    results = []
    success_count = 0
    total_start = time.time()

    for idx, pdf_path in enumerate(pdf_files, 1):
        filename = os.path.basename(pdf_path)
        print(f"[{idx}/{total}] 正在处理: {filename} ...", end=" ", flush=True)

        result = recognize_single_pdf(pdf_path)
        results.append(result)

        if result["status"] == "success":
            success_count += 1
            print(f"✅ ({result['duration_s']}s)")
        else:
            print(f"❌ {result['error']}")

    total_duration = round(time.time() - total_start, 1)

    # 导出 Excel
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_path = os.path.join(OUTPUT_DIR, f"询证函识别结果_{timestamp}.xlsx")
    export_to_excel(results, excel_path)

    # 统计
    print(f"\n{'=' * 60}")
    print(f"  处理完成!")
    print(f"  总数: {total}  成功: {success_count}  失败: {total - success_count}")
    print(f"  总耗时: {total_duration}s  平均: {round(total_duration / total, 1)}s/份")
    print(f"  结果文件: {excel_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
