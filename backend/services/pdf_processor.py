#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import shutil
from src.config import RES_DIR
from src.json_repair import fix_json
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
    print(f"开始处理 PDF，使用 VL 模型识别流程: {pdf_filename}")
    
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
    
    if bank_type == "cgb":
        # 广发银行：扫描所有页面，但只从"第1页"提取汇总（记录页码用于后续交易分配）
        summary_data = []
        summary_schema = bank_template.get("summary_schema", {})
        
        # 获取所有页面图片并按名称排序
        compressed_images = sorted([
            f for f in os.listdir(compressed_dir) 
            if f.lower().endswith(('.jpg', '.jpeg', '.png'))
        ])
        
        for page_idx, img_file in enumerate(compressed_images):
            img_path = os.path.join(compressed_dir, img_file)
            try:
                # 先检查页脚是否包含"第1页"或"第 1 页"
                # 使用简单的提示词检测页码
                from .pdf.data_extractor import request_qwen35
                from src.config import MODEL_LOCAL
                
                page_check_prompt = """
                Check if this page's footer contains "第1页" or "第 1 页" (meaning "Page 1").
                Look at the bottom of the page for page number indicators like "第X页,共X页" or "第X页/共X页".
                
                Return JSON only:
                - If footer shows "第1页" or "第 1 页": {"is_first_page": true}
                - Otherwise: {"is_first_page": false}
                
                No explanation, only JSON.
                """
                
                page_check_response = request_qwen35(question=page_check_prompt, file_base=img_path).strip()
                page_info = json.loads(fix_json(page_check_response))
                
                is_first_page = page_info.get("is_first_page", False)
                
                # 只从"第1页"提取汇总信息
                if not is_first_page:
                    continue
                
                summary_response = read_summary_data_with_schema(img_path, summary_schema, bank_type)
                page_summary = json.loads(fix_json(summary_response))
                
                # 严格验证：必须同时包含多个关键字段才认为是有效汇总
                # 要求：账号 + 户名 + 起止日期 + (收入总金额 或 支出总金额) + 记录数
                is_valid_summary = (
                    page_summary and 
                    page_summary.get("账号") and 
                    page_summary.get("户名") and
                    page_summary.get("起止日期") and
                    (page_summary.get("收入总金额") or page_summary.get("支出总金额")) and
                    page_summary.get("记录数")
                )
                
                if is_valid_summary:
                    # 检查是否已存在相同起止日期的汇总（去重）
                    date_range = page_summary.get("起止日期", "")
                    existing = any(s.get("起止日期") == date_range for s in summary_data)
                    if not existing:
                        # 记录该汇总首次出现的页码（用于后续交易分配）
                        page_summary["_start_page"] = page_idx
                        print(f"  发现汇总: {page_summary.get('起止日期', '未知日期')} (页{page_idx+1}, 第1页标记)")
                        summary_data.append(page_summary)
            except Exception as e:
                # 该页面可能不包含汇总信息，跳过
                pass
        
        # 如果没有找到任何汇总，设为 None
        if not summary_data:
            summary_data = None
        elif len(summary_data) == 1:
            summary_data = summary_data[0]  # 单个汇总返回对象而非数组
    else:
        # 其他银行：只从第一页提取
        if first_page_image:
            try:
                summary_schema = bank_template.get("summary_schema", {})
                summary_response = read_summary_data_with_schema(first_page_image, summary_schema, bank_type)
                summary_data = json.loads(fix_json(summary_response))
            except Exception as e:
                print(f"  汇总数据提取失败: {e}")
    
    # 保存汇总数据
    if summary_data:
        with open(os.path.join(task_dir, "summary.json"), 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)

    # 6. 生成标记图片 (添加辅助线) - 仅在启用时执行
    line_config = bank_template.get("vertical_line_config", {})
    if line_config.get("enabled"):
        print(f"步骤5: 生成标记图片...")
        labeled_dir = os.path.join(task_dir, "labeled")
        os.makedirs(labeled_dir, exist_ok=True)
        line_positions = [l.get("x_position") or l.get("x_percent") for l in line_config.get("lines", [])]
        for filename in os.listdir(compressed_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                add_vertical_lines_to_image(
                    os.path.join(compressed_dir, filename), 
                    os.path.join(labeled_dir, filename), 
                    line_positions
                )
        # 使用标记后的图片目录进行识别
        recognition_dir = labeled_dir
    else:
        # 无需标记，直接使用压缩后的图片目录进行识别
        print(f"步骤5: 跳过标记(vertical_line_config未启用)，直接使用原图...")
        recognition_dir = compressed_dir

    # 7. 批量提取交易数据
    print(f"步骤6: 批量提取数据 (模式: {bank_type})...")
    results_dir = os.path.join(task_dir, "results")
    transaction_schema = bank_template.get("transaction_schema", [])
    batch_process_images_multithread_with_schema(
        recognition_dir, results_dir, 
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