import sys
import os
import time
import tempfile
import shutil
from pathlib import Path

# Add backend root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.invoice_recognition.service import _extract_invoice_info
from services.pdf.pdf_utils import split_pdf_to_images


def test_invoice_api(pdf_path: str):
    """提取PDF中每一页发票信息并输出结果（不保存数据库）"""
    if not os.path.exists(pdf_path):
        print(f"❌ 文件不存在: {pdf_path}")
        return

    print("=" * 60)
    print(f"开始测试发票识别: {os.path.basename(pdf_path)}")
    print("=" * 60)

    start_time = time.time()
    tmp_dir = tempfile.mkdtemp(prefix="invoice_test_")
    
    try:
        # 1. 切分PDF
        print("正在进行 PDF 切分...")
        image_paths = split_pdf_to_images(pdf_path, tmp_dir, dpi=200)
        
        if not image_paths:
            print("❌ PDF 转换图片失败，未产生文件。")
            return
            
        print(f"✅ PDF 切分完成，共 {len(image_paths)} 页。开始调用 AI...")
        print("-" * 60)
        
        # 2. 对每页单独识别并打印
        for i, img_path in enumerate(image_paths):
            print(f"  正在分析第 {i + 1} 页...")
            page_data = _extract_invoice_info(img_path)
            
            print(f"  => [第 {i + 1} 页识别结果]:")
            print(f"     发票类型: {page_data.get('invoice_type')}")
            print(f"     金额(价税合计): {page_data.get('invoice_amount')}")
            print(f"     AI 提取耗时: {page_data.get('duration')} 秒")
            if page_data.get("error_msg"):
                print(f"     错误信息: {page_data.get('error_msg')}")
            print("-" * 40)
            
        duration = round(time.time() - start_time, 2)
        print("\n" + "=" * 60)
        print("  ✅ 测试完成 (纯提取，未保存数据库)")
        print("-" * 60)
        print(f"  识别总耗时: {duration} 秒")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 获取期间发生异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: uv run python tests/test_invoice_recognition_rules.py <pdf文件路径>")
        # 提供一个默认的测试路径（如果存在）
        default_path = "/Users/binginx/Desktop/2026年/星辰/运营管理部/50样本/invoice_sample.pdf"
        if os.path.exists(default_path):
            print(f"使用默认测试文件: {default_path}\n")
            test_invoice_api(default_path)
    else:
        pdf_path = sys.argv[1]
        test_invoice_api(pdf_path)
