#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import shutil
from src.config import RES_DIR
from src.json_repir import fix_json
from .pdf.pdf_utils import split_pdf_to_images, batch_resize_images, resize_image_high_quality
from .pdf.bank_detector import (
    detect_bank_type, 
    load_bank_template, 
    load_bank_registry,
    detect_bank_from_filename,
    detect_bank_from_image
)
from .pdf.data_extractor import (
    read_summary_data_with_schema, 
    batch_process_images_multithread_with_schema,
    load_schema,
    read_data,
    read_summary_data,
    get_summary_column_x,
    get_real_x_coordinate,
    batch_process_images_multithread,
    process_single_image,
    read_data_with_schema
)
from .pdf.image_marker import (
    add_vertical_lines_to_image, 
    add_vertical_line_to_image,
    process_single_image_label,
    batch_process_images_label_multithread
)
from .pdf.excel_exporter import process_txt_files_to_excel, deduplicate_records

def process_pdf_to_excel(pdf_path, max_workers=4):
    """
    完整处理流程：PDF -> 图片 -> 类型识别 -> 压缩图片 -> AI识别 -> 合并结果 -> Excel
    
    Args:
        pdf_path (str): PDF文件路径
        max_workers (int): 处理图片的线程数
        
    Returns:
        dict: 包含 transactions, summary, bank_type 的结果字典
    """
    # 1. 准备任务目录
    pdf_filename = os.path.splitext(os.path.basename(pdf_path))[0]
    task_dir = os.path.join(RES_DIR, f"task_{pdf_filename}")
    os.makedirs(task_dir, exist_ok=True)

    # 2. 拆分 PDF 为图片
    print(f"步骤1: 拆分 PDF: {pdf_filename}")
    images_dir = os.path.join(task_dir, "images")
    split_pdf_to_images(pdf_path, images_dir)

    # 3. 压缩并调整图片大小
    print(f"步骤2: 压缩图片...")
    compressed_dir = os.path.join(task_dir, "compressed")
    batch_resize_images(images_dir, compressed_dir, max_width=2000, max_height=2000)

    # 4. 识别银行类型
    print(f"步骤3: 识别银行类型...")
    # 尝试查找第一页图片进行识别
    first_page_image = None
    for ext in ['.jpg', '.png']:
        candidate = os.path.join(compressed_dir, f"{pdf_filename}_page_001{ext}")
        if os.path.exists(candidate):
            first_page_image = candidate
            break
            
    bank_type = detect_bank_type(pdf_filename, first_page_image)
    bank_template = load_bank_template(bank_type)
    
    # 保存识别出的银行信息
    bank_info_path = os.path.join(task_dir, "bank_info.json")
    with open(bank_info_path, 'w', encoding='utf-8') as f:
        json.dump({"bank_type": bank_type}, f, ensure_ascii=False, indent=2)

    # 5. 汇总数据提取
    print(f"步骤4: 提取汇总数据...")
    summary_data = None
    if first_page_image:
        try:
            summary_schema = bank_template.get("summary_schema", {})
            summary_response = read_summary_data_with_schema(first_page_image, summary_schema, bank_type)
            summary_data = json.loads(fix_json(summary_response))
            # 保存到任务目录
            with open(os.path.join(task_dir, "summary.json"), 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  汇总数据提取失败: {e}")

    # 6. 生成标记图片 (添加辅助线)
    print(f"步骤5: 生成标记图片...")
    labeled_dir = os.path.join(task_dir, "labeled")
    os.makedirs(labeled_dir, exist_ok=True)
    
    line_config = bank_template.get("vertical_line_config", {})
    if line_config.get("enabled"):
        line_positions = [l.get("x_position") or l.get("x_percent") for l in line_config.get("lines", [])]
        for filename in os.listdir(compressed_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                add_vertical_lines_to_image(
                    os.path.join(compressed_dir, filename), 
                    os.path.join(labeled_dir, filename), 
                    line_positions
                )
    else:
        # 无需标记，直接复制
        for filename in os.listdir(compressed_dir):
            shutil.copy2(os.path.join(compressed_dir, filename), os.path.join(labeled_dir, filename))

    # 7. 批量提取交易数据
    print(f"步骤6: 批量提取数据 (模式: {bank_type})...")
    results_dir = os.path.join(task_dir, "results")
    transaction_schema = bank_template.get("transaction_schema", [])
    batch_process_images_multithread_with_schema(
        labeled_dir, results_dir, 
        transaction_schema, bank_type, 
        max_workers=max_workers
    )

    # 8. 合并记录并导出 Excel
    print(f"步骤7: 合并结果并导出 Excel...")
    excel_path = os.path.join(task_dir, f"{pdf_filename}_result.xlsx")
    final_transactions = process_txt_files_to_excel(results_dir, excel_path, bank_type=bank_type)

    print(f"\n✓ 任务完成! 结果保存在: {task_dir}")
    return {
        "transactions": final_transactions,
        "summary": summary_data,
        "bank_type": bank_type
    }

if __name__ == "__main__":
    process_pdf_to_excel(f"{RES_DIR}/3莱商银行.pdf", 10)