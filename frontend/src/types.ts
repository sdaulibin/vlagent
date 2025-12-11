export interface Transaction {
    id: number;
    date: string;
    type: string;
    amount: string;
    balance: string;
    desc: string;
}

export interface FileItem {
    id: number;
    name: string;
    size: string;
    status: 'uploading' | 'done' | 'error';
}
