import re

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

samples = [
    "青岛银行股份有限公司潍坊诸城支行（以下简称 “贵行”）：",
    "青岛银行股份有限公司威海分行（以下简称 “贵行”，即“函证收件人”）：",
    "青岛银行潍坊分行（以下简称 “贵行”）：",
    "青岛银行港口支行（以下简称 “贵行”，即“函证收件人”）：",
    "致：青岛银行",
    "致青岛银行",
    "致：青岛银行股份有限公司威海分行",
    "致： 招商银行济南分行",
]

for s in samples:
    print(f"[{s}] -> [{_extract_recipient_bank(s)}]")
