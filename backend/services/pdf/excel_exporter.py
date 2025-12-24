import os
import json
import pandas as pd
import re
from src.json_repir import fix_json

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

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            fixed_content = fix_json(content)
            data = json.loads(fixed_content)

            # 过滤并添加
            if isinstance(data, list):
                valid_records = [r for r in data if is_valid_record(r)]
                record_count = len(valid_records)
                all_data.extend(valid_records)
            else:
                if is_valid_record(data):
                    record_count = 1
                    all_data.append(data)
                else:
                    record_count = 0

            success_count += 1
            total_records += record_count

        except Exception as e:
            failed_files.append((filename, str(e)))

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
