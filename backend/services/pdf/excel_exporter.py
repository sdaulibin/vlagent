import os
import json
import pandas as pd
import re
from src.json_repair import fix_json

def deduplicate_records(records: list, unique_key: str = "交易流水号"):
    """
    对交易记录进行去重
    """
    seen = set()
    unique_records = []
    
    for record in records:
        val = str(record.get(unique_key, ""))
        if val not in seen:
            seen.add(val)
            unique_records.append(record)
    return unique_records


def merge_cgb_cross_page_records(records: list) -> list:
    """
    合并广发银行跨页记录
    支持两种模式：
    1. 通过 _incomplete 字段识别需要合并的记录
    2. 自动检测：流水号格式不完整（应为8位+4位）或缺少日期的记录
    """
    if not records:
        return records
    
    def is_incomplete_tail(record):
        """判断是否为页面底部不完整记录（tail）"""
        # 有 _incomplete 标记
        if record.get("_incomplete") == "tail":
            return True
        # 有日期但流水号可能只有前半部分（8位）
        serial = str(record.get("流水号", "")).replace(" ", "")
        time_str = str(record.get("交易时间", ""))
        # 如果有日期（YYYY-MM-DD格式）但流水号只有前8位数字
        if re.match(r'\d{4}-\d{2}-\d{2}', time_str):
            if re.match(r'^\d{8}$', serial):  # 只有8位，缺少后4位
                return True
        return False
    
    def is_incomplete_head(record):
        """判断是否为页面顶部延续记录（head）"""
        # 有 _incomplete 标记
        if record.get("_incomplete") == "head":
            return True
        # 没有完整日期，只有时间（如 17:26:28）
        time_str = str(record.get("交易时间", ""))
        serial = str(record.get("流水号", "")).replace(" ", "")
        # 只有时间没有日期
        if re.match(r'^\d{2}:\d{2}:\d{2}$', time_str):
            return True
        # 流水号只有后4位
        if re.match(r'^\d{4}$', serial):
            return True
        return False
    
    merged = []
    i = 0
    
    while i < len(records):
        current = records[i]
        
        # 检测是否需要合并
        should_merge = False
        if is_incomplete_tail(current) and i + 1 < len(records):
            next_record = records[i + 1]
            if is_incomplete_head(next_record):
                should_merge = True
        
        if should_merge:
            next_record = records[i + 1]
            # 合并记录：以 tail 为基础，用 head 的非空字段补充
            merged_record = current.copy()
            
            # 拼接流水号（前8位 + 后4位）
            tail_serial = str(merged_record.get("流水号", "")).replace(" ", "")
            head_serial = str(next_record.get("流水号", "")).replace(" ", "")
            if tail_serial and head_serial and len(tail_serial) == 8 and len(head_serial) == 4:
                merged_record["流水号"] = f"{tail_serial} {head_serial}"
            
            # 拼接交易时间（日期 + 时间）
            tail_time = str(merged_record.get("交易时间", ""))
            head_time = str(next_record.get("交易时间", ""))
            if tail_time and head_time:
                # 如果 tail 有日期，head 有时间
                if re.match(r'\d{4}-\d{2}-\d{2}$', tail_time) and re.match(r'^\d{2}:\d{2}:\d{2}$', head_time):
                    merged_record["交易时间"] = f"{tail_time} {head_time}"
            
            # 用 head 的非空字段补充其他字段
            for key, value in next_record.items():
                if key in ["_incomplete", "流水号", "交易时间"]:
                    continue
                # 如果 tail 中该字段为空，用 head 的值
                if not merged_record.get(key) and value:
                    merged_record[key] = value
                # 如果都有值且需要拼接
                elif merged_record.get(key) and value and key in ["对方户名", "对方开户行", "对方账号"]:
                    if value not in merged_record[key]:
                        merged_record[key] = merged_record[key] + value
            
            # 移除 _incomplete 标记
            merged_record.pop("_incomplete", None)
            merged.append(merged_record)
            i += 2  # 跳过 head 记录
            continue
        
        # 移除临时标记
        current_copy = current.copy()
        current_copy.pop("_incomplete", None)
        merged.append(current_copy)
        i += 1
    
    return merged

def process_txt_files_to_excel(input_folder, output_file, bank_type: str = "shandong_local"):
    """
    遍历文件夹中的所有txt文件，读取其中的JSON数据，
    合并所有数据并按照序号/流水号排序后输出到Excel文件中
    """
    all_data = []
    failed_files = []
    success_count = 0
    total_records = 0

    # 数据过滤逻辑：移除噪声（如 URL 链接）
    def is_valid_record(record):
        if not isinstance(record, dict):
            return False
        
        # 1. 过滤 URL 噪声 (主要针对招行)
        serial_no = str(record.get("交易流水号", "")).lower()
        if any(keyword in serial_no for keyword in ["http", ".com", "aspx", "enquiry"]):
            return False
        
        # 2. 验证日期格式 (根据银行类型选择 key)
        # 招行和光大使用 '交易日期', 山东地方银行使用 '交易时间'
        date_keys = ["交易日期", "交易时间", "日期", "时间"]
        date_str = ""
        for key in date_keys:
            if key in record and record[key]:
                date_str = str(record[key])
                break
        
        # 如果是招行，必须验证日期
        if bank_type == "cmb":
            if not re.search(r'\d', date_str):
                return False
        else:
            # 其他银行，如果有日期则验证，如果没有日期（可能是某些特殊行）暂时放行或根据需求调整
            # 这里的逻辑是：如果能找到日期 key，则必须包含数字
            if date_str and not re.search(r'\d', date_str):
                return False
        
        return True

    # 遍历文件夹中的所有txt文件
    txt_files = sorted([f for f in os.listdir(input_folder) if f.lower().endswith('.txt')])
    
    for filename in txt_files:
        file_path = os.path.join(input_folder, filename)
        
        # 从文件名提取页码（如 page_001.txt -> 0）
        page_num = None
        page_match = re.search(r'page_(\d+)', filename)
        if page_match:
            page_num = int(page_match.group(1)) - 1  # 转为 0-indexed
        else:
            # 尝试其他格式
            num_match = re.search(r'(\d+)', filename)
            if num_match:
                page_num = int(num_match.group(1)) - 1

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            fixed_content = fix_json(content)
            data = json.loads(fixed_content)

            # 过滤并添加
            if isinstance(data, list):
                valid_records = [r for r in data if is_valid_record(r)]
                # 为每条记录添加页码信息
                for r in valid_records:
                    if page_num is not None:
                        r["_page"] = page_num
                record_count = len(valid_records)
                all_data.extend(valid_records)
            else:
                if is_valid_record(data):
                    if page_num is not None:
                        data["_page"] = page_num
                    record_count = 1
                    all_data.append(data)
                else:
                    record_count = 0

            success_count += 1
            total_records += record_count

        except Exception as e:
            failed_files.append((filename, str(e)))

    # 广发银行跨页记录合并处理
    if bank_type == "cgb" and all_data:
        all_data = merge_cgb_cross_page_records(all_data)

    # 排序
    if all_data:
        first_record = all_data[0]
        sort_key = next((k for k in ["序号", "交易流水号", "交易日期"] if k in first_record), None)
        
        if sort_key:
            try:
                all_data.sort(key=lambda x: int(x.get(sort_key, 0)))
            except:
                all_data.sort(key=lambda x: str(x.get(sort_key, "")))

    # 导出
    if all_data:
        df = pd.DataFrame(all_data)
        df.to_excel(output_file, index=False)
        print(f"\n✓ 成功导出 {len(all_data)} 条记录到 {output_file}")
        return all_data
    return []
