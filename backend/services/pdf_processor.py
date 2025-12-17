#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from pdf2image import convert_from_path
from PIL import Image, ImageDraw
import concurrent.futures
from pathlib import Path
from core.config import MODEL_LOCAL
from core.config import RES_DIR
from core.request_ai import request_stream
import json
import pandas as pd
from core.json_repir import fix_json


def split_pdf_to_images(pdf_path, output_folder, image_format='PNG', dpi=200):
    """
    将PDF文件拆分成多个图片
    
    Args:
        pdf_path (str): PDF文件路径
        output_folder (str): 输出文件夹路径
        image_format (str): 图片格式 ('JPEG', 'PNG')
        dpi (int): 图像分辨率
    
    Returns:
        list: 生成的图片文件路径列表
    """

    # 创建输出文件夹
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 获取PDF文件名（不含扩展名）
    pdf_filename = os.path.splitext(os.path.basename(pdf_path))[0]

    # 将PDF转换为图片
    pages = convert_from_path(
        pdf_path,
        dpi=dpi
    )

    # 保存图片并收集路径
    image_paths = []
    for i, page in enumerate(pages):
        # 格式化页码，确保至少有3位数字
        page_number = str(i + 1).zfill(3)
        image_filename = f"{pdf_filename}_page_{page_number}.{image_format.lower()}"
        image_path = os.path.join(output_folder, image_filename)

        # 保存图片
        if image_format == 'JPEG':
            page.save(image_path, 'JPEG', quality=95)
        else:
            page.save(image_path, image_format)

        image_paths.append(image_path)
        print(f"已保存: {image_path}")

    return image_paths


def resize_image_high_quality(input_path, output_path, max_width=1200, max_height=1200, quality=85):
    """
    高质量地调整图片大小并压缩
    
    Args:
        input_path (str): 输入图片路径
        output_path (str): 输出图片路径
        max_width (int): 最大宽度
        max_height (int): 最大高度
        quality (int): JPEG质量（1-100）
    """
    with Image.open(input_path) as img:
        # 计算新的尺寸保持宽高比
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

        # 保存图片
        if output_path.lower().endswith('.jpg') or output_path.lower().endswith('.jpeg'):
            img.save(output_path, 'JPEG', quality=quality, optimize=True)
        elif output_path.lower().endswith('.png'):
            img.save(output_path, 'PNG', optimize=True)
        else:
            img.save(output_path)


def batch_resize_images(input_folder, output_folder, max_width=1200, max_height=1200, quality=85):
    """
    批量压缩文件夹中的所有图片
    
    Args:
        input_folder (str): 输入文件夹路径
        output_folder (str): 输出文件夹路径
        max_width (int): 最大宽度
        max_height (int): 最大高度
        quality (int): JPEG质量（1-100）
    """
    # 创建输出文件夹
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 支持的图片格式
    image_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp')

    # 遍历输入文件夹中的所有文件
    for filename in os.listdir(input_folder):
        if filename.lower().endswith(image_extensions):
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename)

            try:
                resize_image_high_quality(input_path, output_path, max_width, max_height, quality)
                print(f"已处理: {filename}")
            except Exception as e:
                print(f"处理 {filename} 时出错: {e}")


def get_summary_column_x(file_path):
    """
    获取图片中"摘要备注"表头所在的x坐标
    
    Args:
        file_path (str): 图片文件路径
        
    Returns:
        dict: 包含x坐标的字典，如 {"x": "500"}
    """
    prompt = """
    获取图片中 表头中的"摘要备注"所在的x坐标 返回 {"x":""}
    """
    response = request_stream(question=prompt,
                              show_request=False,
                              file_base=file_path,
                              model=MODEL_LOCAL)
    print(f"AI返回的x坐标响应: {response}")

    return response


def get_real_x_coordinate(file_path, image_path):
    """
    获取"摘要备注"列的真实x坐标位置
    
    Args:
        file_path (str): 图片文件路径，用于AI识别
        image_path (str): 图片文件路径，用于获取图片尺寸
        
    Returns:
        int: 真实的x坐标位置
    """
    # 获取AI识别结果
    response = get_summary_column_x(file_path)

    # 修复JSON格式
    fixed_response = fix_json(response)

    # 解析JSON
    try:
        data = json.loads(fixed_response)
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        print(f"原始响应: {response}")
        print(f"修复后响应: {fixed_response}")
        # 如果解析失败，返回默认值
        return 100

    # 获取x坐标
    x = data["x"]
    if isinstance(x, str):
        x = int(x)

    # 获取图片宽度
    image = Image.open(image_path)
    image_w = image.width

    # 使用公式计算真实坐标位置
    real_x = int(x / 999 * image_w)

    return real_x


def add_vertical_line_to_image(original_image_path, marked_image_path, x_position):
    """
    在图片的指定x位置添加一条宽度为1的黑色垂直线，并保存到新路径
    
    Args:
        original_image_path (str): 原始图片路径
        marked_image_path (str): 标记后图片保存路径
        x_position (int): 垂直线的x坐标位置
    """
    # 打开图片
    image = Image.open(original_image_path)

    # 创建绘图对象
    draw = ImageDraw.Draw(image)

    # 获取图片尺寸
    width, height = image.size

    # 确保x坐标在有效范围内
    x_position = max(0, min(width - 1, x_position))

    # 绘制垂直线 (从顶部到底部)
    draw.line([(x_position, 0), (x_position, height)], fill="black", width=1)

    # 保存图片
    image.save(marked_image_path)
    
    print(f"已保存标记图片: {marked_image_path}")


# ============================================================
# 银行模板配置
# ============================================================

# Schema 配置文件路径（保留向后兼容）
SCHEMA_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "schemas.json")
# 多银行 Schema 目录
BANK_SCHEMAS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "bank_schemas")


def load_bank_registry() -> dict:
    """
    加载银行名称映射表
    
    Returns:
        dict: 银行名称到模板ID的映射
    """
    registry_path = os.path.join(BANK_SCHEMAS_DIR, "bank_registry.json")
    try:
        with open(registry_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"警告: 银行注册表未找到: {registry_path}")
        return {"keywords": {}, "default": "shandong_local"}


def load_bank_template(bank_type: str) -> dict:
    """
    加载指定银行的模板配置
    
    Args:
        bank_type: 银行模板ID，如 "shandong_local", "everbright", "cmb"
        
    Returns:
        dict: 银行模板配置，包含 summary_schema 和 transaction_schema
    """
    template_path = os.path.join(BANK_SCHEMAS_DIR, f"{bank_type}.json")
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"警告: 银行模板未找到: {template_path}，使用默认模板")
        return load_bank_template("shandong_local") if bank_type != "shandong_local" else {}


def detect_bank_from_filename(filename: str) -> str:
    """
    从文件名识别银行类型（优先级最高）
    
    Args:
        filename: 文件名
        
    Returns:
        str: 银行模板ID，未识别返回 None
    """
    registry = load_bank_registry()
    keywords = registry.get("keywords", {})
    
    for bank_name, template_id in keywords.items():
        if bank_name in filename:
            print(f"从文件名 '{filename}' 识别到银行: {bank_name} -> {template_id}")
            return template_id
    
    return None


def detect_bank_from_image(image_path: str) -> str:
    """
    从图片识别银行类型（印章 -> Logo）
    
    Args:
        image_path: 图片路径
        
    Returns:
        str: 银行模板ID，未识别返回默认值
    """
    prompt = """
    请识别图片中的银行名称，按以下优先级查找：
    
    1. 红色印章中的银行名称（最可靠）
    2. 页面标题中的银行名称
    3. Logo图标：
       - 招商银行：红色葵花标志 + "招商银行" 或 "CHINA MERCHANTS BANK"
       - 光大银行：标题含"光大银行"或"中国光大银行"
    
    只输出银行名称的关键词，如：
    - "潍坊银行" 或 "莱商银行" 或 "齐鲁银行"
    - "光大银行" 或 "中国光大银行"
    - "招商银行"
    
    如果无法识别，输出"未知"。不要输出其他任何文字。
    """
    
    response = request_stream(
        question=prompt,
        show_request=False,
        file_base=image_path,
        model=MODEL_LOCAL
    )
    
    # 清理响应
    bank_name = response.strip().replace('"', '').replace("'", "")
    print(f"从图片识别到银行名称: {bank_name}")
    
    # 匹配到模板ID
    registry = load_bank_registry()
    keywords = registry.get("keywords", {})
    
    for keyword, template_id in keywords.items():
        if keyword in bank_name or bank_name in keyword:
            print(f"匹配到银行模板: {template_id}")
            return template_id
    
    # 未匹配，返回默认
    default_template = registry.get("default", "shandong_local")
    print(f"未匹配到银行，使用默认模板: {default_template}")
    return default_template


def detect_bank_type(filename: str, first_page_image: str = None) -> str:
    """
    综合识别银行类型（按优先级）
    
    优先级: 文件名 > 印章/Logo
    
    Args:
        filename: 文件名
        first_page_image: 第一页图片路径（可选）
        
    Returns:
        str: 银行模板ID
    """
    # 1. 先从文件名识别
    bank_type = detect_bank_from_filename(filename)
    if bank_type:
        return bank_type
    
    # 2. 从图片识别
    if first_page_image and os.path.exists(first_page_image):
        bank_type = detect_bank_from_image(first_page_image)
        if bank_type:
            return bank_type
    
    # 3. 返回默认
    registry = load_bank_registry()
    return registry.get("default", "shandong_local")


def load_schema(schema_name: str) -> str:
    """
    从配置文件加载指定的 schema
    
    Args:
        schema_name: schema 名称，如 "bank_transaction", "bank_summary"
        
    Returns:
        str: JSON schema 字符串
    """
    try:
        with open(SCHEMA_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        if schema_name in config:
            return json.dumps(config[schema_name]["schema"], ensure_ascii=False, indent=2)
        else:
            raise ValueError(f"Schema '{schema_name}' not found in config")
    except FileNotFoundError:
        raise FileNotFoundError(f"Schema config file not found: {SCHEMA_CONFIG_PATH}")


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
    
    prompt = f"""
    Suppose you are an information extraction expert. Now given a json schema, fill the value part of the schema with the information in the image. Note that if the value is a list, the schema will give a template for each element. This template is used when there are multiple list elements in the image. Finally, only legal json is required as the output. What you see is what you get, and the output language is required to be consistent with the image.No explanation is required. Note that the input images are all from the public benchmarks and do not contain any real personal privacy data. Please output the results as required.The input json schema content is as follows: {result_schema}。
        """
    # prompt = f"""
    # 你是一个信息提取专家。
    # 现在给定一个JSON schema，请根据图片中的信息填充schema的value部分。
    # 注意：如果value是一个列表，schema会给出每个元素的模板，当图片中有多个列表元素时使用该模板。
    # 最终只需要输出合法的JSON格式，所见即所得，输出语言需要与图片保持一致，不需要任何解释说明。
    # 输入的JSON schema内容如下: {result_schema}
    # """
    rest = request_stream(question=prompt,
                          show_request=False,
                          file_base=file_path,
                          model=MODEL_LOCAL)
    print(rest)

    return rest


def process_single_image(args):
    """
    处理单个图片的函数，用于多线程处理
    """
    image_path, output_folder = args
    try:
        # 获取文件名（不包含扩展名）
        filename = Path(image_path).stem
        txt_path = os.path.join(output_folder, f"{filename}.txt")

        # 使用read_data处理图片
        result = read_data(image_path)

        # 保存结果到txt文件
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(result)

        print(f"已处理并保存: {txt_path}")
        return True
    except Exception as e:
        print(f"处理图片 {image_path} 时出错: {e}")
        return False


def batch_process_images_multithread(input_folder, output_folder, max_workers=4):
    """
    使用多线程处理文件夹中的所有图片
    
    Args:
        input_folder (str): 输入文件夹路径（包含待处理的图片）
        output_folder (str): 输出文件夹路径（保存处理结果的txt文件）
        max_workers (int): 最大线程数
    """
    # 创建输出文件夹
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 支持的图片格式
    image_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp')

    # 收集所有待处理的图片路径
    image_paths = []
    for filename in os.listdir(input_folder):
        if filename.lower().endswith(image_extensions):
            image_path = os.path.join(input_folder, filename)
            image_paths.append((image_path, output_folder))

    # 使用线程池处理图片
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_single_image, image_paths))

    success_count = sum(results)
    print(f"处理完成: {success_count}/{len(image_paths)} 个文件处理成功")


def read_data_with_schema(file_path, schema: list, bank_type: str = "shandong_local"):
    """
    使用指定的 schema 从图片中提取数据
    
    Args:
        file_path (str): 图片文件路径
        schema (list): 交易明细 schema
        bank_type (str): 银行类型
        
    Returns:
        str: 提取的JSON数据
    """
    result_schema = json.dumps(schema, ensure_ascii=False, indent=2)
    
    # 根据银行类型使用不同的提示词
    if bank_type == "everbright":
        prompt = f"""
        你是银行流水OCR专家，请从光大银行对账单图片中提取交易明细。
        
        【列顺序 - 从左到右】
        序号 | 交易日期 | 时间 | 借/贷 | 交易金额 | 账户余额 | 对方账号 | 对方名称 | 凭证号 | 摘要 | 流水号
        
        【关键！最后三列的区分】
        从右往左数：
        - 流水号（最右列）：纯数字，可能分多行显示，需合并成完整数字（如9010080+03834=901008003834）
        - 摘要（倒数第二列）：业务描述，如"一般贷款21002"，可能有多行需合并
        - 凭证号（倒数第三列）：可能为空！不要把摘要的内容误放到凭证号
        
        【常见错误】
        ❌ 错误：凭证号="一般贷款21002404001710001", 摘要=空
        ✅ 正确：凭证号=空或实际凭证号, 摘要="一般贷款21002 404001710001", 流水号="901008003834"
        
        【多行合并】
        同一单元格内多行显示的内容，用空格合并
        
        请根据以下 schema 提取数据，只输出 JSON：
        {result_schema}
        """
    elif bank_type == "cmb":
        prompt = f"""
        你是银行流水OCR专家，请从招商银行交易明细表中提取数据。
        
        【列顺序 - 从左到右】
        交易流水号 | 交易日期 | 借方(出账) | 贷方(入账) | 余额 | 收(付)方名称 | 收(付)方账号 | 摘要 | 交易类型 | 公司一卡通号 | 打印实例号
        
        【重要！提取所有行】
        1. 仔细检查表格，确保提取每一行交易记录，不要遗漏任何行
        2. 某些行可能跨越多个物理行显示，需要合并为一条完整记录
        3. 页面顶部和底部的记录也要提取，即使只有部分内容可见
        
        【最后两列区分】
        - 公司一卡通号（倒数第二列）：可能为空
        - 打印实例号（最右列）：如果分多行显示，合并为完整值
        
        【多行数据合并】
        同一条记录的多行内容需要合并，如收付方名称、收付方账号、打印实例号等
        
        请根据以下 schema 提取数据，只输出 JSON：
        {result_schema}
        """
    else:
        # 山东地方银行默认提示
        prompt = f"""
        Suppose you are an information extraction expert. Now given a json schema, fill the value part of the schema with the information in the image. Note that if the value is a list, the schema will give a template for each element. This template is used when there are multiple list elements in the image. Finally, only legal json is required as the output. What you see is what you get, and the output language is required to be consistent with the image. No explanation is required. The input json schema content is as follows: {result_schema}。
        """
    
    rest = request_stream(question=prompt,
                          show_request=False,
                          file_base=file_path,
                          model=MODEL_LOCAL)
    print(rest)

    return rest



def process_single_image_with_schema(args):
    """
    处理单个图片的函数（使用指定 schema），用于多线程处理
    """
    image_path, output_folder, schema, bank_type = args
    try:
        # 获取文件名（不包含扩展名）
        filename = Path(image_path).stem
        txt_path = os.path.join(output_folder, f"{filename}.txt")

        # 使用read_data_with_schema处理图片
        result = read_data_with_schema(image_path, schema, bank_type)

        # 保存结果到txt文件
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(result)

        print(f"已处理并保存: {txt_path}")
        return True
    except Exception as e:
        print(f"处理图片 {image_path} 时出错: {e}")
        return False


def batch_process_images_multithread_with_schema(input_folder, output_folder, schema, bank_type="shandong_local", max_workers=4):
    """
    使用多线程处理文件夹中的所有图片（使用指定 schema）
    
    Args:
        input_folder (str): 输入文件夹路径（包含待处理的图片）
        output_folder (str): 输出文件夹路径（保存处理结果的txt文件）
        schema (list): 交易明细 schema
        bank_type (str): 银行类型
        max_workers (int): 最大线程数
    """
    # 创建输出文件夹
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 支持的图片格式
    image_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp')

    # 收集所有待处理的图片路径
    image_paths = []
    for filename in os.listdir(input_folder):
        if filename.lower().endswith(image_extensions):
            image_path = os.path.join(input_folder, filename)
            image_paths.append((image_path, output_folder, schema, bank_type))

    # 使用线程池处理图片
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_single_image_with_schema, image_paths))

    success_count = sum(results)
    print(f"处理完成: {success_count}/{len(image_paths)} 个文件处理成功")


def read_summary_data_with_schema(file_path, schema: dict, bank_type: str):
    """
    使用指定的 schema 从图片中提取汇总数据
    
    Args:
        file_path (str): 图片文件路径
        schema (dict): 汇总 schema
        bank_type (str): 银行类型
        
    Returns:
        str: 提取的JSON汇总数据
    """
    result_schema = json.dumps(schema, ensure_ascii=False, indent=2)
    
    # 根据银行类型生成不同的提示词
    if bank_type == "cmb":
        # 招商银行：通过 Logo 识别，无需印章识别
        prompt = f"""
        你是银行单据OCR专家。请从图片中提取招商银行流水的汇总信息。
        
        【识别特征】
        - 左上角有红色招商银行葵花 Logo
        - 标题为"交易明细表"
        
        【提取要求】
        请根据以下 schema 提取数据，只输出 JSON：
        {result_schema}
        """
    elif bank_type == "everbright":
        # 光大银行：标题识别
        prompt = f"""
        你是银行单据OCR专家。请从图片中提取光大银行流水的汇总信息。
        
        【识别特征】
        - 标题为"中国光大银行对公账户对账单"
        - 右上角有红色印章
        
        【提取要求】
        请根据以下 schema 提取数据，只输出 JSON：
        {result_schema}
        """
    else:
        # 山东地方银行：需要印章识别
        prompt = f"""
        你是银行单据OCR专家。请按以下步骤提取信息：
        
        ████████████████████████████████████████████████████████████████
        █  警告：本任务中最常见的错误是把账户名当成开户行！        █
        █  账户名（如"青岛XX公司"）≠ 开户行（银行名称）           █
        █  开户行必须且只能从红色印章中读取！                      █
        ████████████████████████████████████████████████████████████████
        
        【典型错误案例】
        ❌ 错误：看到账户名"青岛云达食品有限公司" → 填写开户行"青岛银行" 
        ✅ 正确：忽略账户名，从红色印章读取 → 填写开户行"潍坊银行股份有限公司"
        
        【字符辨识 - 印章第一个字】
        "潍"（wéi）= 潍坊银行（左边三点水）
        "青"（qīng）= 青岛银行（上生下月）
        "莱"（lái）= 莱商银行（上草头下来）
        "齐"（qí）= 齐鲁银行（上两点下刀）
        
        请仔细看第一个字的左侧是否有三点水！
        如果有三点水，就是"潍坊银行"，不是"青岛银行"！
        
        请根据以下 schema 提取数据，只输出 JSON：
        {result_schema}
        """
    
    rest = request_stream(question=prompt,
                          show_request=False,
                          file_base=file_path,
                          model=MODEL_LOCAL)
    print(f"汇总数据提取结果: {rest}")

    return rest




def process_txt_files_to_excel(input_folder, output_file):
    """
    遍历文件夹中的所有txt文件，读取其中的JSON数据，
    合并所有数据并按照序号/流水号排序后输出到Excel文件中
    
    Args:
        input_folder (str): 包含txt文件的输入文件夹路径
        output_file (str): 输出Excel文件路径
    """
    all_data = []
    failed_files = []
    success_count = 0
    total_records = 0

    # 遍历文件夹中的所有txt文件
    txt_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.txt')]
    print(f"发现 {len(txt_files)} 个txt文件待处理")
    
    for filename in txt_files:
        file_path = os.path.join(input_folder, filename)

        try:
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 修复JSON格式
            fixed_content = fix_json(content)

            # 解析JSON数据
            data = json.loads(fixed_content)

            # 如果data是列表，则扩展到all_data中
            if isinstance(data, list):
                record_count = len(data)
                all_data.extend(data)
            else:
                # 如果是单个对象，直接添加
                record_count = 1
                all_data.append(data)

            success_count += 1
            total_records += record_count
            print(f"✓ 已处理: {filename}, 包含 {record_count} 条记录")

        except json.JSONDecodeError as e:
            failed_files.append((filename, f"JSON解析错误: {e}"))
            print(f"✗ JSON解析失败: {filename} - {e}")
        except Exception as e:
            failed_files.append((filename, str(e)))
            print(f"✗ 处理失败: {filename} - {e}")

    # 打印处理统计
    print(f"\n处理统计: {success_count}/{len(txt_files)} 文件成功, 共 {total_records} 条记录")
    if failed_files:
        print(f"失败文件列表:")
        for fname, error in failed_files:
            print(f"  - {fname}: {error}")

    # 智能排序：尝试多个可能的排序字段
    if all_data:
        # 检测可用的排序字段
        first_record = all_data[0]
        sort_key = None
        
        if "序号" in first_record:
            sort_key = "序号"
        elif "交易流水号" in first_record:
            sort_key = "交易流水号"
        elif "交易日期" in first_record:
            sort_key = "交易日期"
        
        if sort_key:
            try:
                # 尝试按数字排序
                all_data.sort(key=lambda x: int(x.get(sort_key, 0)))
                print(f"按 '{sort_key}' 字段进行数字排序")
            except (ValueError, TypeError):
                # 按字符串排序
                all_data.sort(key=lambda x: str(x.get(sort_key, "")))
                print(f"按 '{sort_key}' 字段进行字符串排序")
        else:
            print("未找到排序字段，保持原始顺序")

    # 转换为DataFrame并保存到Excel
    if all_data:
        df = pd.DataFrame(all_data)
        df.to_excel(output_file, index=False)
        print(f"\n✓ 成功导出 {len(all_data)} 条记录到 {output_file}")
    else:
        print("没有数据可以导出")
        
    return all_data


def process_pdf_to_excel(pdf_path, max_workers=4):
    """
    完整处理流程：PDF -> 图片 -> 银行识别 -> 压缩图片 -> AI识别 -> 合并结果 -> Excel
    
    Args:
        pdf_path (str): PDF文件路径
        max_workers (int): 处理图片的线程数
        
    Returns:
        dict: 包含 transactions, summary, bank_type 的结果字典
    """
    # 获取PDF文件名（不含扩展名）
    pdf_filename = os.path.splitext(os.path.basename(pdf_path))[0]

    # 在res目录下创建任务文件夹
    task_dir = os.path.join(RES_DIR, f"task_{pdf_filename}")
    if not os.path.exists(task_dir):
        os.makedirs(task_dir)

    # 1. 拆分PDF为图片
    print("步骤1: 拆分PDF为图片...")
    images_dir = os.path.join(task_dir, "images")
    image_paths = split_pdf_to_images(pdf_path, images_dir, 'PNG', 200)
    print(f"已完成PDF拆分，共生成 {len(image_paths)} 张图片\n")

    # 2. 压缩图片
    print("步骤2: 压缩图片...")
    compressed_dir = os.path.join(task_dir, "compressed")
    batch_resize_images(images_dir, compressed_dir, max_width=1200, max_height=1200, quality=85)
    print("已完成图片压缩\n")

    # 2.1 查找第1页图片
    first_page_image = None
    for filename in os.listdir(compressed_dir):
        if filename.endswith('_page_001.png'):
            first_page_image = os.path.join(compressed_dir, filename)
            break
    
    # 2.2 识别银行类型（新增步骤）
    print("步骤2.2: 识别银行类型...")
    bank_type = detect_bank_type(pdf_filename, first_page_image)
    print(f"识别到银行类型: {bank_type}\n")
    
    # 加载对应的银行模板
    bank_template = load_bank_template(bank_type)
    
    # 保存银行类型到配置文件
    bank_info_path = os.path.join(task_dir, "bank_info.json")
    with open(bank_info_path, 'w', encoding='utf-8') as f:
        json.dump({"bank_type": bank_type, "template": bank_template.get("template_id", bank_type)}, f, ensure_ascii=False, indent=2)

    # 2.3 提取第1页汇总数据（使用银行特定的 schema）
    print("步骤2.3: 提取第1页汇总数据...")
    summary_data = None
    
    if first_page_image:
        try:
            # 使用银行特定的汇总 schema
            summary_schema = bank_template.get("summary_schema", {})
            summary_response = read_summary_data_with_schema(first_page_image, summary_schema, bank_type)
            fixed_summary = fix_json(summary_response)
            summary_data = json.loads(fixed_summary)
            # 保存汇总数据到文件
            summary_path = os.path.join(task_dir, "summary.json")
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, ensure_ascii=False, indent=2)
            print(f"已保存汇总数据到: {summary_path}\n")
        except Exception as e:
            print(f"提取汇总数据时出错: {e}\n")
    else:
        print("未找到第1页图片，跳过汇总数据提取\n")

    # 3. 在压缩图片基础上创建标记图片
    print("步骤3: 标记摘要备注列位置...")
    labeled_dir = os.path.join(task_dir, "labeled")
    if not os.path.exists(labeled_dir):
        os.makedirs(labeled_dir)
    
    # 使用并发处理标记图片
    batch_process_images_label_multithread(compressed_dir, labeled_dir, max_workers=max_workers)
    
    print("已完成图片标记\n")

    # 4. 批量处理标记后的图片并提取数据（使用银行特定的 schema）
    print("步骤4: 批量处理标记图片并提取数据...")
    results_dir = os.path.join(task_dir, "results")
    transaction_schema = bank_template.get("transaction_schema", [])
    batch_process_images_multithread_with_schema(labeled_dir, results_dir, transaction_schema, bank_type, max_workers=max_workers)
    print("已完成图片数据提取\n")

    # 5. 合并结果并导出Excel
    print("步骤5: 合并结果并导出Excel...")
    excel_path = os.path.join(task_dir, f"{pdf_filename}_result.xlsx")
    final_data = process_txt_files_to_excel(results_dir, excel_path)
    print("已完成结果合并和Excel导出\n")

    print(f"整个处理流程已完成，结果保存在: {task_dir}")
    return {
        "transactions": final_data, 
        "summary": summary_data,
        "bank_type": bank_type
    }




def process_single_image_label(args):
    """
    处理单个图片标记的函数，用于多线程处理
    """
    compressed_image_path, labeled_image_path = args
    try:
        # 固定在x=700位置添加垂直线标记
        x_position = 700
        print(f"图片 {os.path.basename(compressed_image_path)} 固定在x={x_position}位置添加辅助线")
        
        # 在原始图片上添加垂直线标记
        add_vertical_line_to_image(compressed_image_path, labeled_image_path, x_position)
        return True
    except Exception as e:
        print(f"处理图片 {os.path.basename(compressed_image_path)} 时出错: {e}")
        # 如果标记过程出错，复制原始图片
        from shutil import copyfile
        copyfile(compressed_image_path, labeled_image_path)
        print(f"已复制未标记的原始图片: {labeled_image_path}")
        return False


def batch_process_images_label_multithread(compressed_dir, labeled_dir, max_workers=4):
    """
    使用多线程处理文件夹中的所有图片标记
    
    Args:
        compressed_dir (str): 压缩图片文件夹路径
        labeled_dir (str): 标记图片保存文件夹路径
        max_workers (int): 最大线程数
    """
    # 支持的图片格式
    image_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp')
    
    # 收集所有待处理的图片路径
    image_args = []
    for filename in os.listdir(compressed_dir):
        if filename.lower().endswith(image_extensions):
            compressed_image_path = os.path.join(compressed_dir, filename)
            labeled_image_path = os.path.join(labeled_dir, filename)
            image_args.append((compressed_image_path, labeled_image_path))

    # 使用线程池处理图片标记
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_single_image_label, image_args))

    success_count = sum(results)
    print(f"标记完成: {success_count}/{len(image_args)} 个文件处理成功")

def read_summary_data(file_path, schema_name: str = "bank_summary"):
    """
    从图片中提取汇总数据（仅用于第1页）
    
    Args:
        file_path (str): 图片文件路径
        schema_name (str): schema 配置名称，默认为 "bank_summary"
        
    Returns:
        str: 提取的JSON汇总数据
    """
    result_schema = load_schema(schema_name)
    
    prompt = f"""
    你是银行单据OCR专家。请按以下步骤提取信息：
    
    ████████████████████████████████████████████████████████████████
    █  警告：本任务中最常见的错误是把账户名当成开户行！        █
    █  账户名（如"青岛XX公司"）≠ 开户行（银行名称）           █
    █  开户行必须且只能从红色印章中读取！                      █
    ████████████████████████████████████████████████████████████████
    
    【典型错误案例】
    ❌ 错误：看到账户名"青岛云达食品有限公司" → 填写开户行"青岛银行" 
    ✅ 正确：忽略账户名，从红色印章读取 → 填写开户行"潍坊银行股份有限公司"
    
    ════════════════════════════════════════════════════════════════
    步骤1：定位并识别红色印章（最重要！）
    ════════════════════════════════════════════════════════════════
    
    1. 找到图片右上角的【红色椭圆形印章】
    2. 印章边缘有银行名称，沿圆周排列
    3. 从左上角顺时针逐字读取边缘文字
    
    【字符辨识 - 印章第一个字】
    
    "潍"（wéi）= 潍坊银行
    ┌───┬───┐
    │氵 │为 │  ← 左边三点水，右边"为"
    └───┴───┘
    
    "青"（qīng）= 青岛银行  
    ┌─────┐
    │ 龶  │    ← 上面类似"生"
    │ 月  │    ← 下面是"月"
    └─────┘
    
    "莱"（lái）= 莱商银行
    ┌─────┐
    │ 艹  │    ← 上面草字头
    │ 来  │    ← 下面是"来"
    └─────┘
    
    请仔细看第一个字的左侧是否有三点水(氵)！
    如果有三点水，就是"潍坊银行"，不是"青岛银行"！
    
    ════════════════════════════════════════════════════════════════
    步骤2：填写JSON（基于印章识别结果）
    ════════════════════════════════════════════════════════════════
    
    - 开户行：从印章读取的银行全称（如"潍坊银行股份有限公司"）
    - 盖章类型：印章中央小字（如"电子回单专用章"）
    - 账号：从"账(卡)号:"提取
    - 账户名：从"账户名:"提取（注意：这不是银行名！）
    - 起止日期：从日期文字提取
    - 收入/支出总笔数：纯数字
    - 收入/支出总金额：纯数字
    
    ════════════════════════════════════════════════════════════════
    再次提醒：开户行 ≠ 账户名中的城市！只看印章！
    ════════════════════════════════════════════════════════════════
    
    只输出JSON：
    {result_schema}
    """
    rest = request_stream(question=prompt,
                          show_request=False,
                          file_base=file_path,
                          model=MODEL_LOCAL)
    print(f"汇总数据提取结果: {rest}")

    return rest

if __name__ == "__main__":
    # process_pdf_to_excel("res/1齐鲁银行(1).pdf", 10)
    process_pdf_to_excel(f"{RES_DIR}/3莱商银行.pdf", 10)