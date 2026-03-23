"""
询证函识别服务

独立的识别处理流程，复用底层 PDF 工具和 AI 请求接口。
"""
import os
import json
import shutil
import tempfile
import re
from datetime import datetime
from typing import Any

from services.pdf.pdf_utils import split_pdf_to_images
from services.core.request_ai import request_qwen35
from src.json_repair import fix_json


# 字段提取提示词
FIELD_EXTRACTION_PROMPT = """
Role: 银行询证函信息提取专家

【绝对核心原则 - 所见即所得，零联想】
- 你是一个纯粹的 OCR 文字复制工具，只负责逐字复制图片中已经存在、肉眼可见的文字
- 【严禁】任何形式的推理、猜测、补全、联想、推断、推导
- 【严禁】根据上下文"推断"可能的值——即使你觉得"这里应该有XX"，如果图片中没有明确写出，就必须返回空字符串 ""
- 【严禁】添加任何图片中没有的字符，包括但不限于："公司"、"有限"、"股份"、"有限合伙"等后缀
- 【严禁】修正图片中的"错误"——图片写什么就提取什么，不要"纠正"
- 每个字段提取后，必须逐字对照原图验证：图片里这几个字真的存在吗？如果不确定，返回空字符串 ""
- 宁可漏提也不要错提——误报比漏报严重得多

Task: 从银行询证函扫描图片中精确提取以下 13 项字段信息，并输出文档的全部原文文字。

【重要】函件可能有多页图片，请综合所有图片内容提取字段，不要遗漏任何页面的信息。
例如：正文可能跨页，印章/盖章可能在最后一页，表格可能在中间页。

## 待提取字段及识别规则：

1. **confirmation_no (函证编号)**
   - 这是最重要的字段，请务必仔细查找
   - 常见位置：标题「银行询证函」附近（上方、下方、右侧），或页面右上角
   - 常见格式：「编号：xxx」「函证编号：xxx」「NO.xxx」「索引号：xxx」
   - 编号通常是字母+数字组合，如 hdsy-yh-008、XZ-2024-001 等
   - 关键字优先级：函证编号 > 询证函编号 > 编号 > NO. > 索引号
   - 注意：不包含页码后缀
   - 【注意】二维码/条形码下方的编号优先级最低，不要优先使用

2. **accounting_firm (事务所名称)**
   - 【重要】仅从「本公司聘请的xxx」或「聘请的xxx」句式中提取事务所名称
   - 事务所名称包含「会计师事务所」关键字
   - 必须提取完整全称，包括：事务所名 + （特殊普通合伙）+ 分所名称（如"济南分所""大连分所"等）
   - 示例："和信会计师事务所（特殊普通合伙）济南分所"、"安永华明会计师事务所（特殊普通合伙）济南分所"
   - 【绝对禁止】添加图片中没有的文字！例如：图片写的是"XX会计师事务所"，绝不能提取成"XX会计师事务所公司"或"XX会计公司"
   - 【逐字对照】提取后必须逐一字符与原图比对：图片里真的有这几个字吗？没有就删掉或返回空字符串
   - 【注意】不要将页面其他位置的公司名称（如落款公司、银行名称）误认为事务所名称
3. **reply_address (回函地址)**
   - 关键字：回函地址、收件地址、回函请寄、回函邮寄地址
   - 【绝对禁止】添加图片中没有的文字，包括"公司"、"省"、"市"等
   - 【逐字对照】地址必须与图片中完全一致，一个字都不能多、一个字都不能少
4. **contact_person (回函联系人)**
   - 【重要】当存在「业务联系人」和「回函收件人」两种联系人时，必须提取「回函收件人」
   - 优先级：回函收件人 > 回函联系人 > 收件人 > 联系人
   - 通常在「回函地址」之后出现
   - 【逐字对照】只提取图片中明确可见的姓名文字，不要联想添加任何字符
   - 【注意】不要把相邻的"电话"、"手机"、"邮箱"、"邮编"等字样错误提取到联系人中
   - 【注意】联系人姓名如果包含中划线（如"审计二部-路"），请完整提取，不要遗漏中划线及前面的内容。
   - 【注意】联系人姓名处如果盖有印章（如普华永道），请区分印章文字（如"道"被识别为"董"）与真实的姓名（如"静"），不要把印章文字当成姓名（如不要输出"董静"）。
   - 不要提取「业务联系人」
5. **phone (回函联系电话)**
   - 【最重要】只提取「回函信息区」的「联系电话」，这是事务所的联系用电话
   - 【绝对禁止】提取「公司签章区」的「公司经办人电话」或印章后面的「电话」！
   - 【位置区分】：
     - ✅ 正确：在「回函地址」「联系人」「邮编」附近的「联系电话」
     - ❌ 错误：在印章、落款、「公司经办人」、「职务」附近的「电话」
   - 【重要】提取与「回函收件人」对应的电话，不是「业务联系电话」
   - 通常紧跟回函收件人之后
   - 优先级：回函收件人旁的电话 > 业务联系电话
   - 【逐字对照】只提取图片中可见的数字和符号，不要联想添加任何内容
   - 【注意】如果存在多个电话，请全部提取，用逗号或者斜杠隔开。
   - 【注意】在提取电话时，坚决不要包含括号及其内部的任何无关文字（例如不要提取"(项目组成员)"或"(函证中心)"等字样）。
6. **postal_code (邮编)**
   - 6位数字格式
   - 【逐字对照】只提取图片中可见的数字，不要联想添加
7. **debit_account (扣费账号)**
   - 常见位置：正文第一页，通常在「截至」日期附近
   - 常见句式：「本公司谨授权贵行可从本公司 xxx 号支取办理本询证函回函服务的费用」
   - 也可能出现为：「扣费账号：xxx」「付款账号：xxx」「费用从账号 xxx 扣除」
   - 账号可能出现字母开头（如 NRA 等），请不要保留任何字母，只需提取纯数字账号
   - 提取账号时必须只提取数字内容，不要限制长度
   - 【逐字对照】只提取图片中可见的数字，不要联想添加任何内容
   - 如果找不到任何扣费/授权支付相关的账号，返回空字符串
8. **cutoff_date (截止日期)**
   - 「截至xxxx年xx月xx日」或「函证基准日」对应的日期
   - 【逐字对照】只提取图片中明确可见的日期数字，不要联想推断
9. **start_date (起始日期)**
   - 【最重要】从表格3的标题中提取，表格的标题一般为"3. 自xxxx年x月x日起至xxxx年x月x日期间内注销的银行存款账户"
   - 【禁止】绝对不能从正文第一段中提取起始日期！
   - 【逐字对照】只提取图片中明确可见的日期数字
10. **end_date (终止日期)**
   - 【最重要】从表格3的标题中提取，表格的标题一般为"3. 自xxxx年x月x日起至xxxx年x月x日期间内注销的银行存款账户"
   - 【禁止】绝对不能从正文第一段的审计期间描述中提取终止日期！
   - 【逐字对照】只提取图片中明确可见的日期数字
11. **seal_date (印章日期)**
   - 提取被询证单位（客户公司）落款处的日期
   - 常见位置：在公司名称和「预留签章/采用电子授权」下方，格式通常为手写的「xxxx年x月x日」
   - 也可能在「以下由被询证银行填列」上方的落款区域，或「资金归集」表的下方落款区域
   - 【最重要】页面右上角的蓝色方形标记章（如"FS""2025-07-25"）是事务所的收发章，其中的日期绝对不是 seal_date！
   - 【最重要】seal_date 必须是落款区域中手写或打印的「xxxx年x月x日」格式的日期，位于公司名称附近
   - 【逐字对照】手写日期务必仔细放大分辨原图中手写数字笔画的弯折处特征，确保每一位数字100%精确，不要猜测或联想
   - 【注意】如果落款区域的手写日期难以辨认，请尽力识别；实在无法辨认才返回空字符串
   - 【注意】不要从正文抬头、页眉、编号区域取日期
12. **signature_name (落款名称)**
   - 提取落款区域打印/手写的公司名称文字，即「预留签章/采用电子授权」上方的那行公司名称
   - 常见位置有两种格式：
     - 格式一：在「以下由被询证银行填列」上方的落款区域，打印的公司名称文字后跟「（预留签章/采用电子授权）」
     - 格式二：在「资金归集」表下方的落款区域，直接打印的公司名称文字
   - 【最重要】【逐字对照】如果公司名称被裁切或只显示了部分文字，只提取图片中可见的部分，绝对不要补全缺失的文字
   - 【最重要】请从打印/手写的文字中提取公司名称，不要从圆形红色印章图案中识别文字
   - 【最重要】以「预留签章/采用电子授权」上方那行打印文字为准，那才是 signature_name
   - 【绝对禁止】添加图片中没有的字符，如"公司"、"有限"等后缀
   - 【重要】signature_name 要的是被询证的客户公司名称（如"xx有限公司"），不是印章类型
   - 【重要】signature_name 不是会计师事务所/审计机构的名称，事务所名称应填入 accounting_firm 字段
   - 【重要】不要将页面上出现的「毕马威」「安永」「德勤」「普华永道」等事务所名称作为 signature_name
   - 【注意】不要返回「财务专用章」「公章」「合同专用章」等印章类型名称
   - 【注意】不要包含「预留签章」「采用电子授权」等非单位名称的文字
   - 【注意】如果无法识别公司名称，返回空字符串

13. **recipient_bank (询证函抬头/收件银行)**
   - 提取正文开头的收件银行全称（即被询证的银行网点）
   - 常见位置一：正文第一段，通常在「（以下简称"贵行"）」之前，如「青岛银行股份有限公司潍坊诸城支行」
   - 常见位置二：在特殊抬头中，位于紧接「致」或「致：」之后，如「致：青岛银行」，需提取「青岛银行」
   - 【逐字对照】只提取图片中明确可见的文字，不要添加"银行"、"支行"等图片中没有的后缀
   - 【注意】不要包含「（以下简称"贵行"）」等括号及内部文字
   - 【注意】不要包含「致」或「致：」等字样
   - 【注意】必须提取完整的支行或分行名称（如果有），不要遗漏

## 输出要求：
- 返回 JSON 格式
- 无法识别的字段返回空字符串 ""
- 日期格式统一为 YYYY-MM-DD
- raw_text 字段输出所有页面的全部原文文字，保持原文顺序，各页之间用换行分隔
- 仅输出 JSON，无需解释

## 最终检查（必须执行）：
在输出每个字段前，逐一字符与原图比对：
1. 图片中真的有这个字符吗？
2. 图片中的字符顺序是这样的吗？
3. 有没有多加任何字符（如"公司"、"有限"等后缀）？
如果有任何不确定，返回空字符串 "" 而不是猜测！

## JSON Schema:
{
    "confirmation_no": "",
    "accounting_firm": "",
    "reply_address": "",
    "contact_person": "",
    "phone": "",
    "postal_code": "",
    "debit_account": "",
    "cutoff_date": "",
    "start_date": "",
    "end_date": "",
    "seal_date": "",
    "signature_name": "",
    "recipient_bank": "",
    "raw_text": ""
}
"""

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



