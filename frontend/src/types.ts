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

export interface FileItem {
    id: number;
    name: string;
    size: string;
    status: 'uploading' | 'done' | 'error';
}
