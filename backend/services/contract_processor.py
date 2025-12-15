#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
合同比对处理服务

功能：
1. 文档转图片
2. 使用 AI 提取文本内容
3. 文本差异比对
4. 生成差异报告
"""

import os
import json
from pathlib import Path
from pdf2image import convert_from_path
from core.config import MODEL_LOCAL, RES_DIR
from core.request_ai import request_stream
from core.json_repir import fix_json
from services.pdf_processor import load_schema

# 合同比对输出目录
CONTRACT_OUTPUT_DIR = os.path.join(RES_DIR, "contracts")
os.makedirs(CONTRACT_OUTPUT_DIR, exist_ok=True)


def extract_text_from_image(image_path: str) -> str:
    """
    使用 AI 从图片中提取文本内容
    
    Args:
        image_path: 图片文件路径
        
    Returns:
        str: 提取的文本内容
    """
    prompt = """
    你是一个专业的文档文本提取专家。请仔细阅读图片中的所有文字内容，并完整提取出来。
    
    要求：
    1. 保持原文的段落结构和层级关系
    2. 保留标题、编号、列表等格式
    3. 如果有表格，用文字描述表格内容
    4. 忽略页眉、页脚、页码等非正文内容
    5. 输出纯文本，不需要 JSON 格式
    
    直接输出提取的文本内容，不需要任何解释。
    """
    
    result = request_stream(
        question=prompt,
        show_request=False,
        file_base=image_path,
        model=MODEL_LOCAL
    )
    
    return result


def convert_to_images(file_path: str, output_folder: str) -> list:
    """
    将文档转换为图片列表
    
    Args:
        file_path: 文档路径 (PDF)
        output_folder: 输出文件夹
        
    Returns:
        list: 图片路径列表
    """
    os.makedirs(output_folder, exist_ok=True)
    
    # PDF 文件
    if file_path.lower().endswith('.pdf'):
        pages = convert_from_path(file_path, dpi=200)
        image_paths = []
        
        filename = Path(file_path).stem
        for i, page in enumerate(pages):
            image_path = os.path.join(output_folder, f"{filename}_page_{i+1:03d}.png")
            page.save(image_path, 'PNG')
            image_paths.append(image_path)
        
        return image_paths
    
    # 图片文件直接返回
    elif file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
        return [file_path]
    
    # DOCX 文件返回空列表（使用文本提取方式）
    elif file_path.lower().endswith(('.docx', '.doc')):
        return []
    
    else:
        raise ValueError(f"Unsupported file format: {file_path}")


def extract_text_from_docx(file_path: str) -> str:
    """
    从 DOCX 文件中提取文本
    
    Args:
        file_path: DOCX 文件路径
        
    Returns:
        str: 提取的文本内容
    """
    try:
        from docx import Document
        doc = Document(file_path)
        
        paragraphs = []
        for para in doc.paragraphs:
            if para.text.strip():
                paragraphs.append(para.text)
        
        # 提取表格内容
        for table in doc.tables:
            for row in table.rows:
                row_text = ' | '.join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    paragraphs.append(row_text)
        
        return '\n\n'.join(paragraphs)
    except ImportError:
        raise ImportError("请安装 python-docx: pip install python-docx")


def extract_document_content(file_path: str) -> str:
    """
    提取文档的全部文本内容
    
    Args:
        file_path: 文档路径
        
    Returns:
        str: 文档文本内容
    """
    # DOCX 文件直接提取文本
    if file_path.lower().endswith(('.docx', '.doc')):
        print(f"提取 DOCX 文本: {file_path}")
        return extract_text_from_docx(file_path)
    
    # 其他格式转图片后 OCR
    filename = Path(file_path).stem
    output_folder = os.path.join(CONTRACT_OUTPUT_DIR, f"task_{filename}")
    
    # 转换为图片
    image_paths = convert_to_images(file_path, output_folder)
    
    if not image_paths:
        raise ValueError(f"无法处理文件: {file_path}")
    
    # 提取每页文本
    all_text = []
    for image_path in image_paths:
        text = extract_text_from_image(image_path)
        all_text.append(text)
    
    return "\n\n".join(all_text)


def compare_texts(text_a: str, text_b: str) -> list:
    """
    使用 AI 对比两份文本的差异
    
    Args:
        text_a: 原文档文本
        text_b: 比对文档文本
        
    Returns:
        list: 差异列表
    """
    prompt = f"""
    你是一个专业的文档比对专家。请对比以下两份文档内容，找出它们之间的差异。

    【原文档】
    {text_a[:3000]}  
    
    【比对文档】
    {text_b[:3000]}
    
    请以 JSON 数组格式输出差异列表，每个差异项包含：
    - type: 差异类型，值为 "added"（新增）、"deleted"（删除）或 "modified"（修改）
    - original: 原文档中的内容（删除或修改时填写）
    - comparison: 比对文档中的内容（新增或修改时填写）
    - location: 差异所在的章节或位置描述

    示例格式：
    [
        {{"type": "modified", "original": "原内容", "comparison": "新内容", "location": "第1章"}},
        {{"type": "deleted", "original": "被删除的内容", "comparison": "", "location": "第2章"}},
        {{"type": "added", "original": "", "comparison": "新增的内容", "location": "第3章"}}
    ]

    只输出 JSON 数组，不需要任何解释。
    """
    
    result = request_stream(
        question=prompt,
        show_request=False,
        model=MODEL_LOCAL
    )
    
    # 解析 JSON
    try:
        # 尝试修复可能的 JSON 格式问题
        fixed_json = fix_json(result)
        diffs = json.loads(fixed_json)
        
        if isinstance(diffs, list):
            return diffs
        else:
            return []
    except Exception as e:
        print(f"JSON 解析失败: {e}")
        print(f"原始结果: {result}")
        return []


def compare_documents(file_a_path: str, file_b_path: str) -> list:
    """
    比对两份文档
    
    Args:
        file_a_path: 原文档路径
        file_b_path: 比对文档路径
        
    Returns:
        list: 差异列表
    """
    result = compare_documents_with_content(file_a_path, file_b_path)
    return result.get("diffs", [])


def compare_documents_with_content(file_a_path: str, file_b_path: str) -> dict:
    """
    比对两份文档，返回内容和差异
    
    Args:
        file_a_path: 原文档路径
        file_b_path: 比对文档路径
        
    Returns:
        dict: 包含 content_a, content_b, diffs
    """
    print(f"开始比对文档: {file_a_path} vs {file_b_path}")
    
    # 提取文本内容
    print("提取原文档内容...")
    text_a = extract_document_content(file_a_path)
    
    print("提取比对文档内容...")
    text_b = extract_document_content(file_b_path)
    
    # 比对差异
    print("分析文档差异...")
    diffs = compare_texts(text_a, text_b)
    
    print(f"共发现 {len(diffs)} 处差异")
    
    return {
        "content_a": text_a,
        "content_b": text_b,
        "diffs": diffs
    }


if __name__ == "__main__":
    # 测试代码
    test_a = os.path.join(RES_DIR, "contracts/test_a.pdf")
    test_b = os.path.join(RES_DIR, "contracts/test_b.pdf")
    
    if os.path.exists(test_a) and os.path.exists(test_b):
        result = compare_documents(test_a, test_b)
        print(json.dumps(result, ensure_ascii=False, indent=2))

