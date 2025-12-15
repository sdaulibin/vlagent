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


def extract_text_from_doc(file_path: str) -> str:
    """
    从旧版 DOC 文件中提取文本 (使用 antiword 或 textract)
    
    Args:
        file_path: DOC 文件路径
        
    Returns:
        str: 提取的文本内容
    """
    import subprocess
    
    # 尝试使用 antiword
    try:
        result = subprocess.run(
            ['antiword', file_path],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            return result.stdout
    except FileNotFoundError:
        print("antiword 未安装，尝试其他方法...")
    except subprocess.TimeoutExpired:
        print("antiword 超时")
    except Exception as e:
        print(f"antiword 失败: {e}")
    
    # 尝试使用 LibreOffice 转换
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                ['soffice', '--headless', '--convert-to', 'txt:Text', '--outdir', temp_dir, file_path],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                # 找到转换后的 txt 文件
                txt_file = os.path.join(temp_dir, Path(file_path).stem + '.txt')
                if os.path.exists(txt_file):
                    with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
                        return f.read()
    except FileNotFoundError:
        print("LibreOffice 未安装")
    except subprocess.TimeoutExpired:
        print("LibreOffice 转换超时")
    except Exception as e:
        print(f"LibreOffice 转换失败: {e}")
    
    # 最后尝试：读取为二进制并提取可读文本
    print("使用基础文本提取...")
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
            # 尝试提取可读文本
            text = content.decode('utf-8', errors='ignore')
            # 过滤掉不可打印字符
            import re
            text = re.sub(r'[^\u4e00-\u9fff\u0020-\u007e\n\r\t]', '', text)
            # 清理多余空行
            text = re.sub(r'\n{3,}', '\n\n', text)
            return text.strip()
    except Exception as e:
        raise ValueError(f"无法提取 DOC 文件内容: {e}")


def extract_document_content(file_path: str) -> str:
    """
    提取文档的全部文本内容
    
    Args:
        file_path: 文档路径
        
    Returns:
        str: 文档文本内容
    """
    # DOCX 文件直接提取文本
    if file_path.lower().endswith('.docx'):
        print(f"提取 DOCX 文本: {file_path}")
        return extract_text_from_docx(file_path)
    
    # 旧版 DOC 文件
    if file_path.lower().endswith('.doc'):
        print(f"提取 DOC 文本: {file_path}")
        return extract_text_from_doc(file_path)
    
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
    # 增加文本长度限制以覆盖更多内容
    max_len = 8000
    
    prompt = f"""
    你是一个专业的文档比对专家。请逐字逐句仔细对比以下两份文档内容，找出它们之间的所有差异。

    【重要提示】
    - 请特别注意以下类型的差异：
      1. 文字增加或删除（如"基本信息"变为"基本信息哈哈哈"）
      2. 数字变化（如编码、金额、日期的任何不同）
      3. 标点符号变化
      4. 章节标题的任何改动
    - 即使是很小的差异也必须报告
    - 逐段落、逐行比对，不要遗漏

    【原文档】
    {text_a[:max_len]}  
    
    【比对文档】
    {text_b[:max_len]}
    
    请以 JSON 数组格式输出差异列表，每个差异项包含：
    - type: 差异类型，值为 "added"（新增）、"deleted"（删除）或 "modified"（修改）
    - original: 原文档中的内容（删除或修改时填写，保留原始完整文本）
    - comparison: 比对文档中的内容（新增或修改时填写，保留原始完整文本）
    - location: 差异所在的章节或位置描述（如"第一章 基本信息"）

    示例格式：
    [
        {{"type": "modified", "original": "产品登记编码 Z7003525000319", "comparison": "产品登记编码 Z7003525000319123", "location": "基本信息"}},
        {{"type": "modified", "original": "第一章 基本信息", "comparison": "第一章 基本信息哈哈哈", "location": "章节标题"}},
        {{"type": "deleted", "original": "被删除的内容", "comparison": "", "location": "第2章"}}
    ]

    请务必找出所有差异，只输出 JSON 数组，不需要任何解释。
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

