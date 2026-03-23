import re

def _clean_raw_tables(tables: list) -> list:
    cleaned = []
    strict_noise_patterns = [
        r"本页小计", r"本页合计", r"期初余额", r"期末余额", r"本期贷方", r"本期借方", 
        r"起止日期", r"打印日期", r"打印时间", r"以下空白", r"以上内容",
        r"收入总(?:金额|笔数)", r"支出总(?:金额|笔数)",
        r"第\s*\d+\s*页", r"第\s*\d+\s*/\s*\d+\s*页", r"共\s*\d+\s*[页条]记录?",
        r"总笔数", r"总金额", r"支出总金额", r"收入总金额"
    ]
    for row in tables:
        if not row: continue
        text = "".join(str(c or "") for c in row).strip()
        
        first = str(row[0] or "").strip()
        is_seq = bool(re.match(r"^\d+$", first))
        if is_seq:
            cleaned.append(row)
            continue
            
        is_strict = False
        for p in strict_noise_patterns:
            if re.search(p, text):
                is_strict = True
                break
                
        if not is_strict:
            cleaned.append(row)
        else:
            print(f"Dropped noise row: {row}")
            
    return cleaned

tables = [
    ["21", "2024-03-27", "网上银行", "100.00", "5000000.00", "30000000.00", "人民币"],
    ["", "收入总金额: 80348", "支出总金额: 500000", "共50条"],
    ["", "第1/3页", "", ""],
    ["", "这是正常的一行附加", "测试片段", ""]
]

cleaned = _clean_raw_tables(tables)
print("Cleaned tables:")
for r in cleaned:
    print(r)
