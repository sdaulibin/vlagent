"""
PDF 类型检测器

检测 PDF 文件是"数字原生"(native) 还是"扫描件"(scanned)。
原生 PDF 可直接用 pdfplumber 提取文本和表格，无需 AI/OCR。
"""
import pdfplumber


def detect_pdf_type(pdf_path: str) -> str:
    """
    检测 PDF 类型。
    
    原理：
    - 原生 PDF（银行系统导出）底层包含字符对象，extract_text() 能提取到大量文字
    - 扫描件 PDF（纸质扫描）底层是嵌入图片，extract_text() 返回空或极少字符
    
    Args:
        pdf_path: PDF 文件路径
        
    Returns:
        'native': 数字原生 PDF（有可提取的文本）
        'scanned': 扫描件 PDF（纯图片，无文本）
    """
    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            return "scanned"
        
        text_chars = 0
        pages_to_check = min(3, len(pdf.pages))
        
        for page in pdf.pages[:pages_to_check]:
            text = page.extract_text() or ""
            text_chars += len(text)
        
        avg_chars = text_chars / pages_to_check
        # 原生 PDF 每页至少有几十到几百个字符
        # 扫描件 PDF 提取文字为 0 或接近 0
        return "native" if avg_chars > 50 else "scanned"


def get_pdf_info(pdf_path: str) -> dict:
    """
    获取 PDF 的基本信息（用于调试）。
    
    Returns:
        dict: 包含页数、类型、前几页的字符数等信息
    """
    with pdfplumber.open(pdf_path) as pdf:
        pages_to_check = min(3, len(pdf.pages))
        page_chars = []
        
        for page in pdf.pages[:pages_to_check]:
            text = page.extract_text() or ""
            page_chars.append(len(text))
        
        avg_chars = sum(page_chars) / len(page_chars) if page_chars else 0
        pdf_type = "native" if avg_chars > 50 else "scanned"
        
        return {
            "total_pages": len(pdf.pages),
            "pdf_type": pdf_type,
            "checked_pages": pages_to_check,
            "chars_per_page": page_chars,
            "avg_chars": round(avg_chars, 1),
        }
