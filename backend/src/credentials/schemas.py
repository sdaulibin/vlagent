from typing import Optional, List
from pydantic import BaseModel, Field


# -----------------------
# 1. 身份证 (ID Card)
# -----------------------
class IdCardResponse(BaseModel):
    is_front_side: Optional[bool] = Field(None, description="是否为身份证正面 (人像面)")
    name: Optional[str] = Field("", description="姓名")
    has_face_photo: Optional[bool] = Field(None, description="是否含有人脸照片")
    gender: Optional[str] = Field("", description="性别")
    ethnicity: Optional[str] = Field("", description="民族")
    birth_date: Optional[str] = Field("", description="出生日期")
    address: Optional[str] = Field("", description="住址")
    document_type: Optional[str] = Field("", description="证件类型(如:居民身份证)")
    id_number: Optional[str] = Field("", description="证件号码")
    issuing_authority: Optional[str] = Field("", description="签发机关")
    issue_date: Optional[str] = Field("", description="签发日期")
    expiry_date: Optional[str] = Field("", description="证件到期日")


# -----------------------
# 2. 电子印章 (Electronic Seal)
# -----------------------
class ElectronicSealResponse(BaseModel):
    header: Optional[str] = Field("", description="表头(如文件类型)")
    seal_codes: List[str] = Field(default_factory=list, description="电子印章编码列表")


# -----------------------
# 3. 银行卡 (Bank Card)
# -----------------------
class BankCardResponse(BaseModel):
    is_bank_card_image: Optional[bool] = Field(None, description="是否为银行卡影像")
    card_number: Optional[str] = Field("", description="银行卡号")
    has_cut_corner: Optional[bool] = Field(None, description="是否包含了剪角的痕迹")


# -----------------------
# 4. 电子凭证 (Electronic Credential)
# -----------------------
class ElectronicCredentialResponse(BaseModel):
    payer_name: Optional[str] = Field("", description="付款人姓名/名称")
    payer_account: Optional[str] = Field("", description="付款人账号")
    customer_number: Optional[str] = Field("", description="客户号")
    payee_name: Optional[str] = Field("", description="收款人姓名/名称")
    payee_account: Optional[str] = Field("", description="收款人账号")
    amount: Optional[str] = Field("", description="交易金额")
    transaction_date: Optional[str] = Field("", description="交易时间")
    serial_number: Optional[str] = Field("", description="流水号")
    purpose: Optional[str] = Field("", description="附言/用途")
    has_handwritten_signature: Optional[bool] = Field(None, description="是否有手写签字")
    signature_content: Optional[str] = Field("", description="手写签字的具体内容(如可识别)")


# -----------------------
# 5. 网银申请书 (Online Banking Application)
# -----------------------
class OperatorInfo(BaseModel):
    name: Optional[str] = Field("", description="操作用户姓名")
    id_number: Optional[str] = Field("", description="身份证号")
    phone: Optional[str] = Field("", description="手机号码")

class OnlineBankingAppResponse(BaseModel):
    is_online_banking_app: Optional[bool] = Field(None, description="是否为企业网银/手机银行注册业务申请表")
    # 企业与法人
    enterprise_name: Optional[str] = Field("", description="企业名称")
    business_license: Optional[str] = Field("", description="营业执照号")
    other_id_number: Optional[str] = Field("", description="其他证件号码")
    legal_rep_name: Optional[str] = Field("", description="法定代表人姓名")
    legal_rep_id: Optional[str] = Field("", description="法定代表人身份证号")
    legal_rep_phone: Optional[str] = Field("", description="法定代表人手机号码")
    
    # 经办人
    handler_name: Optional[str] = Field("", description="经办人姓名")
    handler_id: Optional[str] = Field("", description="经办人身份证号")
    handler_phone: Optional[str] = Field("", description="经办人手机号码")
    
    # 业务详情
    account_number: Optional[str] = Field("", description="账号")
    permissions: Optional[str] = Field("", description="权限")
    single_limit: Optional[str] = Field("", description="单笔限额")
    daily_limit: Optional[str] = Field("", description="日累计限额")
    daily_transfer_count: Optional[str] = Field("", description="日转账笔数")
    deduction_account: Optional[str] = Field("", description="扣费账户账号")
    
    # 操作人员列表
    operators: List[OperatorInfo] = Field(default_factory=list, description="操作用户列表")
    
    # 功能勾选
    channel: Optional[str] = Field("", description="渠道(如网银/手机银行)")
    entry_permission: Optional[str] = Field("", description="录入权限标志")
    audit_permission: Optional[str] = Field("", description="审核权限标志")
    manage_permission: Optional[str] = Field("", description="管理权限标志")
    other_permission: Optional[str] = Field("", description="其他权限标志")
    
    # 审核与签字区
    audit_method: Optional[str] = Field("", description="审核方式")
    legal_rep_signature: Optional[str] = Field("", description="法定代表人(或授权代理人)签字内容")
    legal_rep_sign_date: Optional[str] = Field("", description="法定代表人签字日期")
    bank_handler_signature: Optional[str] = Field("", description="银行经办人(签字/盖章)")
    bank_auditor_signature: Optional[str] = Field("", description="银行审核人(签字/盖章)")
    bank_sign_date: Optional[str] = Field("", description="银行业务日期")


# -----------------------
# 6. 违法犯罪告知书 (Notice of Illegal Activity)
# -----------------------
class NoticeOfIllegalActivityResponse(BaseModel):
    is_illegal_activity_notice: Optional[bool] = Field(None, description="是否为涉嫌违法犯罪告知书")
    bank_account: Optional[str] = Field("", description="账号(银行卡号)")
    applicant_signature: Optional[str] = Field("", description="开户申请人(被告知人)签名")
    sign_date: Optional[str] = Field("", description="日期")
    has_fingerprint: Optional[bool] = Field(None, description="签名处是否有手印")


# -----------------------
# 7. 开户申请书 (Account Opening Application)
# -----------------------
class AccountOpeningAppResponse(BaseModel):
    is_account_opening_app: Optional[bool] = Field(None, description="是否为开立单位银行账户申请书")
    depositor_name_cn: Optional[str] = Field("", description="存款人名称（中文）")
    depositor_type: Optional[str] = Field("", description="存款人类别")
    tax_registration_cert: Optional[str] = Field("", description="税务登记证")
    org_code_cert: Optional[str] = Field("", description="组织机构代码证")
    proof_file_type: Optional[str] = Field("", description="证明文件种类")
    proof_file_number: Optional[str] = Field("", description="证明文件编号")
    registered_address: Optional[str] = Field("", description="注册地址")
    business_scope: Optional[str] = Field("", description="经营范围")
    
    # 人员信息
    legal_rep_name: Optional[str] = Field("", description="法定代表人/单位负责人姓名")
    legal_rep_phone: Optional[str] = Field("", description="法定代表人联系电话")
    legal_rep_id_type: Optional[str] = Field("", description="法定代表人证件种类")
    legal_rep_id_number: Optional[str] = Field("", description="法定代表人证件号码")
    financial_manager_1_name: Optional[str] = Field("", description="财务负责人1姓名")
    financial_manager_1_phone: Optional[str] = Field("", description="财务负责人1联系电话")
    financial_manager_2_name: Optional[str] = Field("", description="财务负责人2姓名")
    financial_manager_2_phone: Optional[str] = Field("", description="财务负责人2联系电话")
    bus_handler_name: Optional[str] = Field("", description="业务经办人姓名")
    bus_handler_phone: Optional[str] = Field("", description="业务经办人联系电话")
    
    # 账户详情
    account_nature: Optional[str] = Field("", description="账户性质")
    fixed_term_account: Optional[str] = Field("", description="定期类账户")
    general_account_reason: Optional[str] = Field("", description="申请一般户原因")
    special_account_fund_nature: Optional[str] = Field("", description="专用户资金性质")
    expiry_date: Optional[str] = Field("", description="有效日期至")
    currency: Optional[str] = Field("", description="申请开户币种")
    
    # 账户服务
    other_account_services: Optional[str] = Field("", description="其他账户服务")
    use_account_password: Optional[str] = Field("", description="使用账户密码")
    tax_resident_declaration: Optional[str] = Field("", description="机构税收居民身份声明")
    
    # 开通服务 (Boolean)
    open_online_banking: Optional[bool] = Field(None, description="开通网上银行")
    open_mobile_banking: Optional[bool] = Field(None, description="开通手机银行")
    open_sms_notice: Optional[bool] = Field(None, description="开通短信通知")
    open_phone_reconciliation: Optional[bool] = Field(None, description="开通电话对账")
    open_official_web_reconciliation: Optional[bool] = Field(None, description="开通官网对账")
    
    # 服务详情
    online_banking_services_detail: Optional[str] = Field("", description="网上银行手机银行服务框里的全部内容")
    sms_notice_details: Optional[str] = Field("", description="短信通知服务信息")
    
    # 银行记录
    bank_name: Optional[str] = Field("", description="开户银行名称")
    bank_code: Optional[str] = Field("", description="开户银行代码")
    account_name: Optional[str] = Field("", description="账户名称")
    account_number: Optional[str] = Field("", description="账号")
    basic_account_license_no: Optional[str] = Field("", description="基本存款账户开户许可证核准号")
    open_date: Optional[str] = Field("", description="开户日期")
    
    # 签章区域
    depositor_seal: Optional[str] = Field("", description="存款人公章名称")
    legal_rep_seal: Optional[str] = Field("", description="法定代表人名章名字")
    handler_signature: Optional[str] = Field("", description="经办人签名")
    sign_date: Optional[str] = Field("", description="日期")
    bottom_line_content: Optional[str] = Field("", description="申请书最下面一行的内容")


# -----------------------
# 8. 授权委托书 (Power of Attorney)
# -----------------------
class AuthorizedItem(BaseModel):
    """单个授权事项"""
    name: str = Field(..., description="业务项目名称")
    checked: bool = Field(False, description="是否打勾(√)")


class AuthorizedItemsByCategory(BaseModel):
    """授权事项按类别分组（包含所有项目及其勾选状态）"""
    opening: List[AuthorizedItem] = Field(default_factory=list, description="开户类业务")
    change: List[AuthorizedItem] = Field(default_factory=list, description="变更类业务")
    cancellation: List[AuthorizedItem] = Field(default_factory=list, description="注销类业务")
    other: List[str] = Field(default_factory=list, description="其他业务（手写或机打内容）")


class PowerOfAttorneyResponse(BaseModel):
    is_power_of_attorney: bool = Field(..., description="是否为授权委托书")
    principal_name: str = Field("", description="本人(委托人)")
    principal_id_number: str = Field("", description="身份证件号码")
    authorized_items_by_category: AuthorizedItemsByCategory = Field(
        default_factory=AuthorizedItemsByCategory,
        description="授权事项按类别分组（包含所有项目及其勾选状态）"
    )
    is_employee: bool = Field(False, description="是否为本单位职工")
    authorized_person_id_number: str = Field("", description="被授权人身份证号码")
    authorized_date: str = Field("", description="代表本人在（日期）")
    seal_date: str = Field("", description="公章下面的日期")
    authorized_person_signature: str = Field("", description="被授权人签字")
    sign_date: str = Field("", description="日期")


# 统一的外层 Response 结构
class CredentialExtractionResponse(BaseModel):
    credential_type: str = Field(..., description="凭证类型")
    extracted_data: dict = Field(..., description="抽取出的数据明细")
