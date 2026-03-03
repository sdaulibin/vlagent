import sys
import os
import time
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Add backend root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import Workbook
from src.invoice_recognition.service import _extract_invoice_info
from services.pdf.pdf_utils import split_pdf_to_images

# Excel 表头
EXCEL_HEADERS = [
    "文件名", "页码", "发票类型", "发票号码", "开票日期",
    "金额(价税合计)", "购买方名称", "购买方信用代码",
    "销售方名称", "销售方信用代码", "AI耗时(s)", "错误信息"
]


def init_excel(output_path: str):
    """创建 Excel 工作簿并写入表头，返回 (Workbook, Worksheet)"""
    wb = Workbook()
    ws = wb.active
    ws.title = "发票识别结果"
    ws.append(EXCEL_HEADERS)
    wb.save(output_path)
    return wb, ws


def append_row_and_save(wb, ws, output_path: str, row: list):
    """追加一行数据并立即保存"""
    ws.append(row)
    wb.save(output_path)


def process_invoice_file(file_path: str, tmp_dir: str, wb, ws, output_path: str):
    """处理单个发票文件（PDF或图片），每识别一页立即写入 Excel"""
    filename = os.path.basename(file_path)
    print(f"\n[{filename}] 开始处理...")
    
    try:
        is_pdf = file_path.lower().endswith('.pdf')
        if is_pdf:
            image_paths = split_pdf_to_images(file_path, tmp_dir, dpi=200)
            if not image_paths:
                print(f"[{filename}] ❌ PDF 转换图片失败，未产生文件。")
                append_row_and_save(wb, ws, output_path, [filename, "", "", "", "", "", "", "", "", "", "", "PDF转换失败"])
                return 0
        else:
            image_paths = [file_path]

        page_count = 0
        for i, img_path in enumerate(image_paths):
            page_data = _extract_invoice_info(img_path)
            
            print(f"  => [第 {i + 1} 页] 类型: {page_data.get('invoice_type')} | 号码: {page_data.get('invoice_no')} | 日期: {page_data.get('invoice_date')} | 金额(价税合计): {page_data.get('invoice_amount')} | 购买方: {page_data.get('buyer_name')} | 耗时: {page_data.get('duration')}s")
            if page_data.get("error_msg"):
                print(f"     ❌ 错误: {page_data.get('error_msg')}")
            
            # 每识别一条立即写入 Excel
            row = [
                filename,
                i + 1,
                page_data.get("invoice_type", ""),
                page_data.get("invoice_no", ""),
                page_data.get("invoice_date", ""),
                page_data.get("invoice_amount", ""),
                page_data.get("buyer_name", ""),
                page_data.get("buyer_tax_id", ""),
                page_data.get("seller_name", ""),
                page_data.get("seller_tax_id", ""),
                page_data.get("duration", ""),
                page_data.get("error_msg", "") or "",
            ]
            append_row_and_save(wb, ws, output_path, row)
            page_count += 1
        
        return page_count
        
    except Exception as e:
        print(f"[{filename}] ❌ 处理时发生异常: {e}")
        append_row_and_save(wb, ws, output_path, [filename, "", "", "", "", "", "", "", "", "", "", str(e)])
        return 0


def test_invoice_batch_api(folder_path: str):
    """提取文件夹下所有发票文件（PDF或图片）中的信息并输出汇总结果，同时保存到 Excel"""
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        print(f"❌ 文件夹不存在或路径不是文件夹: {folder_path}")
        return

    print("=" * 80)
    print(f"开始批量发票识别测试，目标文件夹: {folder_path}")
    print("=" * 80)

    # 收集文件（支持 .pdf, .jpg, .jpeg, .png）
    valid_extensions = ('.pdf', '.jpg', '.jpeg', '.png')
    all_files = [
        os.path.join(folder_path, f) for f in os.listdir(folder_path) 
        if f.lower().endswith(valid_extensions) and os.path.isfile(os.path.join(folder_path, f))
    ]
    all_files.sort()
    
    if not all_files:
        print("文件夹中未找到支持的发票文件(.pdf, .jpg, .jpeg, .png)。")
        return

    print(f"找到 {len(all_files)} 个待处理文件。")

    # 初始化 Excel 输出文件（保存在目标文件夹下）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(folder_path, f"发票识别结果_{timestamp}.xlsx")
    wb, ws = init_excel(output_path)
    print(f"识别结果将实时保存到: {output_path}")

    start_time = time.time()
    tmp_dir = tempfile.mkdtemp(prefix="invoice_batch_test_")
    
    total_files_processed = 0
    total_pages_processed = 0
    
    try:
        for file_path in all_files:
            pages = process_invoice_file(file_path, tmp_dir, wb, ws, output_path)
            if pages > 0:
                total_files_processed += 1
                total_pages_processed += pages
                
    finally:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
            
    duration = round(time.time() - start_time, 2)
    print("\n" + "=" * 80)
    print("  ✅ 批量测试完成")
    print("-" * 80)
    print(f"  总耗时: {duration} 秒")
    print(f"  成功处理文件数: {total_files_processed} / {len(all_files)}")
    print(f"  识别总页面数: {total_pages_processed}")
    if total_pages_processed > 0:
        print(f"  平均每页耗时: {round(duration / total_pages_processed, 2)} 秒")
    print(f"  Excel 结果文件: {output_path}")
    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: uv run python tests/test_invoice_batch_rules.py <文件夹路径>")
        # 提供一个默认的测试路径（如果存在）
        default_dir = "/Users/binginx/Desktop/2026年/星辰/运营管理部/50样本/"
        if os.path.exists(default_dir) and os.path.isdir(default_dir):
            print(f"使用默认测试文件夹: {default_dir}\n")
            test_invoice_batch_api(default_dir)
    else:
        folder_path = sys.argv[1]
        test_invoice_batch_api(folder_path)
