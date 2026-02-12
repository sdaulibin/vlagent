import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api",
});

export const uploadFile = async (file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  const response = await api.post("/files/upload", formData);
  return response.data;
};

export const getFiles = async () => {
  const response = await api.get("/files");
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

export const startRecognition = async (fileId: number) => {
  const response = await api.post(`/files/${fileId}/recognize`);
  return response.data;
};

export const exportExcel = async (fileId: number, filename: string) => {
  const response = await api.get(`/files/${fileId}/export`, {
    responseType: "blob",
  });

  // 创建下载链接
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename.replace(".pdf", ".xlsx"));
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

// ===== 合同比对 API =====

export const compareContracts = async (fileA: File, fileB: File) => {
  const formData = new FormData();
  formData.append("file_a", fileA);
  formData.append("file_b", fileB);
  const response = await api.post("/contracts/compare", formData);
  return response.data;
};

export const getCompareTasks = async () => {
  const response = await api.get("/contracts");
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
export const getFilePreviewUrl = (taskId: number, docType: "a" | "b") => {
  const baseUrl =
    import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
  return `${baseUrl}/contracts/${taskId}/file/${docType}`;
};

// ===== 询证函识别 API =====

export const uploadConfirmationLetter = async (file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  const response = await api.post("/confirmation/upload", formData);
  return response.data;
};

export const getConfirmationLetters = async () => {
  const response = await api.get("/confirmation");
  return response.data;
};

export const getConfirmationLetter = async (letterId: number) => {
  const response = await api.get(`/confirmation/${letterId}`);
  return response.data;
};

export const recognizeConfirmationLetter = async (letterId: number) => {
  const response = await api.post(`/confirmation/${letterId}/recognize`);
  return response.data;
};

export const getConfirmationPreviewUrl = (letterId: number) => {
  const baseUrl =
    import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
  return `${baseUrl}/confirmation/${letterId}/file`;
};

export const updateConfirmationLetter = async (
  letterId: number,
  data: Record<string, string>,
) => {
  const response = await api.put(`/confirmation/${letterId}/result`, data);
  return response.data;
};

export const deleteConfirmationLetter = async (letterId: number) => {
  const response = await api.delete(`/confirmation/${letterId}`);
  return response.data;
};
