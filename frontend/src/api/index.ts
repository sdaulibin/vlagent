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

// ===== 合同比对 API =====

export const compareContracts = async (fileA: File, fileB: File) => {
    const formData = new FormData();
    formData.append('file_a', fileA);
    formData.append('file_b', fileB);
    const response = await api.post('/contracts/compare', formData);
    return response.data;
};

export const getCompareTasks = async () => {
    const response = await api.get('/contracts');
    return response.data;
};

export const getCompareTask = async (taskId: number) => {
    const response = await api.get(`/contracts/${taskId}`);
    return response.data;
};

export const getTaskDiffs = async (taskId: number) => {
    const response = await api.get(`/contracts/${taskId}/diffs`);
    return response.data;
};

export const deleteCompareTask = async (taskId: number) => {
    const response = await api.delete(`/contracts/${taskId}`);
    return response.data;
};

// 获取文件预览 URL
export const getFilePreviewUrl = (taskId: number, docType: 'a' | 'b') => {
    return `http://localhost:8000/api/contracts/${taskId}/file/${docType}`;
};
