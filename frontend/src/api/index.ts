import axios from "axios";
import { getToken, clearAuth } from "../composables/useAuth";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api",
});

// 请求拦截器：自动添加 Authorization header
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：401 时清除认证状态并跳转错误页面（防止死循环）
let _redirecting = false;
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !_redirecting) {
      _redirecting = true;
      clearAuth();
      sessionStorage.removeItem("vlagent_token");
      sessionStorage.removeItem("vlagent_entry_url");
      window.location.replace("/auth-error");
    }
    return Promise.reject(error);
  }
);

/** 通过 POST 获取文件并返回 blob URL（用于 img/iframe src） */
async function fetchFileAsBlobUrl(path: string): Promise<string> {
  const response = await api.post(path, {}, { responseType: "blob" });
  return URL.createObjectURL(response.data);
}

export const uploadFile = async (file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  const response = await api.post("/files/upload", formData);
  return response.data;
};

export const getFiles = async () => {
  const response = await api.post("/files");
  return response.data;
};

export const getFileTransactions = async (fileId: number) => {
  const response = await api.post(`/transactions/${fileId}`);
  return response.data;
};

export const getFileSummary = async (fileId: number) => {
  const response = await api.post(`/transactions/${fileId}/summary`);
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
  const response = await api.post(`/files/${fileId}/export`, {}, {
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

// ===== 权限 API =====

export const getUserPermissions = async () => {
  const response = await api.get("/permissions/me");
  return response.data as string[];
};

// ===== 模块 API =====

export interface ModuleInfo {
  key: string;
  title: string;
  description: string;
  icon: string;
  route: string;
  gradient: string;
  hover_class: string;
  sort_order: number;
  status: boolean;
}

export const getModules = async () => {
  const response = await api.get("/modules");
  return response.data as ModuleInfo[];
};

// ===== 文档比对 API =====

export const compareDocuments = async (fileA: File, fileB: File) => {
  const formData = new FormData();
  formData.append("file_a", fileA);
  formData.append("file_b", fileB);
  const response = await api.post("/documents/compare", formData);
  return response.data;
};

export const getDocumentTasks = async () => {
  const response = await api.post("/documents/list");
  return response.data;
};

export const getDocumentTask = async (taskId: number) => {
  const response = await api.post(`/documents/list/${taskId}`);
  return response.data;
};

export const getDocumentTaskStatus = async (taskId: number) => {
  const response = await api.post(`/documents/${taskId}/status`);
  return response.data;
};

export const deleteDocumentTask = async (taskId: number) => {
  const response = await api.delete(`/documents/${taskId}`);
  return response.data;
};

// ===== 询证函识别 API =====

export const uploadConfirmationLetter = async (file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  const response = await api.post("/confirmation/upload", formData);
  return response.data;
};

export const getConfirmationLetters = async () => {
  const response = await api.post("/confirmation");
  return response.data;
};

export const getConfirmationLetter = async (letterId: number) => {
  const response = await api.post(`/confirmation/${letterId}`);
  return response.data;
};

export const recognizeConfirmationLetter = async (letterId: number) => {
  const response = await api.post(`/confirmation/${letterId}/recognize`);
  return response.data;
};

export const getConfirmationPreviewUrl = (letterId: number) =>
  fetchFileAsBlobUrl(`/confirmation/${letterId}/file`);

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

// ===== 询证函格式比对 API =====

export const uploadFormatCompare = async (file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  const response = await api.post("/format-compare/upload", formData);
  return response.data;
};

export const getFormatCompareTasks = async () => {
  const response = await api.post("/format-compare");
  return response.data;
};

export const getFormatCompareTask = async (taskId: number) => {
  const response = await api.post(`/format-compare/${taskId}`);
  return response.data;
};

export const deleteFormatCompareTask = async (taskId: number) => {
  const response = await api.delete(`/format-compare/${taskId}`);
  return response.data;
};

export const getFormatCompareFileUrl = (taskId: number) =>
  fetchFileAsBlobUrl(`/format-compare/${taskId}/file`);

export const getFormatCompareTemplateUrl = (formatKey: string) =>
  fetchFileAsBlobUrl(`/format-compare/templates/${formatKey}/preview`);

export const getFormatCompareTemplates = async () => {
  const response = await api.post("/format-compare/templates");
  return response.data;
};

export const runFormatCompare = async (taskId: number) => {
  const response = await api.post(`/format-compare/${taskId}/compare`);
  return response.data;
};

// ===== 发票识别 API =====

export const uploadInvoice = async (file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  const response = await api.post("/invoice_recognition/upload", formData);
  return response.data;
};

export const getInvoiceFiles = async () => {
  const response = await api.post("/invoice_recognition/list");
  return response.data;
};

export const getInvoiceResult = async (fileId: number) => {
  const response = await api.post(`/invoice_recognition/list/${fileId}`);
  return response.data;
};

export const deleteInvoiceFile = async (fileId: number) => {
  const response = await api.delete(`/invoice_recognition/${fileId}`);
  return response.data;
};

export const getInvoiceFileUrl = (fileId: number) =>
  fetchFileAsBlobUrl(`/invoice_recognition/${fileId}/file`);

// ===== 类凭证识别 API =====

export const extractCredential = async (file: File, credentialType: string) => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("credential_type", credentialType);
  const response = await api.post("/credentials/extract", formData);
  return response.data;
};

export const getCredentialRecords = async () => {
  const response = await api.post("/credentials/list");
  return response.data;
};

export const getCredentialRecord = async (recordId: number) => {
  const response = await api.post(`/credentials/list/${recordId}`);
  return response.data;
};

export const deleteCredentialRecord = async (recordId: number) => {
  const response = await api.delete(`/credentials/${recordId}`);
  return response.data;
};

export const getCredentialFileUrl = (recordId: number) =>
  fetchFileAsBlobUrl(`/credentials/${recordId}/file`);

// ===== 通用 PDF 提取 API =====

export const uploadPdfExtract = async (file: File, fields: string, outputFormat: string) => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("fields", fields);
  formData.append("output_format", outputFormat);
  const response = await api.post("/pdf_extract/upload", formData);
  return response.data;
};

export const getPdfExtractTasks = async () => {
  const response = await api.post("/pdf_extract/list");
  return response.data;
};

export const getPdfExtractTask = async (taskId: number) => {
  const response = await api.post(`/pdf_extract/list/${taskId}`);
  return response.data;
};

export const deletePdfExtractTask = async (taskId: number) => {
  const response = await api.delete(`/pdf_extract/${taskId}`);
  return response.data;
};

export const downloadPdfExtract = (taskId: number) =>
  fetchFileAsBlobUrl(`/pdf_extract/download/${taskId}`);
