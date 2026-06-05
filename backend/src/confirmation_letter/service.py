"""
询证函识别服务

独立的识别处理流程，复用底层 PDF 工具和 AI 请求接口。
"""
import os
import json
import shutil
import tempfile
import re
import time
from datetime import datetime
from typing import Any

from sqlmodel import select
from services.pdf.pdf_utils import split_pdf_to_images
from services.core.request_ai import request_qwen35, ai_semaphore
from src.json_repair import fix_json
from src.confirmation_letter.prompts import FIELD_EXTRACTION_PROMPT


# 所有识别字段
ALL_FIELDS = [
    "confirmation_no", "recipient_bank", "accounting_firm", "reply_address",
    "contact_person", "phone", "postal_code", "debit_account",
    "cutoff_date", "start_date", "end_date", "seal_date",
    "signature_name"
]

# 编号抓取优先级：函证编号 > 询证函编号 > 编号 > NO. > 索引号 > 项目编号
CONFIRMATION_NO_PATTERNS = [
    r"函证编号\s*[:：]?\s*([A-Za-z0-9\u4e00-\u9fff\-_/，,（）() ]+)",
    r"询证函编号\s*[:：]?\s*([A-Za-z0-9\u4e00-\u9fff\-_/，,（）() ]+)",
    r"\b编号\s*[:：]?\s*([A-Za-z0-9\u4e00-\u9fff\-_/，,（）() ]+)",
    r"\bNO\.?\s*[:：]?\s*([A-Za-z0-9\u4e00-\u9fff\-_/，,（）() ]+)",
    r"索引号\s*[:：]?\s*([A-Za-z0-9\u4e00-\u9fff\-_/，,（）() ]+)",
    r"项目编号\s*[:：]?\s*([A-Za-z0-9\u4e00-\u9fff\-_/，,（）() ]+)",
]

FORMAT_TEMPLATES = {
    "format_1": ["银行询证函", "回函地址", "联系人", "电话", "邮编", "截至"],
    "format_2": ["银行询证函", "回函请寄", "收件人", "联系电话", "函证基准日"],
    "capital_verification": ["验资", "询证函", "出资", "截止日期"],
}

# 模型高频幻觉修正规则（不依赖 raw_text 验证）
# 格式：(错误模式, 正确模式)
HALLUCINATION_FIX_RULES = [
    # 事务所名称：模型喜欢在"有限责任会计师事务所"中间插入"公司"
    (r"有限责任公司会计师事务所", "有限责任会计师事务所"),
    (r"有限公司会计师事务所", "有限责任会计师事务所"),
    (r"公司会计师事务所", "会计师事务所"),
    # 事务所名称常见幻觉：多余的后缀
    (r"会计师事务所公司$", "会计师事务所"),
    (r"会计师事务所有限$", "会计师事务所"),
    # 地址字段：模型可能添加的后缀
    (r"(\d号)公司$", r"\1"),  # "XX路88号公司" → "XX路88号"
    (r"(\d层)公司$", r"\1"),  # "XX大厦5层公司" → "XX大厦5层"
    # 银行名称：模型可能添加的后缀
    (r"银行股份有限$", "银行股份有限公司"),
    (r"(\w银行)有限公司$", r"\1股份有限公司"),
]


def _fix_hallucination_by_rules(value: str, field_name: str = "") -> str:
    """使用规则修正模型的高频幻觉（所见即所得）"""
    if not value:
        return value

    original = value
    for wrong_pattern, correct_pattern in HALLUCINATION_FIX_RULES:
        if isinstance(correct_pattern, str):
            value = re.sub(wrong_pattern, correct_pattern, value)
        else:
            value = re.sub(wrong_pattern, correct_pattern, value)

    if value != original:
        print(f"  ⚠️ [幻觉修正] {field_name}='{original}' → '{value}'")
    return value


# 需要做原文交叉验证的字段（防止模型幻觉）
# 注意：raw_text 与字段来自同一次 AI 调用，对于模型一致性幻觉可能无法完全拦截
# 主要依赖 HALLUCINATION_FIX_RULES 进行规则修正
FIELDS_TO_VALIDATE = [
    "signature_name",
    "recipient_bank",
]


def _validate_field_in_raw_text(field_name: str, value: str, raw_text: str) -> str:
    """验证 AI 提取的字段值是否真的存在于原文中（防幻觉）"""
    if not value or not raw_text:
        return value
    # 去除空格后在 raw_text 中搜索
    normalized_value = re.sub(r'\s+', '', value)
    normalized_text = re.sub(r'\s+', '', raw_text)
    if normalized_value in normalized_text:
        return value

    # 尝试应用幻觉修正规则后再验证
    fixed_value = _fix_hallucination_by_rules(normalized_value, field_name)
    if fixed_value != normalized_value and fixed_value in normalized_text:
        return fixed_value

    print(f"  ⚠️ [幻觉检测] {field_name}='{value}' 在原文中未找到，疑似模型幻觉，已清除")
    return ""


def _clean_id_value(value: str) -> str:
    if not value:
        return ""
    cleaned = value.strip().strip("：:.。")
    # OCR 纠错
    cleaned = cleaned.replace("材库", "林泉")
    # 去除页码后缀，如 2024-001/1，但不截断长后缀（如 /1638999）
    cleaned = re.sub(r"\s*第\s*\d+\s*/.*$", "", cleaned)  # 「第 1/4 页」或截断的「第 1/」
    cleaned = re.sub(r"[/\\][1-9]\d?$", "", cleaned)
    cleaned = re.sub(r"\s*第?\d+\s*页$", "", cleaned)
    cleaned = re.sub(r"^NO\.?\s*[:：]?", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()

def _fix_text_hallucination(text: str) -> str:
    """修复通用或高频的文本提取幻觉（如形近字）"""
    if not text:
        return text
    hallucination_map = {
        "普华水道": "普华永道",
        "安客": "安永",
        "天律": "天津",
        "大华水": "大华永",
    }
    for wrong, correct in hallucination_map.items():
        text = text.replace(wrong, correct)
    return text


def _parse_confirmation_no(text: str, ai_value: str = "") -> str:
    raw = text or ""
    for pattern in CONFIRMATION_NO_PATTERNS:
        match = re.search(pattern, raw, flags=re.IGNORECASE)
        if match:
            return _clean_id_value(match.group(1))

    # AI 返回值优先于二维码/条形码编号
    ai_cleaned = _clean_id_value(ai_value)
    if ai_cleaned:
        return ai_cleaned

    # 二维码/条形码编号优先级最低
    barcode_match = re.search(r"条形码.{0,20}?([A-Za-z0-9\-]{6,})", raw)
    if barcode_match:
        return _clean_id_value(barcode_match.group(1))

    return ""


def _normalize_date(value: str) -> str:
    if not value:
        return ""

    value = value.strip()
    # 去除空格（OCR 文本中年月日之间可能有空格，如 "2022 年 1 月 1 日"）
    value = re.sub(r"\s+", "", value)
    patterns = [
        r"(\d{4})[年/\-.](\d{1,2})[月/\-.](\d{1,2})日?",
        r"(\d{4})(\d{2})(\d{2})",
    ]
    for pattern in patterns:
        m = re.search(pattern, value)
        if not m:
            continue
        y, mm, dd = m.groups()
        try:
            dt = datetime(int(y), int(mm), int(dd))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return ""
    return ""


def _normalize_seal_date(seal_date_raw: str, text: str) -> str:
    """清理印章日期：排除事务所 FS 标记章的日期"""
    seal_date = _normalize_date(seal_date_raw)
    if not seal_date:
        return ""

    # 从 raw_text 中检测 FS 标记章的日期（右上角蓝色方章，格式如 "FS 2025 -07- 25"）
    raw = text or ""
    fs_patterns = [
        r"FS\s*[\n]?\s*(\d{4})\s*[-–]\s*(\d{1,2})\s*[-–]\s*(\d{1,2})",
        r"F\s*S\s*[\n]?\s*(\d{4})\s*[-–]\s*(\d{1,2})\s*[-–]\s*(\d{1,2})",
    ]
    fs_date = ""
    for pattern in fs_patterns:
        m = re.search(pattern, raw)
        if m:
            try:
                y, mm, dd = m.groups()
                fs_date = datetime(int(y), int(mm), int(dd)).strftime("%Y-%m-%d")
                break
            except ValueError:
                pass

    # 如果 seal_date 与 FS 标记章日期相同，说明 AI 取了错误的日期
    if fs_date and seal_date == fs_date:
        # 尝试从落款区域提取正确的手写日期
        handwritten_patterns = [
            r"预留签章.*?(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日?)",
            r"电子授权.*?(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日?)",
            r"有限公司.*?(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日?)",
            r"20\d\d\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日?", # 兜底提取底部任何打印年月
        ]
        for pattern in handwritten_patterns:
            m = re.search(pattern, raw, flags=re.DOTALL)
            if m:
                candidate = _normalize_date(m.group(1))
                if candidate and candidate != fs_date:
                    return candidate
    return seal_date


def _correct_hallucinated_date(date_str: str, raw_text: str) -> str:
    """
    全局日期容错：针对大模型在提取手写或模糊日期时容易产生的特定幻觉（如将 02、07 识别为 01 等），
    去 raw_text 中进行二次比对校验。
    """
    if not date_str or len(date_str) != 10:
        return date_str
        
    y, m, d = date_str[:4], date_str[5:7], date_str[8:10]
    
    # 提取同一月份下在原文中出现过的所有「天」
    # 匹配各类常见日期格式，放宽对中英文数字边界的限制，如：2025 年 12 月 02 日
    pattern = rf"(?:{y})\s*[年/\-.]\s*(?:{m}|{int(m)})\s*[月/\-.]\s*([0-3]?\d)\s*[日号]?"
    m_raw_all = re.findall(pattern, raw_text)
    
    if m_raw_all:
        raw_days = [str(int(day)).zfill(2) for day in m_raw_all if int(day) != 0]
        
        # 1. 如果提取出的天数明确在原文该月中出现了，则信任提取结果
        if d in raw_days:
            return date_str
            
        # 2. 如果提取出的天数不在该月的原文记录中，说明极大可能是幻觉，尝试修正：
        if d == "01":
            if "02" in raw_days: return f"{y}-{m}-02"
            if "07" in raw_days: return f"{y}-{m}-07"
        if d == "07" and "01" in raw_days: return f"{y}-{m}-01"
        if d == "02" and "01" in raw_days: return f"{y}-{m}-01"
            
        # 3. 终极兜底：如果该月在原文中只出现了一个天数，那无论模型跑偏成了啥，都强行纠正
        unique_days = list(set(raw_days))
        if len(unique_days) == 1:
            return f"{y}-{m}-{unique_days[0]}"
            
    return date_str


def _normalize_phone(value: str) -> str:
    """规范化电话号码，保留区号、国际前缀和复合格式（手机/固话），支持多个电话"""
    if not value:
        return ""
    # 轻量清理：去首尾空白，去除包含中文的括号注释（如"(项目组成员)"），保留数字区号（如"(852)"）
    cleaned = value.strip()
    cleaned = re.sub(r"[（(][^）)]*[\u4e00-\u9fff]+[^）)]*[）)]", "", cleaned)
    cleaned = re.sub(r"[，。、；]+$", "", cleaned)  # 去尾部中文标点
    cleaned = re.sub(r"\s{2,}", " ", cleaned)       # 压缩连续空格

    # 尝试分割多个电话（仅按逗号、斜杠、顿号分割，不按空格，避免拆散带区号的电话如 "+86(757) 8620"）
    parts = re.split(r"[,，/／、]+", cleaned)
    valid_phones = []
    for p in parts:
        p_strip = p.strip()
        # 只要包含数字就保留
        if re.search(r"\d", p_strip):
            # 移除非电话字符，保留数字、加号、连字符、括号（区号用）和空格
            p_clean = re.sub(r"[^\d+\-()\s]", "", p_strip)
            p_clean = re.sub(r"\s{2,}", " ", p_clean).strip()
            if p_clean:
                valid_phones.append(p_clean)

    if valid_phones:
        # 如果提取到多个有效电话，用中文逗号分隔
        return "，".join(valid_phones)
    return ""


def _normalize_postal_code(value: str) -> str:
    if not value:
        return ""
    m = re.search(r"\b(\d{6})\b", value)
    return m.group(1) if m else ""


def _normalize_account(value: str) -> str:
    if not value:
        return ""
    # 只提取数字，不要前缀，不限制长度
    digits = re.sub(r"[^\d]", "", value)
    return digits


def _normalize_seal_name(value: str) -> str:
    """清理印章名称中的无关文字"""
    if not value:
        return ""
    name = value.strip()
    # 去除 [] 【】 () （）括号
    name = re.sub(r"[\[\]【】]", "", name)
    # 去除「预留签章」「采用电子授权」等无关文字
    noise_patterns = [
        r"[（(]?\s*预留签章\s*[）)]?",
        r"[（(]?\s*采用电子授权\s*[）)]?",
        r"[（(]?\s*电子签章\s*[）)]?",
        r"[（(]?\s*签章\s*[）)]?",
        r"预留签章[/／]采用电子授权",
    ]
    for pattern in noise_patterns:
        name = re.sub(pattern, "", name)
    # 如果结果是印章类型而非公司名称，返回空字符串
    seal_type_words = ["财务专用章", "公章", "合同专用章", "发票专用章", "行政章", "业务专用章"]
    cleaned_name = _fix_text_hallucination(name.strip())
    if cleaned_name in seal_type_words:
        return ""
    # 如果结果是会计师事务所/审计机构名称，返回空字符串（seal_name 应为客户公司名称）
    audit_firm_keywords = ["会计师事务所", "毕马威", "安永", "德勤", "普华永道", "KPMG", "EY", "Deloitte", "PwC"]
    for keyword in audit_firm_keywords:
        if keyword in cleaned_name:
            return ""
    # 清理多余符号和空格
    name = re.sub(r"[，。、；\s/／]+$", "", name)
    name = re.sub(r"^[，。、；\s/／]+", "", name)
    return name.strip()


def _extract_debit_account(text: str, ai_value: str = "") -> str:
    """从 OCR 文本中提取扣费账号，回退到 AI 返回值"""
    raw = text or ""
    # 常见句式正则模式（按优先级排列）
    patterns = [
        # 「从本公司 NRA812011200002 号支取」 或 「从本公司 8022 10200_账号支取」
        r"从本公司.*?([A-Za-z]*[\d\s]{5,}).*?支取",
        # 「扣费账号：xxx」
        r"扣费账号.*?([A-Za-z]*[\d\s]{5,})",
        # 「付款账号：xxx」
        r"付款账号.*?([A-Za-z]*[\d\s]{5,})",
        # 「授权...从...xxx号支取」
        r"授权.*?从.*?([A-Za-z]*[\d\s]{5,}).*?支取",
        # 「从...账号 xxx 扣除/支付」
        r"从.*?账号.*?([A-Za-z]*[\d\s]{5,}).*?(?:扣除|支付|扣取)",
        # 「账号 xxx 支取/扣费」
        r"账号.*?([A-Za-z]*[\d\s]{5,}).*?(?:支取|扣费)",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw)
        if match:
            return _normalize_account(match.group(1))

    # 回退到 AI 返回值
    return _normalize_account(ai_value)




def _extract_recipient_bank(text: str, ai_value: str = "") -> str:
    """从 OCR 文本中提取询证函抬头（收件银行）"""
    raw = text or ""
    # 优先使用正则从头部匹配
    # 模式一：xxx银行xxx支行（以下简称...
    pattern_standard = r"^\s*([\u4e00-\u9fffA-Za-z0-9]+银行[\u4e00-\u9fff]{0,15}(?:分行|支行|营业部|总行)?)\s*[(（]\s*以下简称"
    # 模式二：不在开头但格式严格：(不在开头时避免误伤)
    pattern_standard_2 = r"([\u4e00-\u9fffA-Za-z0-9]+银行[\u4e00-\u9fff]{0,15}(?:分行|支行|营业部|总行)?)\s*[(（]\s*以下简称"
    # 模式三：致：xxx银行
    pattern_to = r"致\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9]+银行[\u4e00-\u9fff]{0,15}(?:分行|支行|营业部|总行)?)"
    
    for pat in [pattern_standard, pattern_standard_2, pattern_to]:
        match = re.search(pat, raw)
        if match:
            bname = match.group(1).strip()
            # 轻微清理可能的错误换行符或多余前缀
            bname = re.sub(r"^致[:：]?\s*", "", bname)
            return _fix_text_hallucination(bname)

    # 回退到 AI 提取结果
    ai_clean = (ai_value or "").strip()
    ai_clean = re.sub(r"^致[:：]?\s*", "", ai_clean)
    ai_clean = re.sub(r"[(（]\s*以下简称.*", "", ai_clean)
    return _fix_text_hallucination(ai_clean)


def _extract_accounting_firm(text: str, ai_value: str = "") -> str:
    """从 OCR 文本中提取事务所名称，包含分所后缀"""
    raw = text or ""
    # 先去除文本中的 [] 【】 括号，统一处理
    cleaned = re.sub(r"[\[\]【】]", "", raw)

    # 按优先级匹配：带分所 > 带有限公司 > 带（特殊普通合伙） > 通用
    patterns = [
        # 1. 聘请的xxx事务所xxx分所
        r"聘请的?\s*(.{2,30}会计师事务所.{0,20}?分所)",
        # 2. 聘请的xxx事务所有限公司
        r"聘请的?\s*(.{2,30}会计师事务所.{0,10}?有限公司)",
        # 3. 聘请的xxx事务所（特殊普通合伙）
        r"聘请的?\s*(.{2,30}会计师事务所[（(][^）)]*[）)])",
        # 4. 回函寄至xxx事务所xxx分所
        r"回函.*?寄.*?至\s*(.{2,30}会计师事务所.{0,20}?分所)",
        # 5. 回函寄至xxx事务所有限公司
        r"回函.*?寄.*?至\s*(.{2,30}会计师事务所.{0,10}?有限公司)",
        # 6. 回函寄至xxx事务所（特殊普通合伙）
        r"回函.*?寄.*?至\s*(.{2,30}会计师事务所[（(][^）)]*[）)])",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned)
        if match:
            name = match.group(1).strip()
            # 截断：在常见后续词语处停止（如"正在"、"对"、"进行"等）
            name = re.split(r"(?:正在|对[本我]|进行|截至|应当)", name)[0].strip()
            name = re.sub(r"[，。、；\s]+$", "", name)
            if name:
                return _fix_text_hallucination(name)

    # 回退到 AI 返回值
    ai_clean = re.sub(r"[\[\]【】]", "", (ai_value or "")).strip()
    # 同样截断 AI 返回值中的多余内容
    ai_clean = re.split(r"(?:正在|对[本我]|进行|截至|应当)", ai_clean)[0].strip()
    ai_clean = re.sub(r"[，。、；\s]+$", "", ai_clean)
    return _fix_text_hallucination(ai_clean)


def _extract_reply_contact(text: str, ai_contact: str = "", ai_phone: str = "") -> tuple[str, str]:
    """从 OCR 文本中提取回函联系人和电话（优先回函收件人，而非业务联系人）"""
    raw = text or ""
    contact = ""
    phone = ""

    # 【关键】确定搜索边界：只在"回函信息区"搜索，不要延伸到"公司签章区"
    # 找到"公司经办人"、"预留签章"、"以下由被询证银行"等关键字后停止搜索
    boundary_keywords = ["公司经办人", "经办人", "预留签章", "采用电子授权", "以下由被询证银行", "被询证银行填列"]
    boundary_pos = len(raw)
    for keyword in boundary_keywords:
        pos = raw.find(keyword)
        if pos > 0 and pos < boundary_pos:
            boundary_pos = pos

    # 截取回函信息区的文本（从开头到边界）
    reply_zone = raw[:boundary_pos]

    # 电话/手机号的统一正则（匹配「电话」「手机号」等关键字）
    # 支持：+86(757) 8620 4251、(852) 98624135、18624282945/0411-39724212 以及中文备注和逗号分隔
    PHONE_PATTERN = r"(?:手机号|电话|联系电话)\s*[:：]\s*(.*?)(?=\s*(?:邮政编码|邮编|电邮|电子邮箱|邮箱|传真|网址|回函|[\n\r]|$))"

    # 优先提取「回函收件人」
    # 匹配中文字符、中划线及英文字母，避免 OCR 噪音字符混入
    NAME_CAPTURE = r"([\u4e00-\u9fff·a-zA-Z\-_]{1,20})"
    contact_patterns = [
        r"回函\s*收件人\s*[:：]\s*" + NAME_CAPTURE,
        r"回函\s*联系人\s*[:：]\s*" + NAME_CAPTURE,
        r"回函.*?收件人\s*[:：]\s*" + NAME_CAPTURE,
    ]
    for pattern in contact_patterns:
        match = re.search(pattern, reply_zone)
        if match:
            contact = match.group(1).strip()
            break

    # 如果没找到回函收件人，查找回函地址之后的联系人/收件人
    if not contact:
        # 从「回函地址」之后的文本中查找
        addr_match = re.search(r"回函[地址]*\s*[:：]", reply_zone)
        if addr_match:
            after_addr = reply_zone[addr_match.end():]
            general_patterns = [
                r"收件人\s*[:：]\s*" + NAME_CAPTURE,
                r"联系人\s*[:：]\s*" + NAME_CAPTURE,
            ]
            for pattern in general_patterns:
                match = re.search(pattern, after_addr)
                if match:
                    contact = match.group(1).strip()
                    break

    # 提取回函联系电话：只在回函信息区搜索
    if contact:
        # 在联系人出现位置之后找电话
        contact_pos = reply_zone.find(contact)
        if contact_pos >= 0:
            nearby_text = reply_zone[contact_pos:contact_pos + 150]
            phone_match = re.search(PHONE_PATTERN, nearby_text)
            if phone_match:
                phone = phone_match.group(1).strip()

    # 如果在回函区域没找到电话，从回函地址之后找
    if not phone:
        addr_match = re.search(r"回函[地址]*\s*[:：]", reply_zone)
        if addr_match:
            after_addr = reply_zone[addr_match.end():]
            phone_match = re.search(PHONE_PATTERN, after_addr)
            if phone_match:
                phone = phone_match.group(1).strip()

    # 回退到 AI 值（但只在没有回函区域结果时使用）
    if not contact:
        contact = (ai_contact or "").strip()
    if not phone:
        phone = (ai_phone or "").strip()

    if contact:
        # 清除可能误粘连的相邻字段名
        contact = re.sub(r"(?:电话|联系电话|手机|手机号|电邮|电子邮箱|邮箱|邮编|邮政编码|传真|座机).*$", "", contact).strip()
        # 清理常见的印章文字误入联系人姓名（例如普华永道蓝色章的“道”容易被OCR识别为“董”）
        if contact in ["董静", "道静", "谨静"] and re.search(r"普华|Pricewaterhouse|FOR\s*IDENTIFICATION|道|谨", raw, re.IGNORECASE):
            contact = "静"
        # 移除两头多余的特定标点
        contact = contact.strip("_. ")

    return contact, phone


def _extract_date_range(text: str) -> tuple[str, str]:
    """从 OCR 文本中提取起始日期和终止日期，优先表格上方描述"""
    raw = text or ""
    start_date = ""
    end_date = ""
    DATE_PAT = r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日?"

    # 优先级1：表格上方的描述格式「自xxx起至xxx期间」（OCR 极易把括号识别错，或错加换行符，用 [^\d]*? 略过其中的非数字干扰字符）
    table_patterns_high = [
        # 最强特征：带“期间内注销”或“期间注销”的起止日期匹配，可以无视“自”字是否被正确识别
        rf"({DATE_PAT})[^\d]*?至[^\d]*?({DATE_PAT})[^\d]*?(?:期间|注销|账户)",
        # 自[2025年1月1日]起至[2025年9月30日]期间 (兼容各种括号、换行、及"白/目"混杂)
        rf"[自白目][^\d]*?({DATE_PAT})[^\d]*?至[^\d]*?({DATE_PAT})",
        # 从2025年1月1日至2025年9月30日
        rf"从[^\d]*?({DATE_PAT})[^\d]*?至[^\d]*?({DATE_PAT})",
    ]
    for pattern in table_patterns_high:
        matches = re.findall(pattern, raw)
        if matches:
            # 明确带有「自...至...」字样的格式非常准，通常直接取第一个即可
            return matches[0]

    # 我们不再回退到抬头描述的审计期间，因为用户明确要求取的是账户信息表格（如注销账户表）上方的时间
    # 删除了纯日期连读的兜底正则，因为它会误命中抬头描述的 "2025年1月1日-2025年10月31日"
    # 如果表格模式匹配不到，直接抛空交由 AI 的提取结果兜底，避免强制覆盖为错误的抬头时间。
    return "", ""


def _validate_and_normalize_fields(data: dict[str, Any], text: str) -> dict[str, Any]:
    normalized = {field: (data.get(field, "") or "").strip() for field in ALL_FIELDS}
    # 原文交叉验证：检查关键字段是否真的存在于 raw_text 中
    for field in FIELDS_TO_VALIDATE:
        normalized[field] = _validate_field_in_raw_text(field, normalized[field], text)
    normalized["confirmation_no"] = _parse_confirmation_no(text, normalized.get("confirmation_no", ""))
    # 事务所名称：优先从 OCR 文本中提取（更准确），回退到 AI 返回值，最后应用幻觉修正规则
    normalized["accounting_firm"] = _fix_hallucination_by_rules(
        _extract_accounting_firm(text, normalized.get("accounting_firm", "")),
        "accounting_firm"
    )
    # 回函地址：应用幻觉修正规则
    normalized["reply_address"] = _fix_hallucination_by_rules(
        normalized.get("reply_address", ""),
        "reply_address"
    )
    # 联系人和电话：优先取回函收件人，而非业务联系人
    reply_contact, reply_phone = _extract_reply_contact(
        text, normalized.get("contact_person", ""), normalized.get("phone", "")
    )
    normalized["contact_person"] = reply_contact
    normalized["phone"] = _normalize_phone(reply_phone)
    normalized["postal_code"] = _normalize_postal_code(normalized.get("postal_code", ""))
    normalized["debit_account"] = _extract_debit_account(text, normalized.get("debit_account", ""))
    normalized["cutoff_date"] = _correct_hallucinated_date(_normalize_date(normalized.get("cutoff_date", "")), text)
    # 起始/终止日期：优先从表格上方描述提取，回退到 AI 值
    text_start, text_end = _extract_date_range(text)
    normalized["start_date"] = _correct_hallucinated_date(_normalize_date(text_start) if text_start else _normalize_date(normalized.get("start_date", "")), text)
    normalized["end_date"] = _correct_hallucinated_date(_normalize_date(text_end) if text_end else _normalize_date(normalized.get("end_date", "")), text)
    # 印章日期：排除 FS 标记章日期，优先取落款区域的手写日期
    normalized["seal_date"] = _correct_hallucinated_date(_normalize_seal_date(normalized.get("seal_date", ""), text), text)
    # 落款名称：使用印章名称清理逻辑（去除签章类型、事务所名称等噪音）
    normalized["signature_name"] = _normalize_seal_name(normalized.get("signature_name", ""))
    # 询证函抬头（收件银行）：正则配合 AI 获取
    normalized["recipient_bank"] = _extract_recipient_bank(text, normalized.get("recipient_bank", ""))
    return normalized


def _check_format(text: str) -> dict[str, Any]:
    source = text or ""
    best_format = "unknown"
    best_score = -1
    best_keywords: list[str] = []

    for format_name, keywords in FORMAT_TEMPLATES.items():
        score = sum(1 for kw in keywords if kw in source)
        if score > best_score:
            best_score = score
            best_format = format_name
            best_keywords = keywords

    mismatches = []
    if best_format != "unknown":
        for kw in best_keywords:
            if kw not in source:
                mismatches.append(
                    {
                        "item": kw,
                        "expected": f"应包含关键字: {kw}",
                        "actual": "未识别到",
                        "severity": "high",
                    }
                )

    if best_score <= 0:
        best_format = "unknown"
        mismatches.append(
            {
                "item": "template",
                "expected": "格式一/格式二/验资询证函",
                "actual": "无法判定",
                "severity": "high",
            }
        )

    return {
        "format_type": best_format,
        "format_check_passed": len(mismatches) == 0 and best_format != "unknown",
        "format_mismatches": mismatches,
    }


def _compress_images_for_ai(image_paths: list[str], max_size=1600, quality=85) -> list[str]:
    """
    压缩图片以减小 API payload 大小，避免网关 502 错误。
    将 PNG 转为 JPEG 并限制最大尺寸。
    
    Returns:
        list[str]: 压缩后的图片路径列表（存放在临时目录）
    """
    from services.pdf.pdf_utils import resize_image_high_quality
    
    compressed_dir = tempfile.mkdtemp(prefix="compressed_")
    compressed_paths = []
    
    for i, path in enumerate(image_paths):
        out_path = os.path.join(compressed_dir, f"page_{i:03d}.jpg")
        success = resize_image_high_quality(
            path, out_path,
            max_width=max_size, max_height=max_size, quality=quality
        )
        if success:
            compressed_paths.append(out_path)
        else:
            # 压缩失败时使用原图
            compressed_paths.append(path)
    
    return compressed_paths


def extract_fields_from_images(image_paths: list[str]) -> dict:
    """
    从询证函图片中提取字段信息（支持多张图片一次性提交）
    
    Args:
        image_paths: 图片文件路径列表（支持单张或多张）
        
    Returns:
        dict: 提取的字段信息（含 raw_text）
    """
    # 压缩图片以减小 payload，避免大图导致网关 502
    compressed_paths = _compress_images_for_ai(image_paths)
    
    try:
        if len(compressed_paths) == 1:
            # 单张图片使用 file_base
            response = request_qwen35(
                question=FIELD_EXTRACTION_PROMPT,
                file_base=compressed_paths[0],
                show_request=False,
                temperature=0.01,
                top_p=0.1,
            ).strip()
        else:
            # 多张图片使用 file_ary
            response = request_qwen35(
                question=FIELD_EXTRACTION_PROMPT,
                file_ary=compressed_paths,
                show_request=False,
                pic_tip=True,
                temperature=0.01,
                top_p=0.1,
            ).strip()
        
        try:
            data = json.loads(fix_json(response))
            return data
        except Exception as e:
            print(f"JSON 解析失败: {e}, 原始响应: {response[:200]}")
            return {}
    finally:
        # 清理压缩临时文件
        compressed_dir = os.path.dirname(compressed_paths[0]) if compressed_paths else None
        if compressed_dir and compressed_dir.startswith(tempfile.gettempdir()):
            shutil.rmtree(compressed_dir, ignore_errors=True)


def process_confirmation_letter(pdf_path: str, output_dir: str = None) -> dict:
    """
    处理询证函 PDF 文件

    优化流程：所有页面图片一次性提交 AI，合并字段提取与文本提取，
    将原来的 2N 次 AI 调用减少为 1 次。

    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录（可选）

    Returns:
        dict: 识别结果
    """
    # 使用临时目录存放图片，处理完自动清理
    tmp_dir = tempfile.mkdtemp(prefix="confirmation_")

    try:
        # 1. PDF 转图片
        image_paths = split_pdf_to_images(pdf_path, tmp_dir, dpi=200)

        if not image_paths:
            raise ValueError("PDF 转换图片失败，未生成任何图片")

        # 2. 所有页面一次性提交 AI（合并字段提取 + 文本提取）
        result = extract_fields_from_images(image_paths)
        merged_text = result.pop("raw_text", "")

        # 3. 后处理：正则校验与规范化
        normalized = _validate_and_normalize_fields(result, merged_text)
        normalized.update(_check_format(merged_text))
        return normalized

    finally:
        # 4. 清理临时文件
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)


async def process_confirmation_letter_async(file_id: int):
    """
    后台任务处理询证函识别。

    采用三段式避免在 AI 调用期间持有 DB 连接（曾导致连接池耗尽）：
        1) 短 session：读取记录并置 processing，立即释放连接
        2) 不持连接：调用 AI（最长 10 分钟）
        3) 短 session：回写识别结果与状态
    """
    import asyncio
    from datetime import datetime as _dt
    from src.database import SessionLocal
    from src.confirmation_letter.models import ConfirmationFile, ConfirmationResult

    # 阶段 1：标记 processing，立刻释放连接
    async with SessionLocal() as db:
        conf_file = await db.get(ConfirmationFile, file_id)
        if not conf_file:
            return
        file_path = conf_file.file_path
        conf_file.status = "processing"
        conf_file.error_msg = None
        await db.commit()

    start_time = time.time()

    # 阶段 2：纯外部 IO，不持有任何 DB 连接
    try:
        async with ai_semaphore():
            result = await asyncio.to_thread(process_confirmation_letter, file_path)
    except Exception as e:
        print(f"Confirmation Letter Process Error: {e}")
        async with SessionLocal() as db:
            conf_file = await db.get(ConfirmationFile, file_id)
            if conf_file:
                conf_file.status = "failed"
                conf_file.error_msg = str(e)
                conf_file.recognition_duration = round((time.time() - start_time) * 1000, 2)
                conf_file.updated_at = _dt.utcnow()
                await db.commit()
        return

    # 阶段 3：回写结果
    async with SessionLocal() as db:
        conf_file = await db.get(ConfirmationFile, file_id)
        if not conf_file:
            return

        old_stmt = select(ConfirmationResult).where(ConfirmationResult.file_id == file_id)
        old_result = await db.execute(old_stmt)
        old = old_result.scalar_one_or_none()
        if old:
            await db.delete(old)

        conf_result = ConfirmationResult(
            file_id=file_id,
            user_id=conf_file.user_id,
            confirmation_no=result.get("confirmation_no", ""),
            recipient_bank=result.get("recipient_bank", ""),
            accounting_firm=result.get("accounting_firm", ""),
            reply_address=result.get("reply_address", ""),
            contact_person=result.get("contact_person", ""),
            phone=result.get("phone", ""),
            postal_code=result.get("postal_code", ""),
            debit_account=result.get("debit_account", ""),
            cutoff_date=result.get("cutoff_date", ""),
            start_date=result.get("start_date", ""),
            end_date=result.get("end_date", ""),
            seal_date=result.get("seal_date", ""),
            signature_name=result.get("signature_name", ""),
            format_type=result.get("format_type", "unknown"),
            format_check_passed=result.get("format_check_passed", False),
            format_mismatches_json=json.dumps(
                result.get("format_mismatches", []), ensure_ascii=False
            ),
        )
        db.add(conf_result)

        conf_file.status = "done"
        conf_file.recognition_duration = round((time.time() - start_time) * 1000, 2)
        conf_file.updated_at = _dt.utcnow()
        await db.commit()



