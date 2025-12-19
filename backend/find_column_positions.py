"""
根据指定的文件路径和一个或多个 x 轴坐标在图片上绘制黑色垂直辅助线。

用法:
    python find_column_positions.py <图片路径> <x坐标1> <x坐标2> ...

示例:
    python find_column_positions.py input.png 40
    python find_column_positions.py input.png 40 157 401 441
    python find_column_positions.py input.png 0.08 0.36
"""

import sys
import os
from PIL import Image, ImageDraw

def draw_black_vertical_lines(image_path, x_values):
    """
    在图片上的指定 x 坐标处绘制黑色垂直线
    
    Args:
        image_path: 原始图片路径
        x_values: x 轴坐标列表（像素值或 0-1 之间的百分比）
    """
    if not os.path.exists(image_path):
        print(f"错误: 找不到文件 {image_path}")
        return

    try:
        # 打开图片
        img = Image.open(image_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
            
        draw = ImageDraw.Draw(img)
        width, height = img.size
        
        print(f"图片尺寸: {width} x {height}")
        
        for x_str in x_values:
            try:
                # 无论数值大小，全视为绝对像素坐标
                x_pixel = int(float(x_str.strip(',')))
                
                # 绘制黑色垂直线，宽度为2
                draw.line([(x_pixel, 0), (x_pixel, height)], fill="black", width=2)
                print(f"  已在像素 x={x_pixel} 处绘制辅助线")
            except ValueError:
                print(f"  警告: 无效的坐标值 '{x_str}'，跳过")

        # 生成输出路径
        base, ext = os.path.splitext(image_path)
        output_path = f"{base}_marked{ext}"
        
        img.save(output_path)
        print(f"\n处理完成！输出文件: {output_path}")
        
    except Exception as e:
        print(f"处理图片时出错: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
    else:
        # 第一个参数是图片路径，后续所有参数视为坐标
        draw_black_vertical_lines(sys.argv[1], sys.argv[2:])
