export interface Transaction {
    id: number;
    sequence?: string;
    transaction_time?: string;
    channel?: string;
    income?: string;
    expense?: string;
    balance?: string;
    currency?: string;
    counterparty_account?: string;
    counterparty_name?: string;
    description?: string;
}

export interface Summary {
    id: number;
    file_id?: number;
    account_name?: string;
    account_number?: string;
    date_range?: string;
    income_count?: string;
    income_total?: string;
    expense_count?: string;
    expense_total?: string;
    has_stamp?: string;
    bank_name?: string;
    stamp_type?: string;
}

export interface FileItem {
    id: number;
    name: string;
    size: string;
    status: 'uploading' | 'done' | 'error';
}
