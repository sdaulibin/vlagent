// 银行类型
export type BankType = 'shandong_local' | 'everbright' | 'cmb' | 'jining' | 'cgb' | 'psbc';

// 统一交易记录接口（包含所有银行的字段）
export interface Transaction {
    id: number;
    bank_type?: BankType;

    // 通用字段
    sequence?: string;
    balance?: string;
    counterparty_account?: string;
    counterparty_name?: string;
    description?: string;

    // 山东地方银行字段
    transaction_time?: string;
    channel?: string;
    income?: string;
    expense?: string;
    currency?: string;

    // 光大银行字段
    transaction_date?: string;
    time?: string;          // 时间
    debit_credit?: string;  // 借/贷
    amount?: string;
    voucher_no?: string;
    serial_no?: string;

    // 招商银行字段
    transaction_serial_no?: string;  // 交易流水号
    debit_amount?: string;   // 借方出账
    credit_amount?: string;  // 贷方入账
    transaction_type?: string;
    card_no?: string;
    print_instance_no?: string;

    // 济宁银行字段
    counterparty_info?: string;  // 交易对手信息

    // 广发银行字段
    transaction_branch?: string;      // 交易行所
    counterparty_bank_code?: string;  // 对方开户行联行号
    counterparty_bank?: string;       // 对方开户行
    remark?: string;                  // 备注
    postscript?: string;              // 附言
    summary_id?: number;              // 关联汇总ID（广发银行多汇总场景）
    global_route_no?: string;         // 全局路由号
    purpose?: string;                 // 用途
}

// 统一汇总接口（包含所有银行的字段）
export interface Summary {
    id?: number;
    file_id?: number;
    bank_type?: BankType;

    // 通用字段
    account_name?: string;
    account_number?: string;
    bank_name?: string;

    // 山东地方银行字段
    date_range?: string;
    income_count?: string;
    income_total?: string;
    expense_count?: string;
    expense_total?: string;
    has_stamp?: string;
    stamp_type?: string;

    // 光大银行字段
    debit_amount?: string;   // 借方发生额
    credit_amount?: string;  // 贷方发生额
    debit_count?: string;    // 借方笔数
    credit_count?: string;   // 贷方笔数

    // 招商银行字段
    start_date?: string;
    end_date?: string;
    debit_total?: string;    // 出账总金额
    credit_total?: string;   // 入账总金额
    total_count?: string;    // 笔数

    // 济宁银行字段
    currency?: string;       // 币种

    // 广发银行字段
    unit?: string;           // 单位
    current_balance?: string;  // 账户当前余额
    record_count?: string;     // 记录数
}

export interface FileItem {
    id: number;
    name: string;
    size: string;
    status: 'pending' | 'uploading' | 'done' | 'error';
    recognition_duration?: number;
    bank_type?: BankType;
}

// 银行类型显示名称映射
export const BANK_TYPE_NAMES: Record<BankType, string> = {
    'shandong_local': '山东地方银行',
    'everbright': '光大银行',
    'cmb': '招商银行',
    'jining': '济宁银行',
    'cgb': '广发银行',
    'psbc': '邮储银行'
};

