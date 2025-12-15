import axios from 'axios';

const api = axios.create({
    baseURL: 'http://localhost:8000/api', // FastAPI Backend URL
    headers: {
        'Content-Type': 'multipart/form-data',
    },
});

export const uploadFile = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/files/upload', formData);
    return response.data;
};

export const getFiles = async () => {
    const response = await api.get('/files');
    return response.data;
};

export const getFileTransactions = async (fileId: number) => {
    const response = await api.get(`/transactions/${fileId}`);
    return response.data;
};

export const getFileSummary = async (fileId: number) => {
    const response = await api.get(`/transactions/${fileId}/summary`);
    return response.data;
};

export const deleteFile = async (fileId: number) => {
    const response = await api.delete(`/files/${fileId}`);
    return response.data;
};

export const exportExcel = async (fileId: number, filename: string) => {
    const response = await api.get(`/files/${fileId}/export`, {
        responseType: 'blob'
    });

    // 创建下载链接
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename.replace('.pdf', '.xlsx'));
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
};


