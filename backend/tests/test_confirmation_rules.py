import sys
import os
import json
import time
from pathlib import Path

# Add backend root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.confirmation_compare.service import compare_with_template


def test_compare_api(pdf_path: str):
    """模拟 API 接口调用，测试格式比对功能并输出结果"""
    if not os.path.exists(pdf_path):
        print(f"❌ 文件不存在: {pdf_path}")
        return

    print("=" * 60)
    print(f"开始测试询证函格式比对: {os.path.basename(pdf_path)}")
    print("=" * 60)

    start_time = time.time()
    
    try:
        # 调用核心服务（服务内部已包含三阶段的详细打印）
        result = compare_with_template(pdf_path)
        
        duration = round(time.time() - start_time, 2)
        
        print("\n" + "=" * 60)
        print("  ✅ 测试完成 (模拟 API 返回结果)")
        print("-" * 60)
        print(f"  耗时: {duration} 秒")
        print(f"  格式类型: {result.get('format_type')}")
        print(f"  比对通过: {result.get('passed')}")
        print(f"  差异数量: {len(result.get('mismatches', []))}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 比对过程发生异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: uv run python tests/test_confirmation_rules.py <pdf文件路径>")
        # 提供一个默认的测试路径（如果存在）
        default_path = "/Users/binginx/Desktop/2026年/星辰/运营管理部/50样本/1.pdf"
        if os.path.exists(default_path):
            print(f"使用默认测试文件: {default_path}\n")
            test_compare_api(default_path)
    else:
        pdf_path = sys.argv[1]
        test_compare_api(pdf_path)
