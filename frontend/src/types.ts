// 银行类型
export type BankType =
  | "shandong_local"
  | "everbright"
  | "cmb"
  | "jining"
  | "cgb"
  | "psbc"
  | "icbc"
  | "ccb"
  | "abc"
  | "boc"
  | "bocom";

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
  time?: string; // 时间
  debit_credit?: string; // 借/贷
  amount?: string;
  voucher_no?: string;
  serial_no?: string;

  // 招商银行字段
  transaction_serial_no?: string; // 交易流水号
  debit_amount?: string; // 借方出账
  credit_amount?: string; // 贷方入账
  transaction_type?: string;
  card_no?: string;
  print_instance_no?: string;

  // 济宁银行字段
  counterparty_info?: string; // 交易对手信息

  // 广发银行字段
  transaction_branch?: string; // 交易行所
  counterparty_bank_code?: string; // 对方开户行联行号
  counterparty_bank?: string; // 对方开户行
  remark?: string; // 备注
  postscript?: string; // 附言
  summary_id?: number; // 关联汇总ID（广发银行多汇总场景）
  global_route_no?: string; // 全局路由号
  purpose?: string; // 用途

  // 建设银行字段
  account_number?: string; // 账号
  booking_date?: string; // 记账日期
  transaction_serial?: string; // 账户明细编号-交易流水号
  enterprise_serial?: string; // 企业流水号
  voucher_type?: string; // 凭证种类
  voucher_number?: string; // 凭证号
  transaction_medium?: string; // 交易介质编号

  // 中国银行字段
  value_date?: string; // 起息日 Val.D.
  voucher?: string; // 凭证 Vou.
  transaction_details?: string; // 凭证号/业务号/用途/摘要
  reference_no?: string; // 机构/柜员/流水 Reference No.
  notes?: string; // 备注 Notes

  // 交通银行字段
  accounting_date?: string; // 会计日期
  transaction_name?: string; // 交易名称
  card_number?: string; // 卡号
  transaction_location?: string; // 交易地点
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
  debit_amount?: string; // 借方发生额
  credit_amount?: string; // 贷方发生额
  debit_count?: string; // 借方笔数
  credit_count?: string; // 贷方笔数

  // 招商银行字段
  start_date?: string;
  end_date?: string;
  debit_total?: string; // 出账总金额
  credit_total?: string; // 入账总金额
  total_count?: string; // 笔数

  // 济宁银行字段
  currency?: string; // 币种

  // 广发银行字段
  unit?: string; // 单位
  current_balance?: string; // 账户当前余额
  record_count?: string; // 记录数

  // 建设银行字段
  print_date?: string; // 打印日期

  // 中国银行字段
  account_type?: string; // 账户类型 Account Type

  // 交通银行字段
  bank_branch?: string; // 开户机构
  year?: string; // 年份
  month?: string; // 月份
}

export interface FileItem {
  id: number;
  name: string;
  size: string;
  status: "pending" | "uploading" | "done" | "error";
  recognition_duration?: number;
  bank_type?: BankType;
}

// 银行类型显示名称映射
export const BANK_TYPE_NAMES: Record<BankType, string> = {
  shandong_local: "山东地方银行",
  everbright: "光大银行",
  cmb: "招商银行",
  jining: "济宁银行",
  cgb: "广发银行",
  psbc: "邮储银行",
  icbc: "工商银行",
  ccb: "建设银行",
  abc: "农业银行",
  boc: "中国银行",
  bocom: "交通银行",
};
