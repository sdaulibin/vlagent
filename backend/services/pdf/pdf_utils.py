import os
from pdf2image import convert_from_path
from PIL import Image
import concurrent.futures

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
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 将PDF转换成图片列表
    print(f"正在转换PDF: {pdf_path}")
    images = convert_from_path(pdf_path, dpi=dpi)
    
    image_paths = []
    for i, image in enumerate(images):
        output_filename = f"{os.path.splitext(os.path.basename(pdf_path))[0]}_page_{i+1:03d}.{image_format.lower()}"
        output_path = os.path.join(output_folder, output_filename)
        image.save(output_path, image_format)
        image_paths.append(output_path)
    
    print(f"转换完成，共生成 {len(image_paths)} 张图片")
    return image_paths


def pdf_to_images(pdf_path, max_pages=None, dpi=200):
    """
    将PDF转换为图片（支持限制页数）
    
    Args:
        pdf_path (str): PDF文件路径
        max_pages (int): 最大转换页数，None 表示全部
        dpi (int): 图像分辨率
    
    Returns:
        str: 输出目录路径
    """
    # 创建输出目录
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    output_dir = os.path.join(os.path.dirname(pdf_path), f"task_{base_name}_images")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 转换PDF
    if max_pages:
        images = convert_from_path(pdf_path, dpi=dpi, first_page=1, last_page=max_pages)
    else:
        images = convert_from_path(pdf_path, dpi=dpi)
    
    for i, image in enumerate(images):
        output_filename = f"{base_name}_page_{i+1:03d}.png"
        output_path = os.path.join(output_dir, output_filename)
        image.save(output_path, "PNG")
    
    return output_dir

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
    try:
        with Image.open(input_path) as img:
            # 保持比例缩放
            width, height = img.size
            ratio = min(max_width / width, max_height / height)
            
            if ratio < 1:
                new_size = (int(width * ratio), int(height * ratio))
                # 使用高质量重采样
                img = img.resize(new_size, Image.LANCZOS)
            
            # 确保模式正确（如果是PNG转JPEG，需要转换模式）
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
                
            # 保存并压缩
            img.save(output_path, "JPEG", quality=quality, optimize=True)
            return True
    except Exception as e:
        print(f"处理图片 {os.path.basename(input_path)} 时出错: {e}")
        return False

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
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    image_files = [f for f in os.listdir(input_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    print(f"正在批量压缩 {len(image_files)} 张图片...")
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for filename in image_files:
            input_path = os.path.join(input_folder, filename)
            # 转换扩展名为jpg
            base_name = os.path.splitext(filename)[0]
            output_path = os.path.join(output_folder, f"{base_name}.jpg")
            futures.append(executor.submit(resize_image_high_quality, input_path, output_path, max_width, max_height, quality))
        
        # 等待所有任务完成
        concurrent.futures.wait(futures)
    
    print("批量处理完成\n")
