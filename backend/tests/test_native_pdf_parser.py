"""
原生 PDF 解析测试脚本

用于验证 pdfplumber 直接从原生 PDF 中提取银行流水表格数据的效果。
解析结果将保存到与 PDF 同目录的 Excel 文件中。

用法:
    uv run python tests/test_native_pdf_parser.py <pdf文件路径>
"""
import sys
import os
import time
from datetime import datetime
from pathlib import Path

# Add backend root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import Workbook
from services.pdf.pdf_type_detector import detect_pdf_type, get_pdf_info
from services.pdf.native_pdf_extractor import process_native_pdf


def save_to_excel(transactions: list, summary: dict, bank_type: str, pdf_path: str, duration: float) -> str:
    """将解析结果保存到 Excel 文件，返回文件路径"""
    wb = Workbook()
    
    # ---- Sheet 1: 交易明细 ----
    ws_tx = wb.active
    ws_tx.title = "交易明细"
    
    if transactions:
        # 用第一条记录的 key 作为表头
        headers = list(transactions[0].keys())
        ws_tx.append(headers)
        for tx in transactions:
            ws_tx.append([str(tx.get(h, "")).replace("\n", "").replace("\r", "") for h in headers])
    else:
        ws_tx.append(["（无交易数据）"])
    
    # ---- Sheet 2: 汇总信息 ----
    ws_summary = wb.create_sheet("汇总信息")
    ws_summary.append(["字段", "值"])
    ws_summary.append(["银行类型", bank_type])
    ws_summary.append(["源文件", os.path.basename(pdf_path)])
    ws_summary.append(["交易条数", len(transactions)])
    ws_summary.append(["解析耗时(秒)", duration])
    if summary:
        for k, v in summary.items():
            ws_summary.append([k, v])
    
    # 保存到 PDF 同目录
    pdf_dir = os.path.dirname(pdf_path)
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(pdf_dir, f"{pdf_name}_解析结果_{timestamp}.xlsx")
    wb.save(output_path)
    return output_path


def test_native_pdf(pdf_path: str):
    """测试原生 PDF 解析"""
    if not os.path.exists(pdf_path):
        print(f"❌ 文件不存在: {pdf_path}")
        return

    print("=" * 80)
    print(f"原生 PDF 解析测试: {os.path.basename(pdf_path)}")
    print("=" * 80)

    # 1. PDF 类型检测
    print("\n📋 Step 1: PDF 类型检测")
    pdf_info = get_pdf_info(pdf_path)
    print(f"  总页数: {pdf_info['total_pages']}")
    print(f"  PDF 类型: {pdf_info['pdf_type']}")
    print(f"  检查页数: {pdf_info['checked_pages']}")
    print(f"  每页字符数: {pdf_info['chars_per_page']}")
    print(f"  平均字符数: {pdf_info['avg_chars']}")

    if pdf_info['pdf_type'] != 'native':
        print("\n⚠️ 该 PDF 不是原生 PDF（可能是扫描件），无法使用 pdfplumber 提取表格。")
        print("建议使用 VL 模型识别流程。")
        return

    # 2. 提取数据
    print("\n📋 Step 2: 提取表格数据")
    start_time = time.time()
    result = process_native_pdf(pdf_path)
    duration = round(time.time() - start_time, 2)

    # 3. 输出结果
    bank_type = result.get("bank_type", "unknown")
    transactions = result.get("transactions", [])
    summary = result.get("summary")

    print(f"\n📋 Step 3: 解析结果")
    print("-" * 80)
    print(f"  银行类型: {bank_type}")
    print(f"  交易条数: {len(transactions)}")
    print(f"  解析耗时: {duration} 秒")

    if summary:
        print(f"\n  汇总信息:")
        for k, v in summary.items():
            if v:
                print(f"    {k}: {v}")

    if transactions:
        print(f"\n  前 5 条交易记录:")
        print("-" * 80)
        for i, tx in enumerate(transactions[:5]):
            print(f"  [{i + 1}] ", end="")
            fields = [f"{k}: {v}" for k, v in tx.items() if v]
            print(" | ".join(fields[:6]))
        
        if len(transactions) > 5:
            print(f"  ... 还有 {len(transactions) - 5} 条记录")

    # 4. 保存到 Excel
    print(f"\n📋 Step 4: 保存到 Excel")
    excel_path = save_to_excel(transactions, summary, bank_type, pdf_path, duration)
    print(f"  ✅ 已保存到: {excel_path}")

    print("\n" + "=" * 80)
    print(f"✅ 测试完成 | 银行: {bank_type} | 交易: {len(transactions)} 条 | 耗时: {duration}s")
    print(f"   Excel: {excel_path}")
    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: uv run python tests/test_native_pdf_parser.py <pdf文件路径>")
    else:
        test_native_pdf(sys.argv[1])
