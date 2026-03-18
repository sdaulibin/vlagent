import os
import json
from src.config import MODEL_LOCAL
from services.core.request_ai import request_qwen35

# 多银行 Schema 目录
BANK_SCHEMAS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "bank_schemas")

def load_bank_registry():
    """
    加载银行名称映射表
    
    Returns:
        dict: 银行名称到模板ID的映射
    """
    registry_path = os.path.join(BANK_SCHEMAS_DIR, "bank_registry.json")
    if os.path.exists(registry_path):
        with open(registry_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def load_bank_template(bank_type: str):
    """
    加载指定银行的模板配置
    
    Args:
        bank_type: 银行模板ID，如 "shandong_local", "everbright", "cmb"
        
    Returns:
        dict: 银行模板配置，包含 summary_schema 和 transaction_schema
    """
    template_path = os.path.join(BANK_SCHEMAS_DIR, f"{bank_type}.json")
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def detect_bank_from_filename(filename: str):
    """
    从文件名识别银行类型（优先级最高）
    
    Args:
        filename: 文件名
        
    Returns:
        str: 银行模板ID，未识别返回 None
    """
    registry = load_bank_registry()
    keywords = registry.get("keywords", {})
    
    for bank_name, bank_id in keywords.items():
        # 中文关键词直接匹配，英文关键词忽略大小写
        if bank_name in filename or bank_name.lower() in filename.lower():
            return bank_id
    return None

def detect_bank_from_image(image_path: str):
    """
    从图片识别银行类型（印章 -> Logo）
    
    Args:
        image_path: 图片路径
        
    Returns:
        str: 银行模板ID，未识别返回默认值
    """
    prompt = """
    请识别这张银行流水单所属的银行。请观察单据上的公章或Logo。
    候选清单：
    - 招商银行 (CHINA MERCHANTS BANK) -> 返回: cmb
    - 光大银行 (CHINA EVERBRIGHT BANK) -> 返回: everbright
    - 济宁银行 (济宁银行股份有限公司) -> 返回: jining
    - 广发银行 (广发银行股份有限公司/CGB) -> 返回: cgb
    - 邮储银行 (中国邮政储蓄银行/PSBC) -> 返回: psbc
    - 工商银行 (中国工商银行/ICBC) -> 返回: icbc
    - 威海银行 (威海市商业银行) -> 返回: shandong_local
    - 山东农信 (山东省农村信用社/齐鲁银行/泰安银行/潍坊银行/莱商银行等) -> 返回: shandong_local
    
    只需返回模板ID（如 cmb, everbright, jining, cgb, psbc, icbc, shandong_local）。严禁输出其他文字。
    """
    
    response = request_qwen35(question=prompt, 
                             file_base=image_path).strip().lower()
    
    # 清理AI返回的可能含有的markdown或额外空格
    if "icbc" in response: return "icbc"
    if "cmb" in response: return "cmb"
    if "everbright" in response: return "everbright"
    if "jining" in response: return "jining"
    if "cgb" in response: return "cgb"
    if "psbc" in response: return "psbc"
    if "shandong_local" in response: return "shandong_local"
    
    return "shandong_local"  # 默认兖底

def detect_bank_type(filename: str, first_page_image: str = None):
    """
    综合识别银行类型（按优先级）
    
    优先级: 文件名 > 印章/Logo
    
    Args:
        filename: 文件名
        first_page_image: 第一页图片路径（可选）
        
    Returns:
        str: 银行模板ID
    """
    # 1. 尝试从文件名识别
    bank_type = detect_bank_from_filename(filename)
    if bank_type:
        print(f"  根据文件名识别银行类型: {bank_type}")
        return bank_type
        
    # 2. 尝试从图片识别
    if first_page_image:
        print("  文件名未包含银行关键词，正在尝试从图片内容识别...")
        bank_type = detect_bank_from_image(first_page_image)
        print(f"  根据图片识别银行类型: {bank_type}")
        return bank_type
        
    return "shandong_local"
