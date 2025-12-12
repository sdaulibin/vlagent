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
