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
    header: Optional[str] = Field("", description="表头(如企业名称)")
    seal_code: Optional[str] = Field("", description="电子印章编码")


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


# 统一的外层 Response 结构
class CredentialExtractionResponse(BaseModel):
    credential_type: str = Field(..., description="凭证类型")
    extracted_data: dict = Field(..., description="抽取出的数据明细")
