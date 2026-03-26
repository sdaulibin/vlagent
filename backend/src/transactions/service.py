"""
交易记录创建服务 - 将原始交易数据转换为数据库模型
"""
from typing import List, Optional
from decimal import Decimal

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
    # 中国银行
    BocSummary, BocTransaction,
    # 交通银行
    BocomSummary, BocomTransaction,
)


# ============================================================
# 辅助函数
# ============================================================

def _to_decimal_or_none(value) -> Optional[Decimal]:
    """将字符串转换为 Decimal，空字符串返回 None"""
    if value is None or value == "":
        return None
    # 移除千分位逗号
    clean_value = str(value).replace(",", "").strip()
    if not clean_value:
        return None
    return Decimal(clean_value)


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
            transaction_time=item.get("交易时间", "") or None,
            channel=item.get("交易渠道", "") or None,
            income=_to_decimal_or_none(item.get("收入")),
            expense=_to_decimal_or_none(item.get("支出")),
            balance=_to_decimal_or_none(item.get("账户余额")),
            currency=item.get("币种", "") or None,
            counterparty_account=item.get("对方账号", "") or None,
            counterparty_name=item.get("对方户名", "") or None,
            description=item.get("摘要备注", "") or None
        )
        records.append(t)
    return records


def create_shandong_summary_record(file_id: int, summary_data: dict) -> Optional[ShandongLocalSummary]:
    """创建山东地方银行汇总记录"""
    if not summary_data:
        return None
    return ShandongLocalSummary(
        file_id=file_id,
        account_name=summary_data.get("账户名称", "") or None,
        account_number=summary_data.get("账(卡)号", "") or None,
        date_range=summary_data.get("起止日期", "") or None,
        income_count=summary_data.get("收入总笔数", "") or None,
        income_total=_to_decimal_or_none(summary_data.get("收入总金额")),
        expense_count=summary_data.get("支出总笔数", "") or None,
        expense_total=_to_decimal_or_none(summary_data.get("支出总金额")),
        has_stamp=summary_data.get("是否有盖章", "") or None,
        bank_name=summary_data.get("开户行", "") or None,
        stamp_type=summary_data.get("盖章类型", "") or None
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
            transaction_date=item.get("交易日期", "") or None,
            transaction_time=item.get("时间", "") or None,
            debit_credit=item.get("借/贷", "") or None,
            amount=_to_decimal_or_none(item.get("交易金额")),
            balance=_to_decimal_or_none(item.get("账户余额")),
            counterparty_account=item.get("对方账号", "") or None,
            counterparty_name=item.get("对方名称", "") or None,
            voucher_no=item.get("凭证号", "") or None,
            description=item.get("摘要", "") or None,
            serial_no=item.get("流水号", "") or None
        )
        records.append(t)
    return records


def create_everbright_summary_record(file_id: int, summary_data: dict) -> Optional[EverbrightSummary]:
    """创建光大银行汇总记录"""
    if not summary_data:
        return None
    return EverbrightSummary(
        file_id=file_id,
        account_name=summary_data.get("账户名称", "") or None,
        account_number=summary_data.get("账号", "") or None,
        date_range=summary_data.get("交易日期", "") or None,
        debit_amount=_to_decimal_or_none(summary_data.get("借方发生额")),
        credit_amount=_to_decimal_or_none(summary_data.get("贷方发生额")),
        debit_count=summary_data.get("借方笔数", "") or None,
        credit_count=summary_data.get("贷方笔数", "") or None
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
            serial_no=item.get("交易流水号", "") or None,
            transaction_date=item.get("交易日期", "") or None,
            debit_amount=_to_decimal_or_none(item.get("借方(出账)")),
            credit_amount=_to_decimal_or_none(item.get("贷方(入账)")),
            balance=_to_decimal_or_none(item.get("余额")),
            counterparty_name=item.get("收(付)方名称", "") or None,
            counterparty_account=item.get("收(付)方账号", "") or None,
            description=item.get("摘要", "") or None,
            transaction_type=item.get("交易类型", "") or None,
            card_no=item.get("公司一卡通号", "") or None,
            print_instance_no=item.get("打印实例号", "") or None
        )
        records.append(t)
    return records


def create_cmb_summary_record(file_id: int, summary_data: dict) -> Optional[CmbSummary]:
    """创建招商银行汇总记录"""
    if not summary_data:
        return None
    return CmbSummary(
        file_id=file_id,
        account_number=summary_data.get("账号", "") or None,
        account_name=summary_data.get("账号名", "") or None,
        start_date=summary_data.get("开始日期", "") or None,
        end_date=summary_data.get("结束日期", "") or None,
        debit_count=summary_data.get("出账总笔数", "") or None,
        credit_count=summary_data.get("入账总笔数", "") or None,
        debit_total=_to_decimal_or_none(summary_data.get("出账总金额")),
        credit_total=_to_decimal_or_none(summary_data.get("入账总金额")),
        total_count=summary_data.get("笔数", "") or None
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
            transaction_date=item.get("记账日期", "") or None,
            channel=item.get("交易渠道", "") or None,
            income=_to_decimal_or_none(item.get("收入")),
            expense=_to_decimal_or_none(item.get("支出")),
            balance=_to_decimal_or_none(item.get("账户余额")),
            description=item.get("摘要备注", "") or None,
            counterparty_info=item.get("交易对手信息", "") or None
        )
        records.append(t)
    return records


def create_jining_summary_record(file_id: int, summary_data: dict) -> Optional[JiningSummary]:
    """创建济宁银行汇总记录"""
    if not summary_data:
        return None
    return JiningSummary(
        file_id=file_id,
        account_number=summary_data.get("账号", "") or None,
        account_name=summary_data.get("账户名称", "") or None,
        date_range=summary_data.get("起止日期", "") or None,
        currency=summary_data.get("币种", "") or None,
        income_total=_to_decimal_or_none(summary_data.get("收入金额合计")),
        expense_total=_to_decimal_or_none(summary_data.get("支出金额合计")),
        bank_name=summary_data.get("开户机构", "") or None
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
            serial_no=item.get("流水号", "") or None,
            transaction_time=item.get("交易时间", "") or None,
            income=_to_decimal_or_none(item.get("收入")),
            expense=_to_decimal_or_none(item.get("支出")),
            balance=_to_decimal_or_none(item.get("余额")),
            currency=item.get("币种", "") or None,
            counterparty_account=item.get("对方账号", "") or None,
            counterparty_name=item.get("对方户名", "") or None,
            transaction_branch=item.get("交易行所", "") or None,
            counterparty_bank_code=item.get("对方开户行联行号", "") or None,
            counterparty_bank=item.get("对方开户行", "") or None,
            voucher_no=item.get("凭证号", "") or None,
            description=item.get("摘要", "") or None,
            remark=item.get("备注", "") or None,
            postscript=item.get("附言", "") or None
        )
        records.append(t)
    return records


def create_cgb_summary_record(file_id: int, summary_data: dict) -> Optional[CgbSummary]:
    """创建单个广发银行汇总记录"""
    if not summary_data:
        return None
    return CgbSummary(
        file_id=file_id,
        account_name=summary_data.get("户名", "") or None,
        account_number=summary_data.get("账号", "") or None,
        date_range=summary_data.get("起止日期", "") or None,
        currency=summary_data.get("币种", "") or None,
        unit=summary_data.get("单位", "") or None,
        expense_total=_to_decimal_or_none(summary_data.get("支出总金额")),
        expense_count=summary_data.get("支出总笔数", "") or None,
        income_total=_to_decimal_or_none(summary_data.get("收入总金额")),
        income_count=summary_data.get("收入总笔数", "") or None,
        current_balance=_to_decimal_or_none(summary_data.get("账户当前余额")),
        record_count=summary_data.get("记录数", "") or None
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
            serial_no=item.get("交易流水号", "") or None,
            global_route_no=item.get("全局路由号", "") or None,
            transaction_time=item.get("交易时间", "") or None,
            transaction_date=item.get("记账日期", "") or None,
            income=_to_decimal_or_none(item.get("收入金额")),
            expense=_to_decimal_or_none(item.get("支出金额")),
            balance=_to_decimal_or_none(item.get("余额")),
            counterparty_account=item.get("对方账号", "") or None,
            counterparty_name=item.get("对方户名", "") or None,
            counterparty_bank=item.get("对方行名", "") or None,
            purpose=item.get("用途", "") or None,
            postscript=item.get("附言", "") or None,
            description=item.get("摘要", "") or None
        )
        records.append(t)
    return records


def create_psbc_summary_record(file_id: int, summary_data: dict) -> Optional[PsbcSummary]:
    """创建邮储银行汇总记录"""
    if not summary_data:
        return None
    return PsbcSummary(
        file_id=file_id,
        account_name=summary_data.get("户名", "") or None,
        account_number=summary_data.get("账号", "") or None,
        income_total=_to_decimal_or_none(summary_data.get("收入总金额")),
        expense_total=_to_decimal_or_none(summary_data.get("支出总金额")),
        income_count=summary_data.get("收入总笔数", "") or None,
        expense_count=summary_data.get("支出总笔数", "") or None,
        start_date=summary_data.get("起始日期", "") or None,
        end_date=summary_data.get("结束日期", "") or None
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
            transaction_time=item.get("交易时间", "") or None,
            income=_to_decimal_or_none(item.get("转入金额")),
            expense=_to_decimal_or_none(item.get("转出金额")),
            counterparty_account=item.get("对方账号", "") or None,
            debit_credit=item.get("借贷标志", "") or None,
            counterparty_name=item.get("对方单位", "") or None,
            counterparty_bank_code=item.get("对方行号", "") or None,
            description=item.get("摘要", "") or None,
            purpose=item.get("用途", "") or None
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
            account_number=item.get("账号", "") or None,
            transaction_time=item.get("交易时间", "") or None,
            debit_amount=_to_decimal_or_none(item.get("借方发生额")),
            credit_amount=_to_decimal_or_none(item.get("贷方发生额")),
            balance=_to_decimal_or_none(item.get("余额")),
            currency=item.get("币种", "") or None,
            counterparty_name=item.get("对方户名", "") or None,
            counterparty_account=item.get("对方账号", "") or None,
            counterparty_bank=item.get("对方开户机构", "") or None,
            booking_date=item.get("记账日期", "") or None,
            description=item.get("摘要", "") or None,
            remark=item.get("备注", "") or None,
            transaction_serial=item.get("账户明细编号-交易流水号", "") or None,
            enterprise_serial=item.get("企业流水号", "") or None,
            voucher_type=item.get("凭证种类", "") or None,
            voucher_number=item.get("凭证号", "") or None,
            transaction_medium=item.get("交易介质编号", "") or None
        )
        records.append(t)
    return records


def create_ccb_summary_record(file_id: int, summary_data: dict) -> Optional[CcbSummary]:
    """创建建设银行汇总记录"""
    if not summary_data:
        return None
    return CcbSummary(
        file_id=file_id,
        account_name=summary_data.get("本方户名", "") or None,
        print_date=summary_data.get("打印日期", "") or None
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
            transaction_time=item.get("交易时间", "") or None,
            income=_to_decimal_or_none(item.get("收入金额")),
            expense=_to_decimal_or_none(item.get("支出金额")),
            balance=_to_decimal_or_none(item.get("账户余额")),
            counterparty_account=item.get("对方账号", "") or None,
            counterparty_name=item.get("对方户名", "") or None,
            counterparty_bank=item.get("对方开户行", "") or None,
            description=item.get("摘要", "") or None
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
        account_number=summary_data.get("账号", "") or None,
        account_name=summary_data.get("户名", "") or None,
        currency=summary_data.get("币种", "") or None,
        date_range=summary_data.get("起止日期", "") or None,
        income_count=summary_data.get("总收入笔数", "") or None,
        income_total=_to_decimal_or_none(summary_data.get("总收入金额")),
        expense_count=summary_data.get("总支出笔数", "") or None,
        expense_total=_to_decimal_or_none(summary_data.get("总支出金额"))
    )


# ============================================================
# 中国银行（中行）记录创建
# ============================================================

def create_boc_transaction_records(file_id: int, raw_transactions: list) -> List[BocTransaction]:
    """将原始交易数据转换为中国银行交易记录"""
    records = []
    for idx, item in enumerate(raw_transactions):
        t = BocTransaction(
            file_id=file_id,
            sequence=item.get("序号", "") or None,
            booking_date=item.get("记账日", "") or None,
            value_date=item.get("起息日", "") or None,
            transaction_type=item.get("交易类型", "") or None,
            voucher=item.get("凭证", "") or None,
            transaction_details=item.get("凭证号业务号用途摘要", "") or None,
            debit_amount=_to_decimal_or_none(item.get("借方发生额")),
            credit_amount=_to_decimal_or_none(item.get("贷方发生额")),
            balance=_to_decimal_or_none(item.get("余额")),
            reference_no=item.get("机构柜员流水", "") or None,
            notes=item.get("备注", "") or None
        )
        records.append(t)
    return records


def create_boc_summary_record(file_id: int, summary_data: dict) -> Optional[BocSummary]:
    """创建中国银行汇总记录"""
    if not summary_data:
        return None
    return BocSummary(
        file_id=file_id,
        account_number=summary_data.get("账号", "") or None,
        account_name=summary_data.get("账户名称", "") or None,
        currency=summary_data.get("币种", "") or None,
        account_type=summary_data.get("账户类型", "") or None,
        bank_name=summary_data.get("开户行", "") or None,
        start_date=summary_data.get("起始日期", "") or None,
        end_date=summary_data.get("截止日期", "") or None
    )


# 向后兼容的别名
create_transaction_records = create_shandong_transaction_records
create_summary_record = create_shandong_summary_record


# ============================================================
# 交通银行（交行）记录创建
# ============================================================

def create_bocom_transaction_records(file_id: int, raw_transactions: list) -> List[BocomTransaction]:
    """将原始交易数据转换为交通银行交易记录"""
    records = []
    for idx, item in enumerate(raw_transactions):
        t = BocomTransaction(
            file_id=file_id,
            sequence=item.get("序号", "") or None,
            accounting_date=item.get("会计日期", "") or None,
            transaction_date=item.get("交易日期", "") or None,
            transaction_name=item.get("交易名称", "") or None,
            voucher_type=item.get("凭证种类", "") or None,
            voucher_number=item.get("凭证号码", "") or None,
            debit_amount=_to_decimal_or_none(item.get("借方发生额")),
            credit_amount=_to_decimal_or_none(item.get("贷方发生额")),
            balance=_to_decimal_or_none(item.get("余额")),
            card_number=item.get("卡号", "") or None,
            transaction_location=item.get("交易地点", "") or None,
            counterparty_account=item.get("对方账号", "") or None,
            counterparty_name=item.get("对方户名", "") or None,
            counterparty_bank=item.get("对方行名", "") or None,
            description=item.get("摘要", "") or None,
            serial_no=item.get("流水号", "") or None
        )
        records.append(t)
    return records


def create_bocom_summary_record(file_id: int, summary_data: dict) -> Optional[BocomSummary]:
    """创建交通银行汇总记录"""
    if not summary_data:
        return None
    return BocomSummary(
        file_id=file_id,
        bank_branch=summary_data.get("开户机构", "") or None,
        account_number=summary_data.get("账号", "") or None,
        account_name=summary_data.get("户名", "") or None,
        currency=summary_data.get("币种", "") or None,
        year=summary_data.get("年份", "") or None,
        month=summary_data.get("月份", "") or None
    )
