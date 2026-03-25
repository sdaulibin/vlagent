# -----------------------
# 1. 身份证 (ID Card)
# -----------------------
ID_CARD_PROMPT = """
Role: 身份证件信息提取专家

Task: 请仔细识别并提取影像中的中华人民共和国居民身份证信息，并严格判断版式。如果不是身份证请不要强行提取。

## 提取要求：

1. 版式判断 (is_front_side)：
   - 如果影像包含人脸照片、姓名、性别、民族、出生、住址、公民身份号码，这属于**正面(人像面)**，返回 true。
   - 如果影像包含中华人民共和国居民身份证、签发机关、有效期限，这属于**反面(国徽面)**，返回 false。
   - 无法判断或不是身份证，返回 null。

2. 核心要素提取：
   - name (姓名): 完整提取。
   - has_face_photo (是否含有人脸照片): 正面通常有照片，若检测到人像则返回 true。
   - gender (性别): 男或女。
   - ethnicity (民族): 如汉。
   - birth_date (出生日期): 格式如 YYYY年MM月DD日。
   - address (住址): 完整地址。
   - document_type (证件类型): 如“居民身份证”。
   - id_number (证件号码): 18位数字/字母。
   - issuing_authority (签发机关): 发证公安局名称。
   - issue_date (签发日期): 格式如 YYYY.MM.DD。
   - expiry_date (证件到期日): 格式如 YYYY.MM.DD 或“长期”。

## 输出规则：
- 返回严格的 JSON 对象。
- 对于当前影像中未出现的字段，请返回空字符串 "" 或 null (布尔值情况)。
- 不要输出 markdown 标记及任何其他解释性文本。

## JSON Schema 示例:
{
    "is_front_side": true,
    "name": "",
    "has_face_photo": true,
    "gender": "",
    "ethnicity": "",
    "birth_date": "",
    "address": "",
    "document_type": "",
    "id_number": "",
    "issuing_authority": "",
    "issue_date": "",
    "expiry_date": ""
}
"""

# -----------------------
# 2. 电子印章 (Electronic Seal)
# -----------------------
ELECTRONIC_SEAL_PROMPT = """
Role: 电子印章信息提取专家

Task: 请从提供的电子印章影像中提取关键要素，包括文件类型和所有电子印章编码。

## 提取要求：
1. header (表头): 提取影像顶部的**文件类型名称**（如“早送尾箱交接单”、“业务申请表”等）。
2. seal_codes (电子印章编码列表): 
   - 扫描影像中出现的所有电子印章。
   - 【重要】**逐一识别每个不同的印章实例**。即便页面上有多个非常相似的印章，也请分别提取它们各自对应的编码。
   - **禁止直接重复第一个识别到的编码**。必须从每个物理位置不同的印章中提取其实际显示的编码内容。
   - 提取每个印章边缘下方的数字防伪码或编码（通常由大写字母和数字组成）。
   - 【注意】部分印章可能是倒立、侧转或倾斜的，请在识别时将其视为正常印章进行解析。
   - 将所有识别到的、**互不相同**或**物理位置不同**的印章编码依次放入列表中返回。

## 输出规则：
- 返回严格的 JSON 对象。
- seal_codes 必须是字符串列表。
- 不要输出 markdown 标记。

{
    "header": "",
    "seal_codes": []
}
"""

# -----------------------
# 3. 银行卡 (Bank Card)
# -----------------------
BANK_CARD_PROMPT = """
Role: 银行卡信息提取专家

Task: 判断版式是否为银行卡，并提取特定信息，特别是检查卡片是否已作废（剪角）。

## 提取要求：
1. is_bank_card_image (是否为银行卡影像): 如果画面主体是银行卡，返回 true。
2. card_number (卡号): 提取完整的银行卡号码（忽略空格）。
3. has_cut_corner (是否剪角): 
   - 仔细观察银行卡的四个边角（左上、右上、左下、右下）。
   - 如果任意一个角缺失（例如呈现三角形的缺口，或者被截断），这通常意味着银行卡已剪角作废。
   - 包含明显的切掉、剪掉痕迹，或者角部被背景色（如黑色、白色）替代的情况，均应返回 true。
   - 边角完整无缺、弧度正常则返回 false。

## 输出规则：
- 返回严格的 JSON 对象。
- 不要输出 markdown 标记。

{
    "is_bank_card_image": true,
    "card_number": "",
    "has_cut_corner": false
}
"""

# -----------------------
# 4. 电子凭证 (Electronic Credential)
# -----------------------
ELECTRONIC_CREDENTIAL_PROMPT = """
Role: 电子付款凭证信息提取专家

Task: 请从电子凭证/银行回单影像中提取关键交易信息，并特别关注是否有手写签字。

## 提取要求：
1. 基本交易信息：payer_name(付款人姓名/名称)、payer_account(付款人账号)、payee_name(收款人姓名/名称)、payee_account(收款人账号)、amount(交易金额)、transaction_date(交易时间)、serial_number(流水号)、purpose(附言/用途)。
2. 特殊标记提取：
   - has_handwritten_signature (是否有手写签字): 检查单据画面中（常在空白处或指定签名栏）是否存在“手写的”签字痕迹。有则返回 true，无则返回 false。
   - signature_content (手写签字的具体内容): 如果能识别出手写签字的名字或内容，请提取出来，否则返回 ""。

## 输出规则：
- 返回严格的 JSON 对象。
- 不要输出 markdown 标记。

{
    "payer_name": "",
    "payer_account": "",
    "payee_name": "",
    "payee_account": "",
    "amount": "",
    "transaction_date": "",
    "serial_number": "",
    "purpose": "",
    "has_handwritten_signature": true,
    "signature_content": ""
}
"""


# -----------------------
# 5. 网银申请书 (Online Banking Application)
# -----------------------
ONLINE_BANKING_APP_PROMPT = """
Role: 企业网银业务表单提取专家

Task: 处理复杂的网银申请书，准确提取企业、经办人、操作人员及权限明细。

## 提取要求：
1. 版式识别 (is_online_banking_app):
   - 判断所传影像是否为**企业网银、企业手机银行注册业务申请表**，是返回 true，否则返回 false。

2. 字段提取（根据给定字段尽量完整提取，无数据返回 ""）：
   - 企业名称 (enterprise_name)、营业执照号 (business_license)、其他证件号码 (other_id_number)。
   - 法定代表人姓名 (legal_rep_name)、法定代表人身份证号 (legal_rep_id)、手机号码 (legal_rep_phone)。
   - 经办人姓名 (handler_name)、经办人身份证号 (handler_id)、手机号码 (handler_phone)。
   - 业务详情：账号 (account_number)、权限 (permissions)、单笔限额 (single_limit)、日累计限额 (daily_limit)、日转账笔数 (daily_transfer_count)、扣费账户账号 (deduction_account)。
   - 功能勾选：渠道(如企业网银/手机银行)(channel)、录入(entry_permission)、审核(audit_permission)、管理(manage_permission)、其他(other_permission) （如有打勾或选中的，以文本形式标识如"是"或勾选的项目内容）。
   - 审核与签字：
     - 审核方式 (audit_method)
     - 法定代表人(授权代理人)签字 (legal_rep_signature)：若能识别出签字或印章内容请提取。
     - 法定代表人签字日期 (legal_rep_sign_date)
     - 银行经办人(签字/盖章) (bank_handler_signature)
     - 银行审核人(签字/盖章) (bank_auditor_signature)
     - 银行业务日期 (bank_sign_date)

3. 操作人员列表 (operators)：提取表格中列出的操作员记录。每条记录包含：姓名 (name)、身份证号 (id_number)、手机号 (phone)。

## 输出规则：
- 严格遵循以下的 JSON Schema，不输出除 JSON 外的任何多余字符。

{
    "is_online_banking_app": true,
    "enterprise_name": "",
    "business_license": "",
    "other_id_number": "",
    "legal_rep_name": "",
    "legal_rep_id": "",
    "legal_rep_phone": "",
    "handler_name": "",
    "handler_id": "",
    "handler_phone": "",
    "account_number": "",
    "permissions": "",
    "single_limit": "",
    "daily_limit": "",
    "daily_transfer_count": "",
    "deduction_account": "",
    "operators": [
        {
            "name": "",
            "id_number": "",
            "phone": ""
        }
    ],
    "channel": "",
    "entry_permission": "",
    "audit_permission": "",
    "manage_permission": "",
    "other_permission": "",
    "audit_method": "",
    "legal_rep_signature": "",
    "legal_rep_sign_date": "",
    "bank_handler_signature": "",
    "bank_auditor_signature": "",
    "bank_sign_date": ""
}
"""

# -----------------------
# 6. 违法犯罪告知书 (Notice of Illegal Activity)
# -----------------------
NOTICE_ILLEGAL_ACTIVITY_PROMPT = """
Role: 违法犯罪告知书审核专家

Task: 审核影像版式，并提取开户申请人确认信息，特别是手印签字检测。

## 提取要求：
1. 版式识别 (is_illegal_activity_notice):
   - 判断接收到该影像时，是否是关于买卖、出借、出租身份证件、银行账户、电话卡等涉嫌违法犯罪告知书。是返回 true。

2. 特定要素提取：
   - 账号/银行卡号 (bank_account)。
   - 开户申请人/被告知人签名 (applicant_signature): 识别签名文字内容。
   - 日期 (sign_date)。
   - 是否有手印 (has_fingerprint): 检查签名处是否按了红色的印泥手印。如果有红手印痕迹，返回 true，若只有签字没有手印返回 false。

## 输出规则：
- 返回严格的 JSON 对象。
- 不要输出 markdown 标记。

{
    "is_illegal_activity_notice": true,
    "bank_account": "",
    "applicant_signature": "",
    "sign_date": "",
    "has_fingerprint": false
}
"""

PROMPT_MAPPING = {
    "id_card": ID_CARD_PROMPT,
    "electronic_seal": ELECTRONIC_SEAL_PROMPT,
    "bank_card": BANK_CARD_PROMPT,
    "electronic_credential": ELECTRONIC_CREDENTIAL_PROMPT,
    "online_banking_app": ONLINE_BANKING_APP_PROMPT,
    "notice_illegal_activity": NOTICE_ILLEGAL_ACTIVITY_PROMPT
}
