import os
import concurrent.futures
from PIL import Image, ImageDraw

def add_vertical_lines_to_image(original_image_path, marked_image_path, x_positions):
    """
    在图片的指定x像素位置添加多条黑色垂直线
    """
    try:
        with Image.open(original_image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            draw = ImageDraw.Draw(img)
            width, height = img.size
            
            for x in x_positions:
                try:
                    # 确保是正整数
                    x_pixel = int(float(x))
                    if 0 <= x_pixel <= width:
                        # 绘制黑色垂直线，宽度为2
                        draw.line([(x_pixel, 0), (x_pixel, height)], fill="black", width=2)
                except ValueError:
                    continue
            
            # 保存标记后的图片
            marked_image_path_obj = os.path.dirname(marked_image_path)
            if not os.path.exists(marked_image_path_obj):
                os.makedirs(marked_image_path_obj)
            img.save(marked_image_path, "JPEG", quality=95)
            return True
    except Exception as e:
        print(f"为图片 {os.path.basename(original_image_path)} 添加辅助线时出错: {e}")
        return False

def add_vertical_line_to_image(original_image_path, marked_image_path, x_position):
    """
    向后兼容的单线版本
    """
    return add_vertical_lines_to_image(original_image_path, marked_image_path, [x_position])

def process_single_image_label(args):
    """
    处理单个图片标记的函数，用于多线程处理
    """
    compressed_image_path, labeled_image_path, x_positions = args
    try:
        add_vertical_lines_to_image(compressed_image_path, labeled_image_path, x_positions)
        return True
    except Exception as e:
        print(f"处理图片 {os.path.basename(compressed_image_path)} 时出错: {e}")
        return False

def batch_process_images_label_multithread(compressed_dir, labeled_dir, x_positions, max_workers=4):
    """
    使用多线程处理文件夹中的所有图片标记
    """
    if not os.path.exists(labeled_dir):
        os.makedirs(labeled_dir)
    
    image_files = [f for f in os.listdir(compressed_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        args_list = [(os.path.join(compressed_dir, f), os.path.join(labeled_dir, f), x_positions) for f in image_files]
        futures = [executor.submit(process_single_image_label, args) for args in args_list]
        concurrent.futures.wait(futures)
