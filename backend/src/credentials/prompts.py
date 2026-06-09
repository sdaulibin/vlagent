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
   - issue_date (签发日期): 从反面"有效期限"字段的起始日期提取，格式如 YYYY.MM.DD。
     例如"2020.12.01-2040.12.01"→ issue_date 为"2020.12.01"。
   - expiry_date (有效期限): 完整提取反面"有效期限"字段的原文，如"2020.12.01-2040.12.01"或"2020.12.01-长期"。

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
   - **区分相似字符**：严格区分以下易混淆字符对：
     - A vs N（A 封闭三角顶部，N 为斜线连接）
     - D vs O/0（D 右侧为竖直线，O/0 为弧线）
     - I vs 1 vs L（I 无上下横杠，1 有顶部斜线，L 为直角）
     - 5 vs S（5 上方为水平线，S 为连续曲线）
     - H vs Q、6 vs 9、0 vs Q
   - 编码通常由大写字母和数字组成，请逐个字符确认是大写字母还是数字。
   - 编码中的字符是紧密排列的，中间没有分隔符（没有横线"-"、空格或点）。如果编码看起来像 E-H-Q-1-S-L-2-C-5-W，实际编码应为 EHQ1SL2C5W。
   - **确认顺序**：核对每个字符的先后顺序（例如是 E-H-Q 还是 E-Q-H），确保完全一致。
3. **方向识别**：对于倒立的印章，请在脑中先旋转 180 度再以正向视角读取。

## 输出要求：
- header (表头): 提取影像顶部的**文件类型名称**（如"早送尾箱交接单"）。
- seal_codes (电子印章编码列表): 返回提取到的**所有印章实例**的编码。
- **编码长度固定为10位**，由大写字母和数字组成。如果识别结果不是10位，请重新逐字符核对。

## 输出格式 (严格 JSON):
{
    "header": "",
    "seal_codes": ["编码1", "编码2", "..."]
}
"""

# -----------------------


SEAL_CODE_VERIFY_PROMPT = """
Role: 印章编码逐字符核验专家

Task: 影像中有一枚或多枚电子印章，每枚印章底部有一行防伪编码。请对以下待验证编码进行逐字符核验。

## 旋转印章处理（极度重要）：
影像中的印章可能是**旋转180度倒置**的。对于倒置的印章：
1. 先在脑中将印章旋转180度，以正向视角读取
2. 旋转后字符顺序会**反转**（从右到左变成从左到右）
3. 旋转后部分字符形状变化：6旋转后变成9，9旋转后变成6，其他字母旋转后形状基本不变
4. 必须以旋转后的正向视角逐个字符读取，不要在倒置状态下直接识别

## 核验步骤：
1. 在影像中找到每枚印章的编码位置（通常在"业务受理章"字样正下方）
2. 判断该印章是否倒置，如果倒置则先在脑中旋转180度
3. **先数清楚编码一共有几个字符**，记录字符数量
4. 逐个字符与影像中的实际字符对照，注意字符数量必须一致
5. 特别注意以下易混淆字符：
   - E vs 6 vs B vs 5：E 中间有三条横线，6 是闭合圆弧带尾巴，B 右侧是两个弧，5 上方是水平横线
   - F vs E：F 只有两条横线，E 有三条
   - P vs F vs B：P 右侧是上半部弧线，F 无弧线
   - G vs 6 vs C：G 有右侧横杠/开口，6 是闭合圆弧，C 无右侧结构
   - U vs V vs W：U 底部是圆弧，V 底部是尖角，W 是两个 V 连接
   - A vs N：A 顶部是尖角封闭三角，N 是两条竖线加一条斜线
   - I vs 1 vs L：I 是无装饰的竖线，1 顶部有短斜线，L 是直角
   - 9 vs 8 vs 0：9 上部封闭下部开口，8 上下都封闭，0 完整圆环
6. 核对修正后的编码字符数量是否与影像中一致
7. 如果发现不一致，输出修正后的编码

## 输出格式 (严格 JSON):
{
    "verified_codes": ["修正后的编码1", "修正后的编码2"]
}
"""
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
- 

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
1. 基本交易信息：payer_name(付款人姓名/名称)、payer_account(付款人账号)、customer_number(客户号)、payee_name(收款人姓名/名称)、payee_account(收款人账号)、amount(交易金额)、transaction_date(交易时间)、serial_number(流水号)、purpose(附言/用途)。
2. 特殊标记提取：
   - has_handwritten_signature (是否有手写签字): 检查单据画面中（常在空白处或指定签名栏）是否存在"手写的"签字痕迹。有则返回 true，无则返回 false。
   - signature_content (手写签字的具体内容): 如果能识别出手写签字的名字或内容，请提取出来，否则返回 ""。

## 输出规则：
- 返回严格的 JSON 对象。
- 不要输出 markdown 标记。
- 严格按照字段含义提取，不要联想或猜测。如果影像中没有对应内容，该字段留空 ""。例如：payer_account 只能填银行账号，不能填手机号或客户号；customer_number 只能填客户号，不能填手机号或账号。

{
    "payer_name": "",
    "payer_account": "",
    "customer_number": "",
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
   【重要】人名中可能包含罕见字，请逐笔仔细辨别每个字的笔画结构，不要替换为形近常见字。例如：熇(火+高)不要误识为煊(火+宣)，烨不要误识为华。
   - 企业名称 (enterprise_name)、营业执照号 (business_license)、其他证件号码 (other_id_number)。
   - 法定代表人姓名 (legal_rep_name)：必须从表单中明确标注"法定代表人"标签旁提取姓名。
     **严禁混淆不同角色**：表单中可能同时出现法定代表人、经办人、操作员等多个人的姓名，
     legal_rep_name 只能取"法定代表人"标签对应的那个人，绝不能填入经办人或操作员的姓名。
   - 法定代表人身份证号 (legal_rep_id)、手机号码 (legal_rep_phone)。
   - 经办人姓名 (handler_name)：从"经办人"标签旁提取，不要与法定代表人混淆。
   - 经办人身份证号 (handler_id)、手机号码 (handler_phone)。
   - 扣费账户账号 (deduction_account)。
   - 审核与签字（位于表单底部两个栏）：
     - 审核方式 (audit_method)
     - 申请人声明栏：
       - 法定代表人(授权代理人)签字 (legal_rep_signature)：从底部左侧"申请人声明"栏中提取签字或印章内容。
       - 法定代表人签字日期 (legal_rep_sign_date)：申请人声明栏中的日期。
     - 银行（业务公章）栏：
       - 银行经办人(签字/盖章) (bank_handler_signature)：从底部右侧"银行（业务公章）"栏中提取"经办人"后的签字或印章内容。
       - 银行审核人(签字/盖章) (bank_auditor_signature)：从底部右侧"银行（业务公章）"栏中提取"审核人"后的签字或印章内容。
       - 银行业务日期 (bank_sign_date)：银行（业务公章）栏中的日期。

3. 企业需关联的账户列表 (linked_accounts)：提取"企业需关联的账户"表格中的每一行数据。每条记录包含：
   - account_number (账号)
   - ebank_query (企业网银-查询)：true/false
   - ebank_transfer (企业网银-转账)：true/false
   - mbank_query (手机银行-查询)：true/false
   - mbank_transfer (手机银行-转账)：true/false
   - single_limit (单笔限额)
   - daily_limit (日累计限额)
   - daily_transfer_count (日转账笔数)

4. 操作户信息列表 (operators)：提取"操作户信息"表格中的每一行数据。每条记录包含：
   - name (姓名)
   - id_number (身份证号码)
   - phone (手机号码)
   - ebank_channel (网银渠道)：true/false
   - mbank_channel (手机银行渠道)：true/false
   - entry_permission (录入)：true/false
   - audit_permission (审核)：true/false
   - manage_permission (管理)：true/false
   - other_permission (其他)：true/false

   **操作户表格列对齐规则（极度重要 — 易错）**：
   表格中"录入""审核""管理""其他"四列紧密排列，每列各有一个方框，从左到右依次对应。
   提取每一行时，必须用列标题（"录入""审核""管理""其他"）作为锚点，**从上到下沿列标题对齐**，找到该列对应的方框。
   禁止凭视觉印象跳配列。具体步骤：
   1. 先在表头找到"录入"二字的准确位置
   2. 从"录入"垂直向下对齐到当前数据行，读取该位置的方框 → entry_permission
   3. 再找到"审核"二字的准确位置，垂直向下对齐 → audit_permission
   4. 再找到"管理"二字的准确位置，垂直向下对齐 → manage_permission
   5. 再找到"其他"二字的准确位置，垂直向下对齐 → other_permission
   每列独立定位，禁止将相邻列的方框当作当前列的方框。

**手写符号判定规则（极度重要 — 每个字段必须逐框独立判断）**：
表单中所有方框内的符号均为**手写**，必须对每个方框逐一独立判定，禁止根据相邻项推测。
判定方法：只看单个方框内部，问：**方框内有两条独立线条交叉形成一个中心交叉点吗？**
- 有两条线交叉（×形）→ 手写叉号 → false
- 没有交叉点，只有一条连续勾线（√形）→ 手写对号 → true
- 方框完全空白 → false
**严禁"有墨迹就选 true"**：手写叉号×同样有墨迹，但表示不授权，必须判为 false。

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
    "deduction_account": "",
    "linked_accounts": [
        {
            "account_number": "",
            "ebank_query": false,
            "ebank_transfer": false,
            "mbank_query": false,
            "mbank_transfer": false,
            "single_limit": "",
            "daily_limit": "",
            "daily_transfer_count": ""
        }
    ],
    "operators": [
        {
            "name": "",
            "id_number": "",
            "phone": "",
            "ebank_channel": false,
            "mbank_channel": false,
            "entry_permission": false,
            "audit_permission": false,
            "manage_permission": false,
            "other_permission": false
        }
    ],
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
   - 账号/银行卡号 (bank_account)：
     * **逐位读取**，手写数字极易混淆，请仔细区分以下易混淆字符：
       - 1 vs 7（1 顶部有短斜线无横线，7 顶部有横线）
       - 0 vs 6 vs 9（0 是完整椭圆，6 上部封闭下部开口带尾巴，9 上部封闭下部开口朝上）
       - 3 vs 5（3 上下都开口，5 上方有水平横线）
       - 2 vs 7（2 底部有水平横线，7 无底部横线）
     * 银行卡号通常为16-19位，请先数清楚位数，确保没有多读或少读。
   - 开户申请人/被告知人签名 (applicant_signature): 识别签名文字内容。
   - 日期 (sign_date)：
     * **仔细区分手写数字**，特别是年份中的数字。
     * 先确定年份（4位），再确定月和日，确保每一位都准确。
     * 注意区分：2025 vs 2021（5 底部有弯钩，1 是直竖线），2 vs 7，0 vs 6。
   - 是否有手印 (has_fingerprint): 检查签名处是否按了红色的印泥手印。如果有红手印痕迹，返回 true，若只有签字没有手印返回 false。

## 输出规则：
- 返回严格的 JSON 对象。
- 不要输出 markdown 标记。
- 

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
3. 勾选要素识别 (极度重要 - 必须逐项精确对应)：

   这些业务选项（开通网上银行、开通手机银行、开通短信通知业务、开通电话对账、开通官网对账）通常在表单的**同一行内水平排列**，格式为：`[方框] 标签文字  [方框] 标签文字  [方框] 标签文字 ...`，方框在标签文字的左侧或紧邻处。由于多个方框和标签在同一行紧密排列，极易将相邻项的方框搞混。

   **符号判定规则**：
   - √ (对号) / V 形 / 一笔勾起 → true
   - × (叉号) / 两条线交叉 / 有中心交叉点 → false
   - 方框完全空白 → false

   **手写 vs 机打符号区分（极度重要）**：
   表单中的符号可能为**手写**或**机打（打印/盖章）**，两者的判定标准一致，但机打符号更容易被误判。请特别注意：
   - 机打叉号 × 的特征：线条工整、对称、粗细均匀、两端对齐，看起来像标准 × 符号或 ✗。**不要因为机打 × 看起来"整齐"或"像正式标记"就误判为对号。**
   - 机打对号 ✓ 的特征：线条工整的勾形，一笔弯折，没有交叉点。
   - **判定原则**：不管符号是手写还是机打，只看几何形状：
     - **有两条线交叉形成 × 形 → 一律 false**
     - **一笔勾起形成 √ 形 → 一律 true**
   - **严禁"有墨迹就是选中"**：机打 × 叉号同样表示不办理/不授权，绝不能因为方框内有清晰墨迹就判定为 true。

   **强制识别流程 (COT) — 必须严格按以下顺序逐个处理，禁止跳步**：

   步骤一：先从左到右扫描整行，列出所有方框位置及其紧邻的标签文字，建立对照表。
   步骤二：按照从左到右的顺序，对每个字段逐一执行：
     a) 用该字段的**完整标签文字**（如"开通短信通知业务"这6个字）作为锚点定位。
     b) 找到该标签文字**紧邻**的方框（可能在标签左侧或上方/下方）。
     c) 仅判读该方框内的符号。
   步骤三：每判完一个字段，立即记录结果，再处理下一个。禁止回头修改。

   **极易出错的相邻项 — 必须特别留意**：
   - "开通短信通知业务"（6个字）和"开通电话对账"（6个字）经常紧邻排列。
   - 必须读清楚标签文字到底写的是"短信"还是"电话"，再找其对应方框。
   - 禁止将"开通短信通知业务的方框当作"开通电话对账"的方框，反之亦然。
   - **判断方法**：先读出方框旁边的文字是"短信"还是"电话"，确认后再看方框内符号。

   **叉号 X 的含义**：本业务中，叉号 X 专门表示"不授权"或"不办理"。即使框内有墨迹，只要是叉号 X 形状，必须判定为 false。严禁仅凭"非空"就判定为 true。
4. 细节信息：包含账号(account_number)、申请原因(general_account_reason)、银行处理记录（银行名称、代码等）。

## 字段特殊说明（必须严格遵守）：

**字段类型约束（严禁填错类型）**：
- depositor_name_cn (存款人名称)：必须是**公司/单位名称**（通常包含"公司"、"有限"等字样），**严禁**填入统一社会信用代码（如9137开头的18位码）或组织机构代码。
- proof_file_number (证明文件编号)：通常是**统一社会信用代码**（18位，以9开头）或营业执照注册号。请仔细查找表单中"证明文件编号"或"文件编号"标签旁的内容。
- org_code_cert (组织机构代码)：通常是**9位或10位代码**（含短横线，如XXXXXXX-X），不是统一社会信用代码。
- legal_rep_id_type (法定代表人证件类型)：只能是证件类型名称（如"身份证"、"护照"等），**严禁**填入手机号码或其他数字。
- legal_rep_phone (法定代表人电话)：必须是**11位手机号码**，注意区分法定代表人手机号和其他人员手机号。
- financial_manager_1_name (财务负责人1姓名)：确认标签是"财务负责人1"或"财务主管"，提取该标签旁的姓名，**严禁**填入其他人员姓名。人名中可能含罕见字，如"灝"(氵+景)不要误识为"颦"或"濒"，"灏"和"灝"是异体字关系。
- basic_account_license_no (基本户开户许可证号)：通常以"J"开头，约14位，请**完整提取**，不要截断。
- registered_address (注册地址)：请**完整提取**地址全文，不要截断。
- business_scope (经营范围)：请**完整提取**全文，从第一个字到最后一个字，不要遗漏开头部分。
- bottom_line_content (底部文字内容)：这是表单最底部的一整行文字，通常格式为"本存款人已经于 XXXX年 X月 X日收到:开立单位银行账户申请 存人查询密码、☑其他：XXXXX"。请**从行首第一个字开始完整提取到行尾**，包括日期、冒号、空格、勾选标记(☑/√)和所有文字，不要只提取最后几个字。
- sign_date (签章日期) 和 open_date (开户日期)：仔细辨认年份中的每个数字，特别注意以下易混淆数字对：
  - **2 vs 6**：2的底部是水平横线或向左弯的尾巴；6的底部有向右的闭合圆圈。不要把2误识为6。
  - **6 vs 0**：6有弯钩，0是闭合椭圆。
  - 如实读取表单上的年份，不要预设年份。

**勾选字段特殊说明**：
- fixed_term_account (定期账户类型)：如果该行的所有选项（整存整取、零存整取等）都被打叉(×)或留空，该字段应为空字符串 ""。只有某个选项被勾选(√)时才填入对应类型名称。
- 财务负责人2姓名(financial_manager_2_name)：请确认其左侧是否有"财务负责人2"标签，且右侧有手写文字。若无手写内容，结果须为空。

**人名识别（极度重要）**：人名中常包含罕见字或异体字，必须逐笔仔细辨别每个字的偏旁部首和笔画结构，绝不能替换为形近常见字。特别留意：
- "灝"(左边是三点水氵，右边是景) vs "颦"(上面是频，下面是卑) vs "濒"(氵+频) — 三者完全不同
- "灏"和"灝"是同一个字的简繁/异体关系
- 辨别方法：先确认左偏旁是"氵"(水)还是其他偏旁，再看右半部分的结构

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

Task: 从银行授权委托书影像中提取关键信息，逐个判断每个方框内的符号类型。

## 符号识别规则 (极度重要 — 必须逐项精确对应)

授权委托书中的多个授权事项通常在表单上紧密排列（同行或相邻行），每个事项前各有一个方框。由于方框密集相邻，极易将一个事项的方框错配到另一个事项。

**符号判定规则**：
- √ (对号) / V 形 / 一笔勾起 → checked: true
- × (叉号) / 两条线交叉 / 有中心交叉点 → checked: false
- 方框完全空白 → checked: false

**手写 vs 机打符号区分（极度重要）**：
表单中的符号可能为**手写**或**机打（打印/盖章）**，两者的判定标准一致，但机打符号更容易被误判。请特别注意：
- 机打叉号 × 的特征：线条工整、对称、粗细均匀、两端对齐，看起来像标准 × 符号或 ✗。**不要因为机打 × 看起来"整齐"或"像正式标记"就误判为对号。**
- 机打对号 ✓ 的特征：线条工整的勾形，一笔弯折，没有交叉点。
- **判定原则**：不管符号是手写还是机打，只看几何形状：
  - **有两条线交叉形成 × 形 → 一律 checked: false**
  - **一笔勾起形成 √ 形 → 一律 checked: true**
- **严禁"有墨迹就是选中"**：机打 × 叉号同样表示不授权，绝不能因为方框内有清晰墨迹就判定为 checked: true。

**强制识别流程 (COT) — 必须严格按以下顺序逐个处理，禁止跳步**：

步骤一：先扫描整个授权事项区域，列出所有方框位置及其紧邻的事项文字，建立对照表。
步骤二：按照从上到下的顺序，逐个类别处理。对每个类别内的每个事项执行：
  a) 用该事项的**完整文字**（如"账户开户"、"签署税收居民身份声明文件"等）作为锚点定位。
  b) 确认方框位于该文字的**左侧**，且该方框紧邻这条文字（不是下方或上方的方框）。
  c) 仅判读该方框内的符号。
步骤三：每判完一个事项，立即记录结果，再处理下一个。禁止回头修改。
步骤四（类别边界验证）：每完成一个类别的所有项目后，**回头复查该类别的最后一项**：
  - 用该最后一项的文字（如"签署税收居民身份声明文件"）重新定位。
  - 确认你正在看的方框确实紧邻该文字，而不是紧邻下方下一类别的文字。
  - 如果复查结果与初次判断不同，以复查结果为准。

**极易出错的相邻项 — 必须特别留意**：
- 同类别内的事项文字高度相似（如"企业网上银行注册" vs "企业手机银行注册"、"企业网上银行变更" vs "企业手机银行变更" vs "企业短信通知变更"），必须逐字确认标签文字中的关键词（"网上" vs "手机" vs "短信"），再找其对应方框。
- 禁止将一个事项的方框当作相邻事项的方框。
- **判断方法**：先读出方框旁边的完整事项文字，确认是哪个事项后，再看方框内的符号。

**类别边界 — 最易出错的三个位置（禁止跳过）**：
三个类别纵向排列，每个类别的最后一项方框与其下方下一类别的第一项方框**上下紧邻、垂直对齐**，极易读错。出错时结果恰好反转（√↔×）。
1. 开户类→变更类边界：开户类第5项"签署税收居民身份声明文件"的方框，**正上方**是同一项文字，**正下方**是变更类第1项"账户信息变更"的方框。必须找"签署税收居民身份声明文件"这行文字左侧的方框，不要读下方的。
2. 变更类→注销类边界（**全表最高风险位置**）：变更类第6项"企业手机银行变更"的方框**正下方**紧邻"三、注销类"标题文字。"三"字的笔画可能造成方框内有墨迹的错觉。**必须严格做到**：先定位"企业手机银行变更"这7个字的文字行，再找该行左侧的方框，只看方框内部的交叉情况。忽略方框下方"三"字的视觉干扰。如果方框内是两条线交叉形成×，即使方框附近有其他文字/笔画，也必须判为 false。
3. 注销类末尾：注销类第4项"企业短信通知注销"之后可能紧邻"其他业务"区域，确认该方框对应的是"企业短信通知注销"而非其他内容。

**叉号 × 的含义**：本业务中，叉号 × 专门表示"不授权"。即使框内有墨迹，只要是叉号 × 形状，必须判定为 checked: false。严禁仅凭"非空"就判定为 true。

## 授权事项分类

### 一、开户类业务（opening）- 5个项目
1. 账户开户
2. 企业网上银行注册
3. 企业手机银行注册
4. 企业短信通知注册
5. 签署税收居民身份声明文件

### 二、变更类业务（change）- 6个项目
1. 账户信息变更
2. 预留印鉴变更
3. 公章变更
4. 企业网上银行变更
5. 企业短信通知变更
6. 企业手机银行变更

### 三、注销类业务（cancellation）- 4个项目
1. 账户销户
2. 企业网上银行注销
3. 企业手机银行注销
4. 企业短信通知注销

### 四、其他业务（other）
- 手写或打印的其他授权事项文字
- 按顿号、逗号、空格拆分为独立项目

## 输出格式

返回严格的 JSON，包含所有项目及其勾选状态：

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

重要提醒：
- 必须输出所有15个标准项目及其勾选状态
- 每个项目独立判断，不要根据其他项目推测
- 文档中可能有多个√，也可能大部分是×，或混合，都是正常的
- 相邻事项必须先读完整文字再配对方框，禁止凭视觉印象跳配
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
