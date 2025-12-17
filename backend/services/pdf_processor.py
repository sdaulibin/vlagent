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


# Schema 配置文件路径
SCHEMA_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "schemas.json")


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


def process_txt_files_to_excel(input_folder, output_file):
    """
    遍历文件夹中的所有txt文件，读取其中的JSON数据，
    合并所有数据并按照"序号"排序后输出到Excel文件中
    
    Args:
        input_folder (str): 包含txt文件的输入文件夹路径
        output_file (str): 输出Excel文件路径
    """
    all_data = []

    # 遍历文件夹中的所有txt文件
    for filename in os.listdir(input_folder):
        if filename.lower().endswith('.txt'):
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
                    all_data.extend(data)
                else:
                    # 如果是单个对象，直接添加
                    all_data.append(data)

                print(f"已处理文件: {filename}, 包含 {len(data) if isinstance(data, list) else 1} 条记录")

            except json.JSONDecodeError as e:
                print(f"解析文件 {filename} 中的JSON时出错: {e}")
            except Exception as e:
                print(f"处理文件 {filename} 时出错: {e}")

    # 按照"序号"排序
    try:
        # 确保序号是整数类型以便正确排序
        all_data.sort(key=lambda x: int(x.get("序号", 0)))
    except ValueError:
        # 如果序号不是数字，按字符串排序
        all_data.sort(key=lambda x: x.get("序号", ""))

    # 转换为DataFrame并保存到Excel
    if all_data:
        df = pd.DataFrame(all_data)
        df.to_excel(output_file, index=False)
        print(f"成功导出 {len(all_data)} 条记录到 {output_file}")
    else:
        print("没有数据可以导出")
        
    return all_data


def process_pdf_to_excel(pdf_path, max_workers=4):
    """
    完整处理流程：PDF -> 图片 -> 压缩图片 -> AI识别 -> 合并结果 -> Excel
    
    Args:
        pdf_path (str): PDF文件路径
        max_workers (int): 处理图片的线程数
        
    Returns:
        list: 识别出的交易数据列表
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

    # 2.1 提取第1页汇总数据
    print("步骤2.1: 提取第1页汇总数据...")
    summary_data = None
    # 查找第1页图片
    first_page_image = None
    for filename in os.listdir(compressed_dir):
        if filename.endswith('_page_001.png'):
            first_page_image = os.path.join(compressed_dir, filename)
            break
    
    if first_page_image:
        try:
            summary_response = read_summary_data(first_page_image)
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

    # 4. 批量处理标记后的图片并提取数据
    print("步骤4: 批量处理标记图片并提取数据...")
    results_dir = os.path.join(task_dir, "results")
    batch_process_images_multithread(labeled_dir, results_dir, max_workers=max_workers)
    print("已完成图片数据提取\n")

    # 5. 合并结果并导出Excel
    print("步骤5: 合并结果并导出Excel...")
    excel_path = os.path.join(task_dir, f"{pdf_filename}_result.xlsx")
    final_data = process_txt_files_to_excel(results_dir, excel_path)
    print("已完成结果合并和Excel导出\n")

    print(f"整个处理流程已完成，结果保存在: {task_dir}")
    return {"transactions": final_data, "summary": summary_data}




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
    你是一个信息提取专家。请从图片中提取银行流水的汇总信息，并按照给定的JSON schema填充。
    
    关于数值字段的特别说明：
    - "收入总笔数"和"支出总笔数"：只输出纯数字，如 "5"，不要带"笔"等单位
    - "收入总金额"和"支出总金额"：只输出纯金额数字，如 "12345.67"，不要带货币符号或"元"等单位
    
    【印章识别 - 重要指引】
    这是最关键的部分，请务必仔细执行：
    
    1. **仔细阅读印章文字**：
       - 印章通常是红色圆形或椭圆形图案
       - 请逐字阅读印章内部的所有文字（通常沿边缘排列）
       - 印章格式通常为 "XXX银行股份有限公司" 或 "XXX银行XXX分行"
    
    2. **"开户行"字段填写规则**（按优先级）：
       - 【最高优先级】直接从印章内部文字提取银行名称
       - 【次优先级】从文档标题或表头提取银行名称
       - 【禁止】不要凭印象或猜测填写常见银行名称（如工商银行、建设银行等）
    
    3. **常见印章银行名称示例**：
       - 潍坊银行股份有限公司
       - 青岛银行股份有限公司
       - 莱商银行股份有限公司
       - 齐鲁银行股份有限公司
       （注意：不要把地方银行误认为是全国性大银行）
    
    4. **"盖章类型"字段**：
       - 常见值："电子回单专用章"、"业务专用章"、"公章"
       - 请从印章底部或中央的小字提取
    
    只输出合法的JSON格式，不需要任何解释。如果某个字段在图片中找不到，请填写空字符串。
    JSON schema如下: {result_schema}
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