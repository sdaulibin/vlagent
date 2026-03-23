"""
银行适配规则

每家银行的 PDF 流水格式不同，通过策略模式定义各银行的：
- 关键词（用于自动识别银行类型）
- 表头映射（PDF 表头 → 标准字段名）
- 汇总信息正则模式
- 行过滤规则（跳过表头、汇总行等噪声行）
"""
import re
from typing import Optional


# ============================================================
# 标准字段名定义
# ============================================================

STANDARD_FIELDS = [
    "sequence",             # 序号
    "transaction_time",     # 交易时间
    "transaction_date",     # 交易日期/记账日期
    "income",               # 收入/贷方金额
    "expense",              # 支出/借方金额
    "balance",              # 余额
    "currency",             # 币种
    "counterparty_account", # 对方账号
    "counterparty_name",    # 对方户名
    "counterparty_bank",    # 对方开户行
    "description",          # 摘要/备注
    "serial_no",            # 流水号
    "voucher_no",           # 凭证号
    "debit_credit",         # 借贷标志
    "channel",              # 交易渠道
    "purpose",              # 用途
    "remark",               # 备注
]

STANDARD_SUMMARY_FIELDS = [
    "account_name",         # 户名
    "account_number",       # 账号
    "bank_name",            # 开户行
    "currency",             # 币种
    "date_range",           # 起止日期
    "start_date",           # 起始日期
    "end_date",             # 结束日期
    "income_total",         # 收入总金额
    "expense_total",        # 支出总金额
    "income_count",         # 收入总笔数
    "expense_count",        # 支出总笔数
]


# ============================================================
# 通用表头映射（覆盖常见银行表头写法）
# ============================================================

DEFAULT_HEADER_MAPPING = {
    # 序号
    "序号": "sequence",
    # 时间
    "交易时间": "transaction_time",
    "交易日期": "transaction_date",
    "记账日期": "transaction_date",
    "记账日": "transaction_date",
    "会计日期": "transaction_date",
    "日期": "transaction_date",
    "时间": "transaction_time",
    # 金额
    "收入": "income",
    "收入金额": "income",
    "贷方发生额": "income",
    "贷方金额": "income",
    "贷方(入账)": "income",
    "入账金额": "income",
    "转入金额": "income",
    "支出": "expense",
    "支出金额": "expense",
    "借方发生额": "expense",
    "借方金额": "expense",
    "借方(出账)": "expense",
    "出账金额": "expense",
    "转出金额": "expense",
    "交易金额": "amount",
    # 余额
    "余额": "balance",
    "账户余额": "balance",
    # 币种
    "币种": "currency",
    # 对方信息
    "对方账号": "counterparty_account",
    "对方户名": "counterparty_name",
    "对方名称": "counterparty_name",
    "对方单位": "counterparty_name",
    "收(付)方名称": "counterparty_name",
    "收(付)方账号": "counterparty_account",
    "对方开户行": "counterparty_bank",
    "对方行名": "counterparty_bank",
    "对方开户机构": "counterparty_bank",
    "对方开户行联行号": "counterparty_bank_code",
    "对方行号": "counterparty_bank_code",
    # 复合表头（文本策略可能将相邻列合并）
    "对方户名 摘要备注": "counterparty_name_remark",
    # 摘要
    "摘要": "description",
    "摘要备注": "description",
    "用途": "purpose",
    "附言": "remark",
    "备注": "remark",
    # 流水号/凭证号
    "流水号": "serial_no",
    "交易流水号": "serial_no",
    "凭证号": "voucher_no",
    "凭证种类": "voucher_type",
    "凭证号码": "voucher_no",
    # 借贷标志
    "借贷标志": "debit_credit",
    "借/贷": "debit_credit",
    # 渠道
    "交易渠道": "channel",
    "交易类型": "transaction_type",
    "交易名称": "transaction_type",
    # 其他
    "交易行所": "transaction_branch",
    "交易地点": "transaction_location",
    "起息日": "value_date",
    "打印实例号": "print_instance_no",
    "卡号": "card_no",
    "公司一卡通号": "card_no",
    "全局路由号": "global_route_no",
    "企业流水号": "enterprise_serial",
    "交易介质编号": "transaction_medium",
    "账户明细编号-交易流水号": "detail_serial_no",
    "对方交易对手信息": "counterparty_info",
    "交易对手信息": "counterparty_info",
    "机构柜员流水": "reference_no",
    "凭证号业务号用途摘要": "transaction_details",
}


# ============================================================
# 汇总信息正则模式
# ============================================================

DEFAULT_SUMMARY_PATTERNS = {
    "account_number": [
        r"账\s*号[：:]\s*(\d[\d\s\-]*\d)",
        r"账\(?卡\)?号[：:]\s*(\d[\d\s\-]*\d)",
        r"帐\s*号[：:]\s*(\d[\d\s\-]*\d)",
    ],
    "account_name": [
        r"(?:户\s*名|账户名称|账户名|客户名称)[：:]\s*(.+?)(?:\s{2,}|$)",
        r"(?:本方账号户名|账号名)[：:]\s*(.+?)(?:\s{2,}|$)",
    ],
    "currency": [
        r"币\s*种[：:]\s*(.+?)(?:\s{2,}|$)",
    ],
    "bank_name": [
        r"(?:开户行|开户机构|开户网点)[：:]\s*(.+?)(?:\s{2,}|$)",
        r"(?:本方账号开户行)[：:]\s*(.+?)(?:\s{2,}|$)",
    ],
    "date_range": [
        r"(?:起止日期|交易期间|查询期间|打印期间)[：:]\s*(.+?)(?:\s{2,}|$)",
        r"(?:财务日期范围)[：:]\s*(.+?)(?:\s{2,}|$)",
    ],
    "start_date": [
        r"(?:开始日期|起始日期)[：:]\s*(\d{4}[\-/年]\d{1,2}[\-/月]\d{1,2}日?)",
    ],
    "end_date": [
        r"(?:结束日期|截止日期)[：:]\s*(\d{4}[\-/年]\d{1,2}[\-/月]\d{1,2}日?)",
    ],
    "income_total": [
        r"(?:收入总金额|贷方合计|总收入金额|入账总金额)[：:]\s*([\d,\.]+)",
    ],
    "expense_total": [
        r"(?:支出总金额|借方合计|总支出金额|出账总金额)[：:]\s*([\d,\.]+)",
    ],
    "income_count": [
        r"(?:收入总笔数|贷方笔数|总收入笔数|入账总笔数)[：:]\s*(\d+)",
    ],
    "expense_count": [
        r"(?:支出总笔数|借方笔数|总支出笔数|出账总笔数)[：:]\s*(\d+)",
    ],
}


# ============================================================
# 噪声行判断
# ============================================================

# 需要跳过的行的关键词（表尾汇总、分页标记等）
NOISE_KEYWORDS = [
    "本页小计", "本页合计", "累计", "合计",
    "以上内容", "以下空白", "共计",
    "第.*页", "打印时间", "打印日期",
    "本期借方", "本期贷方",
    "期初余额", "期末余额",
    "注：", "备注：", "说明：",
    "---",  # 分隔线
    "总计", "总金额", "总笔数", "起止日期", "账户名:", "账号:",
]


def is_noise_row(row: list) -> bool:
    """判断是否为噪声行（汇总行、分页标记等）"""
    if not row:
        return True
    
    text = "".join(str(cell or "") for cell in row).strip()
    if not text:
        return True
        
    first = str(row[0] or "").strip()
    
    # 强制白名单：如果该行是极其标准的“交易明细”起手式，即使被吸附了页脚文字也绝不丢弃
    is_seq = bool(re.match(r"^\d+$", first))
    has_date_near = False
    for cell in row[1:4]:
        val = str(cell or "").strip()
        if re.search(r"(?:^|\s)\d{4}[\-/\.]\d{1,2}[\-/\.]\d{1,2}", val):
            has_date_near = True
            break
            
    is_date_start = bool(re.match(r"^\d{4}[\-/\.]\d{1,2}[\-/\.]\d{1,2}", first))
    
    if (is_seq and has_date_near) or is_date_start:
        return False
        
    # 匹配噪声关键词
    for keyword in NOISE_KEYWORDS:
        if re.search(keyword, text):
            return True
    return False


def is_header_row(row: list, header_mapping: dict = None) -> bool:
    """判断是否为表头行"""
    mapping = header_mapping or DEFAULT_HEADER_MAPPING
    if not row:
        return False
    
    match_count = 0
    clean_mapping_keys = {re.sub(r"\s+", "", k): k for k in mapping.keys()}

    for cell in row:
        val = str(cell or "").strip()
        if not val:
            continue
        # 直接匹配
        if val in mapping:
            match_count += 1
            continue
        # 消除内部所有空格和换行符后的模糊匹配
        val_clean = re.sub(r"\s+", "", val)
        if val_clean in clean_mapping_keys:
            match_count += 1
            
    # 超过 30% 的列匹配到表头关键词，视为表头行
    return match_count >= max(2, len([c for c in row if c]) * 0.3)


# ============================================================
# 银行类型检测
# ============================================================

BANK_KEYWORDS = {
    "icbc": ["中国工商银行", "工商银行", "ICBC"],
    "ccb": ["中国建设银行", "建设银行", "CCB"],
    "abc": ["中国农业银行", "农业银行", "ABC"],
    "boc": ["中国银行", "BOC"],
    "bocom": ["交通银行", "BOCOM"],
    "cmb": ["招商银行", "CMB", "CHINA MERCHANTS"],
    "everbright": ["光大银行", "EVERBRIGHT"],
    "psbc": ["邮政储蓄银行", "邮储银行", "PSBC"],
    "cgb": ["广发银行", "CGB"],
    "jining": ["济宁银行"],
    "shandong_local": ["潍坊银行", "莱商银行", "齐鲁银行", "威海银行", "泰安银行", "山东农信"],
}


def detect_bank_type(text: str) -> str:
    """从 PDF 全文文本中识别银行类型"""
    for bank_type, keywords in BANK_KEYWORDS.items():
        for kw in keywords:
            if kw in text or kw.lower() in text.lower():
                return bank_type
    return "unknown"


def map_headers(raw_headers: list, extra_mapping: dict = None) -> list:
    """
    将 PDF 中的原始表头映射为标准字段名

    Args:
        raw_headers: PDF 中提取的原始表头列表
        extra_mapping: 额外的自定义映射（优先级高于默认映射）

    Returns:
        标准字段名列表（未匹配的保留原始名称）
    """
    mapping = {**DEFAULT_HEADER_MAPPING}
    if extra_mapping:
        mapping.update(extra_mapping)

    result = []
    seen = {}
    for header in raw_headers:
        h = str(header or "").strip()
        mapped_field = ""
        
        # 精确匹配
        if h in mapping:
            mapped_field = mapping[h]
        else:
            # 模糊匹配（去除空格后匹配）
            h_clean = re.sub(r"\s+", "", h)
            matched = False
            for key, value in mapping.items():
                if re.sub(r"\s+", "", key) == h_clean:
                    mapped_field = value
                    matched = True
                    break
            if not matched:
                # 若未匹配，则保留原名或设置兜底
                mapped_field = h if h else "empty"
                
        # 强制唯一性约束：如果有多个未匹配的空列或同名词，防止字典重复覆盖从而导致 Excel 中内容错乱横向广播
        if mapped_field in seen:
            seen[mapped_field] += 1
            mapped_field = f"{mapped_field}_{seen[mapped_field]}"
        else:
            seen[mapped_field] = 0
            
        result.append(mapped_field)
        
    return result
