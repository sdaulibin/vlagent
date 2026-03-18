import os
import json
import concurrent.futures
from src.config import MODEL_LOCAL
from services.core.request_ai import request_stream, request_qwen35
from src.json_repair import fix_json

# Schema 配置文件路径
SCHEMA_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "schemas.json")
# Prompt 配置目录路径（拆分后的提示词文件）
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "prompts")

# 缓存已加载的提示词配置（按银行类型）
_prompt_config_cache = {}

def load_schema(schema_name: str):
    """
    从配置文件加载指定的 schema
    
    Args:
        schema_name: schema 名称，如 "bank_transaction", "bank_summary"
        
    Returns:
        str: JSON schema 字符串
    """
    if os.path.exists(SCHEMA_CONFIG_PATH):
        with open(SCHEMA_CONFIG_PATH, 'r', encoding='utf-8') as f:
            schemas = json.load(f)
            return json.dumps(schemas.get(schema_name, {}), ensure_ascii=False)
    return "{}"

def load_prompt_config(bank_type: str = "default"):
    """
    加载指定银行类型的提示词配置（带缓存）
    
    Args:
        bank_type: 银行类型，如 "cmb", "everbright", "icbc" 等
        
    Returns:
        dict: 提示词配置字典
    """
    global _prompt_config_cache
    
    if bank_type in _prompt_config_cache:
        return _prompt_config_cache[bank_type]
    
    # 尝试加载银行专属配置
    prompt_file = os.path.join(PROMPTS_DIR, f"{bank_type}.json")
    if os.path.exists(prompt_file):
        with open(prompt_file, 'r', encoding='utf-8') as f:
            _prompt_config_cache[bank_type] = json.load(f)
            return _prompt_config_cache[bank_type]
    
    # 回退到默认配置
    if bank_type != "default":
        return load_prompt_config("default")
    
    return {}

def build_prompt_from_config(config: dict, schema_str: str = None) -> str:
    """
    将配置字典转换为提示词字符串
    
    Args:
        config: 提示词配置字典
        schema_str: 可选的 schema JSON 字符串
        
    Returns:
        str: 格式化后的提示词
    """
    parts = []
    
    # Role
    if "role" in config:
        parts.append(f"Role: {config['role']}")
    
    # Task
    if "task" in config:
        parts.append(f"Task: {config['task']}")
    
    # Special format (for jining)
    if "special_format" in config:
        sf = config["special_format"]
        parts.append(f"\nSpecial Format: {sf.get('description', '')}")
        if "row1" in sf:
            parts.append(f"Row 1: {sf['row1']}")
        if "row2" in sf:
            parts.append(f"Row 2: {sf['row2']}")
    
    # Column order
    if "column_order" in config:
        parts.append(f"\nColumn Order (left to right): {' | '.join(config['column_order'])}")
    
    # Column descriptions
    if "column_descriptions" in config:
        parts.append("\nColumn Descriptions:")
        for col, desc in config["column_descriptions"].items():
            parts.append(f"  - {col}: {desc}")
    
    # Visual guidelines
    if "visual_guidelines" in config:
        vg = config["visual_guidelines"]
        parts.append(f"\nVisual Guidelines: {vg.get('description', '')}")
        if "line_positions" in vg:
            for pos in vg["line_positions"]:
                parts.append(f"  - {pos}")
    
    # Extraction rules
    if "extraction_rules" in config:
        parts.append("\nExtraction Rules:")
        for rule in config["extraction_rules"]:
            if isinstance(rule, dict):
                parts.append(f"  [{rule.get('rule', '')}]")
                for detail in rule.get("details", []):
                    parts.append(f"    - {detail}")
            else:
                parts.append(f"  - {rule}")
    
    # Cross-page handling (for cgb)
    if "cross_page_handling" in config:
        cph = config["cross_page_handling"]
        parts.append(f"\nCross-page Handling: {cph.get('description', '')}")
        if "incomplete_tail" in cph:
            parts.append(f"  - Incomplete Tail: {cph['incomplete_tail']}")
        if "incomplete_head" in cph:
            parts.append(f"  - Incomplete Head: {cph['incomplete_head']}")
        if "complete_record" in cph:
            parts.append(f"  - Complete Record: {cph['complete_record']}")
    
    # Merge rules
    if "merge_rules" in config:
        parts.append("\nMerge Rules:")
        for rule in config["merge_rules"]:
            parts.append(f"  - {rule}")
    
    # Noise filters
    if "noise_filters" in config:
        parts.append("\nNoise Filters:")
        for f in config["noise_filters"]:
            parts.append(f"  - {f}")
    
    # Stop conditions
    if "stop_conditions" in config:
        parts.append("\nStop Conditions:")
        for cond in config["stop_conditions"]:
            parts.append(f"  - {cond}")
    
    # Instructions (for default/simple prompts)
    if "instructions" in config:
        parts.append("\nInstructions:")
        for inst in config["instructions"]:
            parts.append(f"  - {inst}")
    
    # Output constraints
    if "output_constraints" in config:
        parts.append("\nOutput Constraints:")
        for constraint in config["output_constraints"]:
            parts.append(f"  - {constraint}")
    
    # Add schema if provided
    if schema_str:
        parts.append(f"\nJSON Schema to fill:\n{schema_str}")
    
    return "\n".join(parts)

def get_summary_column_x(file_path):
    """
    获取图片中"摘要备注"表头所在的x坐标
    """
    # 从默认配置加载提示词
    config = load_prompt_config("default")
    utility_config = config.get("utility", {}).get("summary_column_x", {})
    
    if utility_config:
        prompt = build_prompt_from_config(utility_config)
    else:
        # 兜底提示词
        prompt = """
        Role: OCR expert
        Task: Identify x-coordinate of 'Memo' or 'Remark' column header center point.
        Return only JSON: {"x": "coordinate_value"} (0-1000 range). No other text.
        """
    
    response = request_qwen35(question=prompt, file_base=file_path).strip()
    try:
        data = json.loads(fix_json(response))
        return data
    except:
        return {"x": "700"} # 默认兜底

def get_real_x_coordinate(file_path, image_path):
    """
    获取"摘要备注"列的真实x坐标位置
    """
    from PIL import Image
    ai_res = get_summary_column_x(file_path)
    try:
        x_percent = int(ai_res.get("x", 700))
        with Image.open(image_path) as img:
            width, _ = img.size
            real_x = int((x_percent / 1000) * width)
            return real_x
    except:
        return 700

def read_data_with_schema(file_path, schema: list, bank_type: str = "shandong_local"):
    """
    使用指定的 schema 从图片中提取交易明细数据
    """
    result_schema = json.dumps(schema, ensure_ascii=False)
    
    # 从银行专属配置文件加载提示词
    config = load_prompt_config(bank_type)
    bank_config = config.get("transaction_extraction", {})
    
    if bank_config:
        prompt = build_prompt_from_config(bank_config, result_schema)
    else:
        # 兜底提示词
        prompt = f"""
        Role: Information extraction expert
        Task: Extract structured data from image based on given JSON schema.
        Instructions:
          - Fill the value part of the schema with information from the image
          - If value is a list, use the schema template for each element
          - Output only valid JSON
          - What you see is what you get
          - Output language must be consistent with the image
          - No explanation required
        
        JSON Schema to fill:
        {result_schema}
        """
    
    rest = request_qwen35(question=prompt,
                          show_request=False,
                          file_base=file_path)
    return rest

def read_data(file_path, schema_name: str = "bank_transaction"):
    """
    使用AI模型从图片中提取数据
    
    Args:
        file_path (str): 图片文件路径
        schema_name (str): schema 配置名称，默认为 "bank_transaction"
        
    Returns:
        str: 提取的JSON数据
    """
    result_schema = load_schema(schema_name)
    
    # 从默认配置文件加载提示词
    config = load_prompt_config("default")
    default_config = config.get("transaction_extraction", {})
    
    if default_config:
        prompt = build_prompt_from_config(default_config, result_schema)
    else:
        prompt = f"""
        Role: Information extraction expert
        Task: Extract structured data from image based on given JSON schema.
        
        JSON Schema to fill:
        {result_schema}
        """
    rest = request_qwen35(question=prompt,
                          show_request=False,
                          file_base=file_path)

    return rest

def process_single_image(args):
    """
    处理单个图片的函数，用于多线程处理
    """
    image_path, results_dir = args
    try:
        filename = os.path.basename(image_path)
        output_path = os.path.join(results_dir, f"{os.path.splitext(filename)[0]}.txt")
        
        # 提取数据
        rest = read_data(image_path)
        
        # 保存结果
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(rest)
        return True
    except Exception as e:
        print(f"处理图片 {os.path.basename(image_path)} 时出错: {e}")
        return False

def process_single_image_with_schema(args):
    """
    处理单个图片的函数（使用指定 schema），用于多线程处理
    """
    image_path, results_dir, schema, bank_type = args
    try:
        filename = os.path.basename(image_path)
        output_path = os.path.join(results_dir, f"{os.path.splitext(filename)[0]}.txt")
        
        # 提取数据
        rest = read_data_with_schema(image_path, schema, bank_type)
        
        # 保存结果
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(rest)
        
        print(f"  ✓ 页面 {filename} 识别完成")
        return True
    except Exception as e:
        print(f"  ✗ 处理图片 {os.path.basename(image_path)} 时出错: {e}")
        return False

def batch_process_images_multithread_with_schema(input_folder, output_folder, schema, bank_type="shandong_local", max_workers=4):
    """
    使用多线程处理文件夹中的所有图片（使用指定 schema）
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    image_files = sorted([f for f in os.listdir(input_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        args_list = [(os.path.join(input_folder, f), output_folder, schema, bank_type) for f in image_files]
        futures = [executor.submit(process_single_image_with_schema, args) for args in args_list]
        concurrent.futures.wait(futures)

def batch_process_images_multithread(input_folder, output_folder, max_workers=4):
    """
    使用多线程处理文件夹中的所有图片
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    image_files = sorted([f for f in os.listdir(input_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        args_list = [(os.path.join(input_folder, f), output_folder) for f in image_files]
        futures = [executor.submit(process_single_image, args) for args in args_list]
        concurrent.futures.wait(futures)

def read_summary_data_with_schema(file_path, schema: dict, bank_type: str):
    """
    使用指定的 schema 从图片中提取汇总数据
    """
    result_schema = json.dumps(schema, ensure_ascii=False)
    
    # 从配置文件加载提示词
    config = load_prompt_config()
    summary_config = config.get("summary_extraction", {})
    
    # 获取对应银行类型的提示词配置，如果没有则使用 default
    bank_config = summary_config.get(bank_type, summary_config.get("default", {}))
    
    if bank_config:
        prompt = build_prompt_from_config(bank_config, result_schema)
    else:
        # 兜底提示词
        prompt = f"""
        Role: Information extraction expert
        Task: Extract structured data from image based on given JSON schema.
        Instructions:
          - Fill the value part of the schema with information from the image
          - Output only valid JSON
          - What you see is what you get
          - Output language must be consistent with the image
          - No explanation required
        
        JSON Schema to fill:
        {result_schema}
        """
        
    response = request_qwen35(question=prompt, file_base=file_path).strip()
    return response

def read_summary_data(file_path, schema_name: str = "bank_summary"):
    """
    从图片中提取汇总数据（仅用于第1页）
    """
    schema_str = load_schema(schema_name)
    # 从配置文件加载提示词
    config = load_prompt_config()
    default_config = config.get("summary_extraction", {}).get("default", {})
    
    if default_config:
        prompt = build_prompt_from_config(default_config, schema_str)
    else:
        prompt = f"Role: Information extraction expert. Task: Extract data from image. Schema: {schema_str}"
    response = request_qwen35(question=prompt, file_base=file_path).strip()
    return response
