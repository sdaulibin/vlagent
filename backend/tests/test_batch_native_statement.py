#!/usr/bin/env python3
"""
原生 PDF 流水批量解析测试脚本

用法:
    # 使用旧版解析器
    python tests/test_batch_native_statement.py --input /path/to/pdfs

    # 使用新版模版驱动解析器
    python tests/test_batch_native_statement.py --input /path/to/pdfs --v2

    # 指定输出目录
    python tests/test_batch_native_statement.py --input /path/to/pdfs --output /path/to/results --v2

功能:
    - 批量处理指定目录下的所有 PDF 文件
    - 自动跳过非原生电子版 PDF
    - 支持新旧两版解析器
    - 输出 Excel 结果和解析摘要
"""
import os
import sys
import time
import argparse

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_parser(use_v2: bool = False):
    """获取解析器函数"""
    if use_v2:
        from src.native_statement.parser_v2 import parse_native_pdf, is_native_pdf
        return parse_native_pdf, is_native_pdf, "v2"
    else:
        from src.native_statement.parser import parse_native_pdf, is_native_pdf
        return parse_native_pdf, is_native_pdf, "v1"


def process_single_file(
    pdf_path: str,
    output_dir: str,
    parse_func,
    is_native_func,
    exporter
) -> dict:
    """处理单个 PDF 文件"""
    filename = os.path.basename(pdf_path)
    base_name = os.path.splitext(filename)[0]

    start_time = time.time()

    # 检测是否为原生 PDF
    if not is_native_func(pdf_path):
        elapsed = time.time() - start_time
        return {
            "filename": filename,
            "status": "skipped",
            "reason": "非原生电子版 PDF",
            "elapsed": f"{elapsed:.2f}s",
        }

    # 解析
    result = parse_func(pdf_path)
    elapsed = time.time() - start_time

    if result.get("error") and not result.get("is_native"):
        return {
            "filename": filename,
            "status": "error",
            "reason": result["error"],
            "elapsed": f"{elapsed:.2f}s",
        }

    # 导出 Excel
    output_path = os.path.join(output_dir, f"{base_name}_解析结果.xlsx")
    exporter(result, output_path)

    return {
        "filename": filename,
        "status": "success",
        "bank_type": result.get("bank_type", "unknown"),
        "page_count": result.get("page_count", 0),
        "total_rows": result.get("total_rows", 0),
        "summary_fields": len(result.get("summary", {})),
        "extraction_strategy": result.get("extraction_strategy", "unknown"),
        "output": output_path,
        "elapsed": f"{elapsed:.2f}s",
    }


def main():
    parser = argparse.ArgumentParser(
        description="原生 PDF 流水批量解析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用旧版解析器
  python tests/test_batch_native_statement.py -i ./pdfs

  # 使用新版模版驱动解析器（推荐）
  python tests/test_batch_native_statement.py -i ./pdfs --v2

  # 指定输出目录
  python tests/test_batch_native_statement.py -i ./pdfs -o ./results --v2
        """
    )
    parser.add_argument("--input", "-i", required=True, help="PDF 文件目录")
    parser.add_argument("--output", "-o", default=None, help="输出目录（默认为 input 目录下的 results 子目录）")
    parser.add_argument("--v2", action="store_true", help="使用新版模版驱动解析器")
    args = parser.parse_args()

    input_dir = args.input
    use_v2 = args.v2
    output_dir = args.output or os.path.join(input_dir, "native_results_v2" if use_v2 else "native_results")

    if not os.path.isdir(input_dir):
        print(f"❌ 输入目录不存在: {input_dir}")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    # 获取解析器
    parse_func, is_native_func, version = get_parser(use_v2)

    # 获取导出函数
    from src.native_statement.exporter import export_to_excel

    # 收集所有 PDF 文件
    pdf_files = sorted([
        f for f in os.listdir(input_dir)
        if f.lower().endswith(".pdf")
    ])

    if not pdf_files:
        print(f"❌ 目录中没有 PDF 文件: {input_dir}")
        sys.exit(1)

    print("=" * 60)
    print(f"  原生 PDF 流水批量解析")
    print(f"  解析器版本: {version}")
    print("=" * 60)
    print(f"📂 输入目录: {input_dir}")
    print(f"📁 输出目录: {output_dir}")
    print(f"📄 共发现 {len(pdf_files)} 个 PDF 文件")
    print("=" * 60)

    results = []
    total_start = time.time()

    for i, filename in enumerate(pdf_files, 1):
        pdf_path = os.path.join(input_dir, filename)
        print(f"\n[{i}/{len(pdf_files)}] 处理: {filename}")

        result = process_single_file(
            pdf_path, output_dir,
            parse_func, is_native_func,
            export_to_excel
        )
        results.append(result)

        status = result["status"]
        if status == "success":
            strategy = result.get("extraction_strategy", "unknown")
            print(f"  ✅ 成功 | 银行: {result['bank_type']} | "
                  f"页数: {result['page_count']} | "
                  f"记录: {result['total_rows']} | "
                  f"策略: {strategy} | "
                  f"耗时: {result['elapsed']}")
        elif status == "skipped":
            print(f"  ⏭️  跳过 | {result['reason']} | 耗时: {result['elapsed']}")
        else:
            print(f"  ❌ 失败 | {result.get('reason', 'unknown')} | 耗时: {result['elapsed']}")

    total_elapsed = time.time() - total_start

    # 打印汇总
    print("\n" + "=" * 60)
    print("  处理汇总")
    print("=" * 60)

    success = sum(1 for r in results if r["status"] == "success")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    failed = sum(1 for r in results if r["status"] == "error")

    print(f"  总计: {len(results)} 个文件")
    print(f"  ✅ 成功: {success}")
    print(f"  ⏭️  跳过: {skipped}")
    print(f"  ❌ 失败: {failed}")
    print(f"  ⏱️  总耗时: {total_elapsed:.2f}s")

    if success > 0:
        avg_time = total_elapsed / success
        print(f"  📊 平均耗时: {avg_time:.2f}s/文件")

        # 按银行类型统计
        bank_stats = {}
        for r in results:
            if r["status"] == "success":
                bank = r.get("bank_type", "unknown")
                if bank not in bank_stats:
                    bank_stats[bank] = {"count": 0, "rows": 0}
                bank_stats[bank]["count"] += 1
                bank_stats[bank]["rows"] += r.get("total_rows", 0)

        print(f"\n  按银行统计:")
        for bank, stats in sorted(bank_stats.items()):
            print(f"    - {bank}: {stats['count']} 个文件, {stats['rows']} 条记录")

    print("=" * 60)
    print(f"📁 结果已保存到: {output_dir}")


if __name__ == "__main__":
    main()
