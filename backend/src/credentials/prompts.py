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
   - document_type (证件类型): 如"居民身份证"。
   - id_number (证件号码): 18位数字/字母。
   - issuing_authority (签发机关): 发证公安局名称。
   - issue_date (签发日期): 格式如 YYYY.MM.DD。
   - expiry_date (证件到期日): 格式如 YYYY.MM.DD 或"长期"。

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
Role: 财务单据多印章高精度识别专家

Task: 识别影像中所有的电子印章，并提取每一枚印章的唯一编码。

## 特别注意 (Critical):
- 影像中可能包含**多张相互独立的表单或联次**（建议已在预处理中切分）。
- 每张独立表单中通常各有一枚印章。即便它们形态极其相似，其**防伪编码通常也是不同的**。
- **严禁直接复用第一个编码**或产生视觉残留错觉。必须对每一枚印章进行独立的局部区域扫描。

## 提取步骤：
1. **定位锚点**：寻找"**业务受理章**"字样，编码通常在其正下方。
2. **字符级校验 (极度重要)**：
   - 提取编码时，请**逐位读写**，不要凭直觉组合。
   - **区分相似字符**：严格区分 H 与 Q、6 与 9、A 与 V、0 与 Q。
   - **确认顺序**：核对每个字符的先后顺序（例如是 E-H-Q 还是 E-Q-H），确保完全一致。
3. **方向识别**：对于倒立的印章，请在脑中先旋转 180 度再以正向视角读取。

## 输出要求：
- header (表头): 提取影像顶部的**文件类型名称**（如"早送尾箱交接单"）。
- seal_codes (电子印章编码列表): 返回提取到的**所有印章实例**的编码。

## 输出格式 (严格 JSON):
{
    "header": "",
    "seal_codes": ["编码1", "编码2", "..."]
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
   - has_handwritten_signature (是否有手写签字): 检查单据画面中（常在空白处或指定签名栏）是否存在"手写的"签字痕迹。有则返回 true，无则返回 false。
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

# -----------------------
# 7. 开户申请书 (Account Opening Application)
# -----------------------
ACCOUNT_OPENING_APP_PROMPT = """
Role: 银行开户申请书信息抽取专家

Task: 识别《开立单位银行账户申请书》中的所有要素。请遵循"所见即所得"原则。

## 提取要求：
1. 版式识别 (is_account_opening_app): 确认为"开立单位银行账户申请书"才返回 true。
2. 要素提取 (所见即所得)：
   - **精确匹配标签**：请识别纸面上的打印标签文字（如"财务负责人1"、"业务经办人"、"财务负责人2"），并提取其右侧或下方的对应内容。
   - **严禁错位填充**：若某个标签（如"财务负责人2"）右侧没有任何文字内容，**必须返回空字符串 ""**。绝不可使用其他行（如"业务经办人"）的内容进行填充。

3. 【核心】勾选符号识别 (CHECKMARK vs CROSS)：

   ### 对号 √（选中/True）的几何特征：
   - **一笔连续**：从左上起笔，向右下斜行，到底部后向上挑起
   - **笔画走向**：↘ 然后 ↗，形成"钩"形
   - **无交叉点**：整个符号没有线条相交
   - **类似形状**：✓ ✔ √ V（一笔完成）

   ### 叉号 ×（未选中/False）的几何特征：
   - **两笔交叉**：两条线段从四个角出发，在中心交叉
   - **笔画走向**：↘ 和 ↙ 两条线，或者 ╱ 和 ╲ 两条线
   - **有交叉点**：中心有一个明显的交叉点
   - **类似形状**：✗ ✘ × X x（两笔交叉）

   ### 判定流程（必须执行）：
   对于每个 Boolean 字段，请按以下步骤判定：

   **步骤1 - 定位方框**：找到该字段对应的方框 [ ] 位置

   **步骤2 - 观察框内内容**：
   - 如果框内完全空白 → 返回 `false`
   - 如果框内有墨迹 → 进入步骤3

   **步骤3 - 笔划分析（关键）**：
   请放大观察框内笔划的物理形态：

   A. 数笔划数量：
      - 如果是**一笔**连续写完的 → 可能是 √，进入 A1
      - 如果是**两笔**交叉的 → 必定是 ×，返回 `false`

   B. 看线条走向：
      - 如果线条从**左上→右下→右上**（像个"钩"）→ 是 √，返回 `true`
      - 如果线条是**两条对角线交叉**（像个"乘号"）→ 是 ×，返回 `false`

   C. 找交叉点：
      - 如果有明显的**中心交叉点** → 是 ×，返回 `false`
      - 如果**没有交叉点**，线条是连续的 → 是 √，返回 `true`

   ### 常见错误纠正：
   - ❌ 错误：看到框内有墨迹就认为是 √
   - ✅ 正确：必须分析笔划形态，× 也是墨迹，但表示"不办理"
   - ❌ 错误：把 X 误认为 √
   - ✅ 正确：X 是两条线交叉，√ 是一笔钩形

4. 细节信息：包含账号(account_number)、申请原因(general_account_reason)、银行处理记录（银行名称、代码等）。

## 字段特殊说明：
- 财务负责人2姓名(financial_manager_2_name)：请确认其左侧是否有"财务负责人2"标签，且右侧有手写文字。若无手写内容，结果须为空。

## 输出格式 (严格 JSON):
{
    "is_account_opening_app": true,
    "depositor_name_cn": "",
    "depositor_type": "",
    "tax_registration_cert": "",
    "org_code_cert": "",
    "proof_file_type": "",
    "proof_file_number": "",
    "registered_address": "",
    "business_scope": "",
    "legal_rep_name": "",
    "legal_rep_phone": "",
    "legal_rep_id_type": "",
    "legal_rep_id_number": "",
    "financial_manager_1_name": "",
    "financial_manager_1_phone": "",
    "bus_handler_name": "",
    "bus_handler_phone": "",
    "financial_manager_2_name": "",
    "financial_manager_2_phone": "",
    "account_nature": "",
    "fixed_term_account": "",
    "general_account_reason": "",
    "special_account_fund_nature": "",
    "expiry_date": "",
    "currency": "",
    "other_account_services": "",
    "use_account_password": "",
    "tax_resident_declaration": "",
    "open_online_banking": false,
    "open_mobile_banking": false,
    "open_sms_notice": false,
    "open_phone_reconciliation": false,
    "open_official_web_reconciliation": false,
    "online_banking_services_detail": "",
    "sms_notice_details": "",
    "bank_name": "",
    "bank_code": "",
    "account_name": "",
    "account_number": "",
    "basic_account_license_no": "",
    "open_date": "",
    "depositor_seal": "",
    "legal_rep_seal": "",
    "handler_signature": "",
    "sign_date": "",
    "bottom_line_content": ""
}
"""

# -----------------------
# 8. 授权委托书 (Power of Attorney)
# -----------------------
POWER_OF_ATTORNEY_PROMPT = """
Role: 银行授权委托书识别专家

Task: 从银行授权委托书影像中提取关键信息，必须**逐项、独立、精确**识别所有授权事项的勾选状态（√或×）。

## 【最高优先级规则】默认 false，只有确定才返回 true

⚠️ **核心原则：宁可漏识，不可误识**
- 如果不确定符号是 √ 还是 ×，**必须返回 false**
- 只有当你**100%确定**看到的是一个"钩形"时，才返回 true
- 看到框内有墨迹**不代表**是打勾！× 也是墨迹！

## 【必须禁止的错误行为】

| ❌ 错误 | ✅ 正确 |
|--------|--------|
| 看到框内有墨迹就认为是√ | 必须分析形状，×也是墨迹 |
| 把X误认为√ | X有交叉点，√没有交叉点 |
| 根据项目名称推测勾选状态 | 只看方框内的实际符号 |
| 看到同类有一项√就认为其他也√ | 每项独立判断，互不影响 |
| 不确定时猜测 | 不确定时返回false |

## 授权事项分类（共四大类，每类有明确的业务项目）

### 一、开户类业务（opening）- 5个项目（必须全部识别）
1. 账户开户
2. 企业网上银行注册
3. 企业手机银行注册
4. 企业短信通知注册
5. 签署税收居民身份声明文件

### 二、变更类业务（change）- 6个项目（必须全部识别）
1. 账户信息变更
2. 预留印鉴变更
3. 公章变更
4. 企业网上银行变更
5. 企业短信通知变更
6. 企业手机银行变更

### 三、注销类业务（cancellation）- 4个项目（必须全部识别）
1. 账户销户
2. 企业网上银行注销
3. 企业手机银行注销
4. 企业短信通知注销

### 四、其他业务（other）
- 这是手写或机打的其他授权事项填写区域
- 【重要】必须完整提取该区域的**所有内容**
- 如果有多项内容，通常用以下分隔符分开：逗号（，）、顿号（、）、分号（；）、空格
- 必须逐个识别并拆分
- 例如："签约电话对账、官网对账、自助回单业务" 应拆分为3项：["签约电话对账", "官网对账", "自助回单业务"]
- 常见的其他业务包括：签约电话对账、官网对账、自助回单业务、大额预约、账户查询等

## 勾选符号识别规则（核心！必须严格遵守）

### ⭕ 只有以下情况才返回 checked: true

**打钩 √ 的几何特征（必须全部满足）：**
1. **一笔连续**：从起笔到收笔，中间不抬笔
2. **笔画走向**：从左上 → 右下 → 右上挑起（像一个"钩"）
3. **没有交叉点**：整条线没有与自己相交
4. **形状类似**：✓ ✔ √

⚠️ 只有当你能清晰看到上述"钩形"时，才返回 true

### ❌ 以下情况必须返回 checked: false

**打叉 × 的几何特征（满足任一即为×）：**
- 两条线段在**中心交叉**
- **有明显的交叉点**（这是最关键的区分特征！）
- 形状类似：✗ ✘ × X x

**空白方框：**
- 方框内完全没有墨迹

**模糊/不确定：**
- 如果你看不清楚，或者不确定是√还是×
- **必须返回 false**

## 【判定流程】对每个项目严格执行

**步骤1 - 定位方框：** 找到该项目名称对应的方框 [ ] 位置

**步骤2 - 观察框内：**
- 完全空白 → checked: false，结束
- 有墨迹 → 进入步骤3

**步骤3 - 放大分析（最关键）：**

A. **首先找交叉点（最可靠的判断依据）**
   - 如果能看到两条线在中心交叉 → 是 × → 返回 false
   - 如果没有交叉点 → 继续判断

B. **数笔画**
   - 如果是两笔交叉（一条从左上到右下，另一条从右上到左下）→ 是 × → 返回 false
   - 如果是一笔连续 → 可能是 √，继续判断

C. **看线条走向**
   - 如果是 左上→右下→右上挑起（钩形）→ 是 √ → 返回 true
   - 其他情况 → 返回 false

**步骤4 - 不确定处理**
   - 如果仍然不确定 → **必须返回 false**

## 【重要提醒】

1. 银行表单中，大多数项目通常是打×的（不办理），只有少数项目打√
2. 如果你发现所有项目都返回 true，那很可能是识别错误
3. 请逐个独立判断，不要受其他项目影响

## 输出规则

1. 开户类、变更类、注销类：必须输出【所有项目】及其勾选状态，不能遗漏
2. 每个项目用对象表示：{"name": "项目名称", "checked": true/false}
3. 其他业务：按分隔符拆分为独立项目，以字符串数组形式输出
4. 返回严格的 JSON 对象，不要输出任何解释性文字

## JSON Schema

{
    "is_power_of_attorney": true,
    "principal_name": "",
    "principal_id_number": "",
    "authorized_items_by_category": {
        "opening": [
            {"name": "账户开户", "checked": false},
            {"name": "企业网上银行注册", "checked": false},
            {"name": "企业手机银行注册", "checked": false},
            {"name": "企业短信通知注册", "checked": false},
            {"name": "签署税收居民身份声明文件", "checked": false}
        ],
        "change": [
            {"name": "账户信息变更", "checked": false},
            {"name": "预留印鉴变更", "checked": false},
            {"name": "公章变更", "checked": false},
            {"name": "企业网上银行变更", "checked": false},
            {"name": "企业短信通知变更", "checked": false},
            {"name": "企业手机银行变更", "checked": false}
        ],
        "cancellation": [
            {"name": "账户销户", "checked": false},
            {"name": "企业网上银行注销", "checked": false},
            {"name": "企业手机银行注销", "checked": false},
            {"name": "企业短信通知注销", "checked": false}
        ],
        "other": []
    },
    "is_employee": false,
    "authorized_person_id_number": "",
    "authorized_date": "",
    "seal_date": "",
    "authorized_person_signature": "",
    "sign_date": ""
}
"""

PROMPT_MAPPING = {
    "id_card": ID_CARD_PROMPT,
    "electronic_seal": ELECTRONIC_SEAL_PROMPT,
    "bank_card": BANK_CARD_PROMPT,
    "electronic_credential": ELECTRONIC_CREDENTIAL_PROMPT,
    "online_banking_app": ONLINE_BANKING_APP_PROMPT,
    "notice_illegal_activity": NOTICE_ILLEGAL_ACTIVITY_PROMPT,
    "account_opening_app": ACCOUNT_OPENING_APP_PROMPT,
    "power_of_attorney": POWER_OF_ATTORNEY_PROMPT
}
