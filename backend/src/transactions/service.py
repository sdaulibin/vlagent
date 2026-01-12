"""
交易记录创建服务 - 将原始交易数据转换为数据库模型
"""
from typing import List, Optional

from src.transactions.models import (
    # 山东地方银行
    ShandongLocalSummary, ShandongLocalTransaction,
    # 光大银行
    EverbrightSummary, EverbrightTransaction,
    # 招商银行
    CmbSummary, CmbTransaction,
    # 济宁银行
    JiningSummary, JiningTransaction,
    # 广发银行
    CgbSummary, CgbTransaction,
    # 邮储银行
    PsbcSummary, PsbcTransaction,
    # 工商银行
    IcbcSummary, IcbcTransaction,
    # 建设银行
    CcbSummary, CcbTransaction,
    # 农业银行
    AbcSummary, AbcTransaction,
)


# ============================================================
# 山东地方银行（潍坊、莱商、齐鲁）记录创建
# ============================================================

def create_shandong_transaction_records(file_id: int, raw_transactions: list) -> List[ShandongLocalTransaction]:
    """将原始交易数据转换为山东地方银行交易记录"""
    records = []
    for idx, item in enumerate(raw_transactions):
        t = ShandongLocalTransaction(
            file_id=file_id,
            sequence=str(item.get("序号", idx + 1)),
            transaction_time=item.get("交易时间", ""),
            channel=item.get("交易渠道", ""),
            income=item.get("收入", ""),
            expense=item.get("支出", ""),
            balance=item.get("账户余额", ""),
            currency=item.get("币种", ""),
            counterparty_account=item.get("对方账号", ""),
            counterparty_name=item.get("对方户名", ""),
            description=item.get("摘要备注", "")
        )
        records.append(t)
    return records


def create_shandong_summary_record(file_id: int, summary_data: dict) -> Optional[ShandongLocalSummary]:
    """创建山东地方银行汇总记录"""
    if not summary_data:
        return None
    return ShandongLocalSummary(
        file_id=file_id,
        account_name=summary_data.get("账户名称", ""),
        account_number=summary_data.get("账(卡)号", ""),
        date_range=summary_data.get("起止日期", ""),
        income_count=summary_data.get("收入总笔数", ""),
        income_total=summary_data.get("收入总金额", ""),
        expense_count=summary_data.get("支出总笔数", ""),
        expense_total=summary_data.get("支出总金额", ""),
        has_stamp=summary_data.get("是否有盖章", ""),
        bank_name=summary_data.get("开户行", ""),
        stamp_type=summary_data.get("盖章类型", "")
    )


# ============================================================
# 光大银行记录创建
# ============================================================

def create_everbright_transaction_records(file_id: int, raw_transactions: list) -> List[EverbrightTransaction]:
    """将原始交易数据转换为光大银行交易记录"""
    records = []
    for idx, item in enumerate(raw_transactions):
        t = EverbrightTransaction(
            file_id=file_id,
            sequence=str(item.get("序号", idx + 1)),
            transaction_date=item.get("交易日期", ""),
            transaction_time=item.get("时间", ""),
            debit_credit=item.get("借/贷", ""),
            amount=item.get("交易金额", ""),
            balance=item.get("账户余额", ""),
            counterparty_account=item.get("对方账号", ""),
            counterparty_name=item.get("对方名称", ""),
            voucher_no=item.get("凭证号", ""),
            description=item.get("摘要", ""),
            serial_no=item.get("流水号", "")
        )
        records.append(t)
    return records


def create_everbright_summary_record(file_id: int, summary_data: dict) -> Optional[EverbrightSummary]:
    """创建光大银行汇总记录"""
    if not summary_data:
        return None
    return EverbrightSummary(
        file_id=file_id,
        account_name=summary_data.get("账户名称", ""),
        account_number=summary_data.get("账号", ""),
        date_range=summary_data.get("交易日期", ""),
        debit_amount=summary_data.get("借方发生额", ""),
        credit_amount=summary_data.get("贷方发生额", ""),
        debit_count=summary_data.get("借方笔数", ""),
        credit_count=summary_data.get("贷方笔数", "")
    )


# ============================================================
# 招商银行记录创建
# ============================================================

def create_cmb_transaction_records(file_id: int, raw_transactions: list) -> List[CmbTransaction]:
    """将原始交易数据转换为招商银行交易记录"""
    records = []
    for idx, item in enumerate(raw_transactions):
        t = CmbTransaction(
            file_id=file_id,
            serial_no=item.get("交易流水号", ""),
            transaction_date=item.get("交易日期", ""),
            debit_amount=item.get("借方(出账)", ""),
            credit_amount=item.get("贷方(入账)", ""),
            balance=item.get("余额", ""),
            counterparty_name=item.get("收(付)方名称", ""),
            counterparty_account=item.get("收(付)方账号", ""),
            description=item.get("摘要", ""),
            transaction_type=item.get("交易类型", ""),
            card_no=item.get("公司一卡通号", ""),
            print_instance_no=item.get("打印实例号", "")
        )
        records.append(t)
    return records


def create_cmb_summary_record(file_id: int, summary_data: dict) -> Optional[CmbSummary]:
    """创建招商银行汇总记录"""
    if not summary_data:
        return None
    return CmbSummary(
        file_id=file_id,
        account_number=summary_data.get("账号", ""),
        account_name=summary_data.get("账号名", ""),
        start_date=summary_data.get("开始日期", ""),
        end_date=summary_data.get("结束日期", ""),
        debit_count=summary_data.get("出账总笔数", ""),
        credit_count=summary_data.get("入账总笔数", ""),
        debit_total=summary_data.get("出账总金额", ""),
        credit_total=summary_data.get("入账总金额", ""),
        total_count=summary_data.get("笔数", "")
    )


# ============================================================
# 济宁银行记录创建
# ============================================================

def create_jining_transaction_records(file_id: int, raw_transactions: list) -> List[JiningTransaction]:
    """将原始交易数据转换为济宁银行交易记录"""
    records = []
    for idx, item in enumerate(raw_transactions):
        t = JiningTransaction(
            file_id=file_id,
            sequence=str(item.get("序号", idx + 1)),
            transaction_date=item.get("记账日期", ""),
            channel=item.get("交易渠道", ""),
            income=item.get("收入", ""),
            expense=item.get("支出", ""),
            balance=item.get("账户余额", ""),
            description=item.get("摘要备注", ""),
            counterparty_info=item.get("交易对手信息", "")
        )
        records.append(t)
    return records


def create_jining_summary_record(file_id: int, summary_data: dict) -> Optional[JiningSummary]:
    """创建济宁银行汇总记录"""
    if not summary_data:
        return None
    return JiningSummary(
        file_id=file_id,
        account_number=summary_data.get("账号", ""),
        account_name=summary_data.get("账户名称", ""),
        date_range=summary_data.get("起止日期", ""),
        currency=summary_data.get("币种", ""),
        income_total=summary_data.get("收入金额合计", ""),
        expense_total=summary_data.get("支出金额合计", ""),
        bank_name=summary_data.get("开户机构", "")
    )


# ============================================================
# 广发银行记录创建
# ============================================================

def create_cgb_transaction_records(file_id: int, raw_transactions: list, summary_id: int = None) -> List[CgbTransaction]:
    """将原始交易数据转换为广发银行交易记录"""
    records = []
    for idx, item in enumerate(raw_transactions):
        t = CgbTransaction(
            file_id=file_id,
            summary_id=summary_id,  # 关联汇总
            serial_no=item.get("流水号", ""),
            transaction_time=item.get("交易时间", ""),
            income=item.get("收入", ""),
            expense=item.get("支出", ""),
            balance=item.get("余额", ""),
            currency=item.get("币种", ""),
            counterparty_account=item.get("对方账号", ""),
            counterparty_name=item.get("对方户名", ""),
            transaction_branch=item.get("交易行所", ""),
            counterparty_bank_code=item.get("对方开户行联行号", ""),
            counterparty_bank=item.get("对方开户行", ""),
            voucher_no=item.get("凭证号", ""),
            description=item.get("摘要", ""),
            remark=item.get("备注", ""),
            postscript=item.get("附言", "")
        )
        records.append(t)
    return records


def create_cgb_summary_record(file_id: int, summary_data: dict) -> Optional[CgbSummary]:
    """创建单个广发银行汇总记录"""
    if not summary_data:
        return None
    return CgbSummary(
        file_id=file_id,
        account_name=summary_data.get("户名", ""),
        account_number=summary_data.get("账号", ""),
        date_range=summary_data.get("起止日期", ""),
        currency=summary_data.get("币种", ""),
        unit=summary_data.get("单位", ""),
        expense_total=summary_data.get("支出总金额", ""),
        expense_count=summary_data.get("支出总笔数", ""),
        income_total=summary_data.get("收入总金额", ""),
        income_count=summary_data.get("收入总笔数", ""),
        current_balance=summary_data.get("账户当前余额", ""),
        record_count=summary_data.get("记录数", "")
    )


def create_cgb_summary_records(file_id: int, summaries_data: list) -> List[CgbSummary]:
    """创建多个广发银行汇总记录（用于多汇总场景）"""
    records = []
    for summary_data in summaries_data:
        if summary_data:
            summary = create_cgb_summary_record(file_id, summary_data)
            if summary:
                records.append(summary)
    return records


# ============================================================
# 邮储银行记录创建
# ============================================================

def create_psbc_transaction_records(file_id: int, raw_transactions: list) -> List[PsbcTransaction]:
    """将原始交易数据转换为邮储银行交易记录"""
    records = []
    for idx, item in enumerate(raw_transactions):
        t = PsbcTransaction(
            file_id=file_id,
            serial_no=item.get("交易流水号", ""),
            global_route_no=item.get("全局路由号", ""),
            transaction_time=item.get("交易时间", ""),
            transaction_date=item.get("记账日期", ""),
            income=item.get("收入金额", ""),
            expense=item.get("支出金额", ""),
            balance=item.get("余额", ""),
            counterparty_account=item.get("对方账号", ""),
            counterparty_name=item.get("对方户名", ""),
            counterparty_bank=item.get("对方行名", ""),
            purpose=item.get("用途", ""),
            postscript=item.get("附言", ""),
            description=item.get("摘要", "")
        )
        records.append(t)
    return records


def create_psbc_summary_record(file_id: int, summary_data: dict) -> Optional[PsbcSummary]:
    """创建邮储银行汇总记录"""
    if not summary_data:
        return None
    return PsbcSummary(
        file_id=file_id,
        account_name=summary_data.get("户名", ""),
        account_number=summary_data.get("账号", ""),
        income_total=summary_data.get("收入总金额", ""),
        expense_total=summary_data.get("支出总金额", ""),
        income_count=summary_data.get("收入总笔数", ""),
        expense_count=summary_data.get("支出总笔数", ""),
        start_date=summary_data.get("起始日期", ""),
        end_date=summary_data.get("结束日期", "")
    )


# ============================================================
# 工商银行（中国工商银行）记录创建
# ============================================================

def create_icbc_transaction_records(file_id: int, raw_transactions: list) -> List[IcbcTransaction]:
    """将原始交易数据转换为工商银行交易记录"""
    records = []
    for idx, item in enumerate(raw_transactions):
        t = IcbcTransaction(
            file_id=file_id,
            transaction_time=item.get("交易时间", ""),
            income=item.get("转入金额", ""),
            expense=item.get("转出金额", ""),
            counterparty_account=item.get("对方账号", ""),
            debit_credit=item.get("借贷标志", ""),
            counterparty_name=item.get("对方单位", ""),
            counterparty_bank_code=item.get("对方行号", ""),
            description=item.get("摘要", ""),
            purpose=item.get("用途", "")
        )
        records.append(t)
    return records


def create_icbc_summary_record(file_id: int, summary_data: dict) -> Optional[IcbcSummary]:
    """创建工商银行汇总记录"""
    if not summary_data:
        return None
    return IcbcSummary(
        file_id=file_id,
        account_number=summary_data.get("账号", ""),
        account_name=summary_data.get("本方账号户名", ""),
        currency=summary_data.get("币种", ""),
        bank_name=summary_data.get("本方账号开户行", ""),
        date_range=summary_data.get("财务日期范围", "")
    )


# ============================================================
# 建设银行（中国建设银行）记录创建
# ============================================================

def create_ccb_transaction_records(file_id: int, raw_transactions: list) -> List[CcbTransaction]:
    """将原始交易数据转换为建设银行交易记录"""
    records = []
    for idx, item in enumerate(raw_transactions):
        t = CcbTransaction(
            file_id=file_id,
            account_number=item.get("账号", ""),
            transaction_time=item.get("交易时间", ""),
            debit_amount=item.get("借方发生额", ""),
            credit_amount=item.get("贷方发生额", ""),
            balance=item.get("余额", ""),
            currency=item.get("币种", ""),
            counterparty_name=item.get("对方户名", ""),
            counterparty_account=item.get("对方账号", ""),
            counterparty_bank=item.get("对方开户机构", ""),
            booking_date=item.get("记账日期", ""),
            description=item.get("摘要", ""),
            remark=item.get("备注", ""),
            transaction_serial=item.get("账户明细编号-交易流水号", ""),
            enterprise_serial=item.get("企业流水号", ""),
            voucher_type=item.get("凭证种类", ""),
            voucher_number=item.get("凭证号", ""),
            transaction_medium=item.get("交易介质编号", "")
        )
        records.append(t)
    return records


def create_ccb_summary_record(file_id: int, summary_data: dict) -> Optional[CcbSummary]:
    """创建建设银行汇总记录"""
    if not summary_data:
        return None
    return CcbSummary(
        file_id=file_id,
        account_name=summary_data.get("本方户名", ""),
        print_date=summary_data.get("打印日期", "")
    )


# ============================================================
# 农业银行（中国农业银行）记录创建
# ============================================================

def create_abc_transaction_records(file_id: int, raw_transactions: list) -> List[AbcTransaction]:
    """将原始交易数据转换为农业银行交易记录"""
    records = []
    for idx, item in enumerate(raw_transactions):
        t = AbcTransaction(
            file_id=file_id,
            transaction_time=item.get("交易时间", ""),
            income=item.get("收入金额", ""),
            expense=item.get("支出金额", ""),
            balance=item.get("账户余额", ""),
            counterparty_account=item.get("对方账号", ""),
            counterparty_name=item.get("对方户名", ""),
            counterparty_bank=item.get("对方开户行", ""),
            description=item.get("摘要", "")
        )
        records.append(t)
    return records


def create_abc_summary_record(file_id: int, summary_data: dict) -> Optional[AbcSummary]:
    """创建农业银行汇总记录
    
    注意：农业银行汇总信息分布在首页顶部和末页底部
    - 首页：账号、户名、币种、起止日期
    - 末页：总收入笔数、总收入金额、总支出笔数、总支出金额
    """
    if not summary_data:
        return None
    return AbcSummary(
        file_id=file_id,
        account_number=summary_data.get("账号", ""),
        account_name=summary_data.get("户名", ""),
        currency=summary_data.get("币种", ""),
        date_range=summary_data.get("起止日期", ""),
        income_count=summary_data.get("总收入笔数", ""),
        income_total=summary_data.get("总收入金额", ""),
        expense_count=summary_data.get("总支出笔数", ""),
        expense_total=summary_data.get("总支出金额", "")
    )


# 向后兼容的别名
create_transaction_records = create_shandong_transaction_records
create_summary_record = create_shandong_summary_record

