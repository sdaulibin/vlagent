<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { ArrowLeft, Upload, Loader2, FileCheck2, Trash2, Eye } from 'lucide-vue-next';
import {
  extractCredential,
  getCredentialRecords,
  getCredentialRecord,
  deleteCredentialRecord,
  getCredentialFileUrl,
} from '../api';
import PowerOfAttorneyResult from '../components/PowerOfAttorneyResult.vue';
import SettlementCompareResult from '../components/SettlementCompareResult.vue';
import type { CredentialRecordItem } from '../types';

const router = useRouter();

const CREDENTIAL_TYPES = [
  { value: 'id_card', label: '身份证' },
  { value: 'electronic_seal', label: '电子印章' },
  { value: 'bank_card', label: '银行卡' },
  { value: 'electronic_credential', label: '电子凭证' },
  { value: 'online_banking_app', label: '网银申请书' },
  { value: 'notice_illegal_activity', label: '违法犯罪告知书' },
  { value: 'account_opening_app', label: '开户申请书' },
  { value: 'power_of_attorney', label: '授权委托书' },
  { value: 'settlement_application', label: '结算业务申请书' }
];

const CREDENTIAL_TYPE_LABELS: Record<string, string> = {
  id_card: '身份证',
  electronic_seal: '电子印章',
  bank_card: '银行卡',
  electronic_credential: '电子凭证',
  online_banking_app: '网银申请书',
  notice_illegal_activity: '违法犯罪告知书',
  account_opening_app: '开户申请书',
  power_of_attorney: '授权委托书',
  settlement_application: '结算业务申请书'
};

const selectedType = ref('id_card');
const isUploading = ref(false);
const resultData = ref<any>(null);
const errorMsg = ref('');
const selectedRecordId = ref<number | null>(null);
const previewUrl = ref('');

const records = ref<CredentialRecordItem[]>([]);
const pollTimer = ref<ReturnType<typeof setInterval> | null>(null);

const hasProcessingRecords = computed(() =>
  records.value.some(r => r.status === 'pending' || r.status === 'processing')
);

const FIELD_LABELS: Record<string, string> = {
  is_front_side: '是否为正面(人像面)',
  has_face_photo: '是否包含人脸照片',
  is_bank_card_image: '是否为银行卡影像',
  has_cut_corner: '是否剪角',
  has_handwritten_signature: '是否有手写签字',
  has_fingerprint: '是否有手印',
  is_online_banking_app: '是否为网银/手机表单',
  is_illegal_activity_notice: '是否为违法告知书',
  name: '姓名',
  gender: '性别',
  ethnicity: '民族',
  birth_date: '出生日期',
  address: '住址',
  document_type: '证件类型',
  id_number: '证件号码',
  issuing_authority: '签发机关',
  issue_date: '签发日期',
  expiry_date: '有效期限',
  header: '文件类型',
  seal_codes: '电子印章编码',
  seal_details: '电子印章编码（含联次）',
  card_number: '银行卡号',
  payer_name: '付款人',
  payer_account: '付款人账号',
  customer_number: '客户号',
  payee_name: '收款人',
  payee_account: '收款人账号',
  amount: '交易金额',
  transaction_date: '交易时间',
  serial_number: '流水号/回单号',
  purpose: '用途/附言',
  signature_content: '手写签字内容',
  enterprise_name: '企业名称',
  business_license: '营业执照号',
  other_id_number: '其他证件号码',
  legal_rep_name: '法定代表人姓名',
  legal_rep_id: '法人身份证号',
  legal_rep_phone: '法人手机号',
  handler_name: '经办人姓名',
  handler_id: '经办人身份证号',
  handler_phone: '经办人手机号',
  account_number: '账号',
  permissions: '业务权限',
  single_limit: '单笔限额',
  daily_limit: '日累计限额',
  daily_transfer_count: '日累计笔数',
  deduction_account: '扣费账号',
  channel: '渠道',
  entry_permission: '录入权限',
  audit_permission: '审核权限',
  manage_permission: '管理权限',
  other_permission: '其他权限',
  audit_method: '审核方式',
  legal_rep_signature: '法人/授权人签字',
  legal_rep_sign_date: '法人签字日期',
  bank_handler_signature: '银行经办人',
  bank_auditor_signature: '银行审核人',
  bank_sign_date: '银行业务日期',
  bank_account: '银行账号',
  applicant_signature: '开户申请人签名',
  sign_date: '日期',
  is_account_opening_app: '是否为开户申请书',
  depositor_name_cn: '存款人名称(中)',
  depositor_type: '存款人类别',
  tax_registration_cert: '税务登记证',
  org_code_cert: '组织机构代码证',
  proof_file_type: '证明文件种类',
  proof_file_number: '证明文件编号',
  registered_address: '注册地址',
  business_scope: '经营范围',
  legal_rep_id_type: '法人证件种类',
  legal_rep_id_number: '法人证件号码',
  financial_manager_1_name: '财务负责人1',
  financial_manager_1_phone: '财务负责人1电话',
  financial_manager_2_name: '财务负责人2',
  financial_manager_2_phone: '财务负责人2电话',
  bus_handler_name: '业务经办人',
  bus_handler_phone: '业务经办人电话',
  account_nature: '账户性质',
  fixed_term_account: '定期类账户',
  general_account_reason: '申请一般户原因',
  special_account_fund_nature: '专用户资金性质',
  currency: '账户币种',
  other_account_services: '其他账户服务',
  use_account_password: '使用账户密码',
  tax_resident_declaration: '税收居民声明',
  open_online_banking: '开通网上银行',
  open_mobile_banking: '开通手机银行',
  open_sms_notice: '开通短信通知',
  open_phone_reconciliation: '开通电话对账',
  open_official_web_reconciliation: '开通官网对账',
  online_banking_services_detail: '服务框全部内容',
  sms_notice_details: '短信服务细节',
  bank_name: '开户银行名称',
  bank_code: '开户银行代码',
  account_name: '账户名称',
  basic_account_license_no: '核准号',
  open_date: '开户日期',
  depositor_seal: '存款人公章',
  legal_rep_seal: '法人名章',
  handler_signature: '经办人签名',
  bottom_line_content: '底部文字内容',
  is_power_of_attorney: '是否为授权委托书',
  principal_name: '本人(委托人)',
  principal_id_number: '委托人证件号',
  authorized_items: '授权事项',
  is_employee: '本单位职工',
  authorized_person_id_number: '被授权人证件号',
  authorized_date: '代表本人日期',
  seal_date: '公章日期',
  authorized_person_signature: '被授权人签字'
};

const goBack = () => {
  router.push('/');
};

const openPreview = () => {
  if (previewUrl.value) window.open(previewUrl.value + '#toolbar=0', '_blank');
};

const getStatusText = (status: string) => {
  switch (status) {
    case 'pending': return '待提取';
    case 'processing': return '提取中';
    case 'done': return '已完成';
    case 'failed': return '失败';
    default: return status;
  }
};

const getStatusClass = (status: string) => {
  switch (status) {
    case 'pending': return 'status-badge status-badge--pending';
    case 'processing': return 'status-badge status-badge--processing';
    case 'done': return 'status-badge status-badge--done';
    case 'failed': return 'status-badge status-badge--failed';
    default: return 'status-badge';
  }
};

const loadRecords = async () => {
  try {
    records.value = await getCredentialRecords();
  } catch (e) {
    console.error("加载提取记录失败", e);
  }
};

const selectRecord = async (id: number) => {
  selectedRecordId.value = id;
  try {
    const detail = await getCredentialRecord(id);
    resultData.value = detail.result;
    errorMsg.value = detail.error_msg || '';
    selectedType.value = detail.credential_type;
    previewUrl.value = await getCredentialFileUrl(id);
  } catch (e) {
    console.error("加载记录详情失败", e);
  }
};

const handleDeleteRecord = async (id: number) => {
  if (!confirm('确定要删除这条提取记录吗？')) return;
  try {
    await deleteCredentialRecord(id);
    if (selectedRecordId.value === id) {
      selectedRecordId.value = null;
      resultData.value = null;
      errorMsg.value = '';
      previewUrl.value = '';
    }
    await loadRecords();
  } catch (e) {
    console.error("删除失败", e);
  }
};

const handleFileUpload = async (event: Event) => {
  const target = event.target as HTMLInputElement;
  const fileList = target.files;
  if (!fileList || fileList.length === 0) return;

  const file = fileList[0];
  if (!file) return;

  isUploading.value = true;
  resultData.value = null;
  errorMsg.value = '';
  previewUrl.value = '';

  try {
    const data = await extractCredential(file, selectedType.value);
    selectedRecordId.value = data.id;
    await loadRecords();
    // 上传后后台异步处理，启动轮询等待完成
    startPolling();
  } catch (e: any) {
    console.error("提取失败", e);
    errorMsg.value = e.response?.data?.detail || e.message || "由于网络或服务异常，提取失败";
  } finally {
    isUploading.value = false;
    target.value = '';
  }
};

const isImageFile = (filename: string) => {
  const ext = filename.split('.').pop()?.toLowerCase();
  return ext === 'jpg' || ext === 'jpeg' || ext === 'png';
};

const startPolling = () => {
  if (pollTimer.value) return;
  pollTimer.value = setInterval(async () => {
    await loadRecords();
    // 如果当前选中的记录已完成，刷新详情
    if (selectedRecordId.value) {
      const current = records.value.find(r => r.id === selectedRecordId.value);
      if (current && (current.status === 'done' || current.status === 'failed')) {
        await selectRecord(selectedRecordId.value);
      }
    }
    // 没有正在处理的记录时停止轮询
    if (!hasProcessingRecords.value) {
      stopPolling();
    }
  }, 3000);
};

const stopPolling = () => {
  if (pollTimer.value) {
    clearInterval(pollTimer.value);
    pollTimer.value = null;
  }
};

onMounted(async () => {
  await loadRecords();
  if (hasProcessingRecords.value) {
    startPolling();
  }
});

onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <div class="page-container">
    <!-- Header -->
    <header class="page-header">
      <button @click="goBack" class="page-back-btn">
        <ArrowLeft class="w-5 h-5" />
        返回首页
      </button>
      <div class="page-title-group">
        <div class="page-icon bg-gradient-to-br from-indigo-500 to-purple-600">
          <FileCheck2 class="text-white w-7 h-7" />
        </div>
        <div>
          <h1 class="page-title">类凭证识别</h1>
          <p class="page-subtitle">上传指定格式凭证类文件，自动提取关键要素及签字信息</p>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="page-main">

      <!-- Left: Upload & Config & History -->
      <div class="page-left-col">
        <div class="content-card p-4">
          <h3 class="font-medium text-slate-700 mb-4">1. 选择凭证类型</h3>
          <select
            v-model="selectedType"
            class="w-full border-slate-300 rounded-md shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50 p-2 border"
          >
            <option v-for="t in CREDENTIAL_TYPES" :key="t.value" :value="t.value">
              {{ t.label }}
            </option>
          </select>
        </div>

        <div class="content-card p-4">
          <h3 class="font-medium text-slate-700 mb-4">2. 上传文件</h3>
          <label class="upload-zone--large hover:border-indigo-400">
            <template v-if="isUploading">
              <Loader2 class="w-8 h-8 text-indigo-400 animate-spin" />
              <span class="text-slate-600 mt-2">智能解析中，请稍候...</span>
            </template>
            <template v-else>
              <Upload class="w-8 h-8 text-slate-400" />
              <span class="text-slate-600 mt-2 text-center text-sm">点击上传<br/>(PDF / JPG / PNG)</span>
            </template>
            <input type="file" accept=".pdf,.jpg,.jpeg,.png" class="hidden" @change="handleFileUpload" :disabled="isUploading" />
          </label>
        </div>

        <!-- 提取记录列表 -->
        <div class="file-list">
          <div class="file-list-header">
            <h3 class="content-card-title">提取记录 ({{ records.length }})</h3>
          </div>
          <ul class="file-list-items">
            <li
              v-for="record in records"
              :key="record.id"
              @click="selectRecord(record.id)"
              :class="[
                'file-list-item',
                selectedRecordId === record.id ? 'bg-indigo-50' : ''
              ]"
            >
              <div class="file-list-item-info">
                <p class="file-list-item-name">{{ record.filename }}</p>
                <div class="file-list-item-meta">
                  <span :class="getStatusClass(record.status)">
                    {{ getStatusText(record.status) }}
                  </span>
                  <span class="text-xs text-slate-400">{{ CREDENTIAL_TYPE_LABELS[record.credential_type] || record.credential_type }}</span>
                  <span v-if="record.processing_duration" class="text-xs text-slate-400">{{ record.processing_duration.toFixed(1) }}s</span>
                </div>
              </div>
              <div class="file-list-item-actions">
                <button @click.stop="handleDeleteRecord(record.id)" class="file-list-delete-btn">
                  <Trash2 class="w-4 h-4" />
                </button>
              </div>
            </li>
            <li v-if="records.length === 0" class="file-list-empty">
              暂无提取记录
            </li>
          </ul>
        </div>
      </div>

      <!-- Right: File Preview + Results -->
      <div class="page-right-col">
        <div class="content-card-header">
          <h3 class="content-card-title">提取结果</h3>
          <div v-if="selectedRecordId" class="flex items-center gap-2">
            <button
              @click="openPreview()"
              class="btn-toolbar"
            >
              <Eye class="w-3.5 h-3.5" />
              新窗口预览
            </button>
          </div>
        </div>

        <!-- Loading State -->
        <div v-if="isUploading" class="loading-state">
          <Loader2 class="w-8 h-8 animate-spin text-indigo-400" />
          <p>智能解析中，请稍候...</p>
        </div>

        <template v-else-if="selectedRecordId">
          <!-- File Preview -->
          <div v-if="previewUrl" class="border-b border-slate-100 bg-slate-50">
            <div class="p-3">
              <p class="text-xs font-medium text-slate-500 mb-2">原文预览</p>
              <div class="file-preview-container">
                <img
                  v-if="isImageFile(previewUrl)"
                  :src="previewUrl"
                  class="file-preview-img"
                />
                <iframe
                  v-else
                  :src="previewUrl + '#toolbar=0'"
                  class="file-preview-iframe"
                />
              </div>
            </div>
          </div>

          <!-- Error State -->
          <div v-if="errorMsg" class="error-state">
            <p class="text-lg font-medium">识别失败</p>
            <p class="text-sm bg-red-50 p-3 rounded-lg border border-red-100">{{ errorMsg }}</p>
          </div>

          <!-- Results Display -->
          <div v-if="resultData" class="flex-1 p-6 overflow-auto">
            <!-- 授权委托书特殊展示 -->
            <template v-if="selectedType === 'power_of_attorney'">
              <PowerOfAttorneyResult :data="resultData" />
            </template>

            <!-- 结算业务申请书：左右两联字段比对展示 -->
            <template v-else-if="selectedType === 'settlement_application'">
              <SettlementCompareResult :data="resultData" />
            </template>

            <!-- 其他凭证类型：通用展示 -->
            <template v-else>
              <div class="result-grid">
                <!-- 电子印章：按颜色区分联次的彩色胶囊（seal_details 为对象数组，需专属渲染） -->
                <div v-if="resultData.seal_details && Array.isArray(resultData.seal_details) && resultData.seal_details.length > 0" class="result-field md:col-span-2">
                  <p class="result-field-label font-mono">电子印章编码（含联次）</p>
                  <p class="result-field-value break-words">
                    <span
                      v-for="(item, i) in resultData.seal_details"
                      :key="i"
                      class="inline-flex flex-col align-top px-2.5 py-1 rounded text-xs font-mono mr-2 mb-2 border"
                      :class="item.color === 'black' ? 'bg-slate-800 text-white border-slate-900'
                            : item.color === 'blue' ? 'bg-blue-600 text-white border-blue-700'
                            : 'bg-indigo-50 text-slate-700 border-indigo-100'"
                    >
                      <span class="inline-flex items-center gap-1.5">
                        <span class="font-sans opacity-80">{{ item.copy || (item.color === 'black' ? '第一联' : item.color === 'blue' ? '第二联' : '') }}</span>
                        <span class="font-semibold">{{ item.code }}</span>
                      </span>
                      <span v-if="item.vehicle_no || item.route || item.form_no" class="font-sans opacity-70 text-[10px] mt-0.5">
                        <template v-if="item.vehicle_no">车号 {{ item.vehicle_no }}</template>
                        <template v-if="item.route">{{ item.vehicle_no ? ' · ' : '' }}线路 {{ item.route }}</template>
                        <template v-if="item.form_no">{{ (item.vehicle_no || item.route) ? ' · ' : '' }}No.{{ item.form_no }}</template>
                      </span>
                    </span>
                  </p>
                </div>
                <template v-for="(val, key) in resultData" :key="key">
                  <div v-if="String(key) !== 'operators' && String(key) !== 'linked_accounts' && String(key) !== 'authorized_items_by_category' && String(key) !== 'seal_details' && !(selectedType === 'electronic_seal' && String(key) === 'seal_codes' && resultData.seal_details) && val !== null" class="result-field">
                    <p class="result-field-label font-mono">{{ FIELD_LABELS[key] || key }}</p>
                    <p class="result-field-value break-words">
                      <template v-if="Array.isArray(val)">
                        <div v-for="(item, i) in val" :key="i" class="bg-indigo-50 px-2 py-1 rounded text-xs inline-block mr-2 mb-1 border border-indigo-100">
                          {{ item }}
                        </div>
                        <span v-if="val.length === 0" class="text-slate-400">无</span>
                      </template>
                      <template v-else-if="typeof val === 'boolean'">
                        <span :class="val ? 'text-green-600 bg-green-100 px-2 py-0.5 rounded text-xs' : 'text-slate-500 bg-slate-200 px-2 py-0.5 rounded text-xs'">
                          {{ val ? '是 (True)' : '否 (False)' }}
                        </span>
                      </template>
                      <template v-else>
                        {{ val === '' || val === null ? '无' : val }}
                      </template>
                    </p>
                  </div>
                </template>
              </div>

              <!-- Linked Accounts Table for Online Banking App -->
              <div v-if="resultData.linked_accounts && resultData.linked_accounts.length > 0" class="mt-6">
                <h4 class="font-medium text-slate-700 mb-3 border-b pb-2">企业需关联的账户</h4>
                <div class="overflow-x-auto">
                  <table class="w-full text-sm border-collapse">
                    <thead>
                      <tr class="bg-slate-100">
                        <th class="border border-slate-300 px-3 py-2 text-left font-medium text-slate-600" rowspan="2">账号</th>
                        <th class="border border-slate-300 px-3 py-2 text-center font-medium text-slate-600" colspan="2">企业网银</th>
                        <th class="border border-slate-300 px-3 py-2 text-center font-medium text-slate-600" colspan="2">手机银行</th>
                        <th class="border border-slate-300 px-3 py-2 text-center font-medium text-slate-600" rowspan="2">单笔限额</th>
                        <th class="border border-slate-300 px-3 py-2 text-center font-medium text-slate-600" rowspan="2">日累计限额</th>
                        <th class="border border-slate-300 px-3 py-2 text-center font-medium text-slate-600" rowspan="2">日转账笔数</th>
                      </tr>
                      <tr class="bg-slate-100">
                        <th class="border border-slate-300 px-3 py-2 text-center font-medium text-slate-500">查询</th>
                        <th class="border border-slate-300 px-3 py-2 text-center font-medium text-slate-500">转账</th>
                        <th class="border border-slate-300 px-3 py-2 text-center font-medium text-slate-500">查询</th>
                        <th class="border border-slate-300 px-3 py-2 text-center font-medium text-slate-500">转账</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(acc, idx) in resultData.linked_accounts" :key="idx" class="hover:bg-slate-50">
                        <td class="border border-slate-300 px-3 py-2 font-mono">{{ acc.account_number || '-' }}</td>
                        <td class="border border-slate-300 px-3 py-2 text-center">
                          <span :class="acc.ebank_query ? 'text-green-600 font-bold' : 'text-slate-300'">{{ acc.ebank_query ? '✓' : '×' }}</span>
                        </td>
                        <td class="border border-slate-300 px-3 py-2 text-center">
                          <span :class="acc.ebank_transfer ? 'text-green-600 font-bold' : 'text-slate-300'">{{ acc.ebank_transfer ? '✓' : '×' }}</span>
                        </td>
                        <td class="border border-slate-300 px-3 py-2 text-center">
                          <span :class="acc.mbank_query ? 'text-green-600 font-bold' : 'text-slate-300'">{{ acc.mbank_query ? '✓' : '×' }}</span>
                        </td>
                        <td class="border border-slate-300 px-3 py-2 text-center">
                          <span :class="acc.mbank_transfer ? 'text-green-600 font-bold' : 'text-slate-300'">{{ acc.mbank_transfer ? '✓' : '×' }}</span>
                        </td>
                        <td class="border border-slate-300 px-3 py-2 text-center">{{ acc.single_limit || '-' }}</td>
                        <td class="border border-slate-300 px-3 py-2 text-center">{{ acc.daily_limit || '-' }}</td>
                        <td class="border border-slate-300 px-3 py-2 text-center">{{ acc.daily_transfer_count || '-' }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <!-- Operators Table for Online Banking App -->
              <div v-if="resultData.operators && resultData.operators.length > 0" class="mt-6">
                <h4 class="font-medium text-slate-700 mb-3 border-b pb-2">操作户信息</h4>
                <div class="overflow-x-auto">
                  <table class="w-full text-sm border-collapse">
                    <thead>
                      <tr class="bg-slate-100">
                        <th class="border border-slate-300 px-3 py-2 text-left font-medium text-slate-600">姓名</th>
                        <th class="border border-slate-300 px-3 py-2 text-left font-medium text-slate-600">身份证号码</th>
                        <th class="border border-slate-300 px-3 py-2 text-left font-medium text-slate-600">手机号码</th>
                        <th class="border border-slate-300 px-3 py-2 text-center font-medium text-slate-600">网银</th>
                        <th class="border border-slate-300 px-3 py-2 text-center font-medium text-slate-600">手机银行</th>
                        <th class="border border-slate-300 px-3 py-2 text-center font-medium text-slate-600">录入</th>
                        <th class="border border-slate-300 px-3 py-2 text-center font-medium text-slate-600">审核</th>
                        <th class="border border-slate-300 px-3 py-2 text-center font-medium text-slate-600">管理</th>
                        <th class="border border-slate-300 px-3 py-2 text-center font-medium text-slate-600">其他</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(op, idx) in resultData.operators" :key="idx" class="hover:bg-slate-50">
                        <td class="border border-slate-300 px-3 py-2 font-medium">{{ op.name || '-' }}</td>
                        <td class="border border-slate-300 px-3 py-2 font-mono text-xs">{{ op.id_number || '-' }}</td>
                        <td class="border border-slate-300 px-3 py-2">{{ op.phone || '-' }}</td>
                        <td class="border border-slate-300 px-3 py-2 text-center">
                          <span :class="op.ebank_channel ? 'text-green-600 font-bold' : 'text-slate-300'">{{ op.ebank_channel ? '✓' : '×' }}</span>
                        </td>
                        <td class="border border-slate-300 px-3 py-2 text-center">
                          <span :class="op.mbank_channel ? 'text-green-600 font-bold' : 'text-slate-300'">{{ op.mbank_channel ? '✓' : '×' }}</span>
                        </td>
                        <td class="border border-slate-300 px-3 py-2 text-center">
                          <span :class="op.entry_permission ? 'text-green-600' : 'text-slate-300'">{{ op.entry_permission ? '✓' : '×' }}</span>
                        </td>
                        <td class="border border-slate-300 px-3 py-2 text-center">
                          <span :class="op.audit_permission ? 'text-green-600' : 'text-slate-300'">{{ op.audit_permission ? '✓' : '×' }}</span>
                        </td>
                        <td class="border border-slate-300 px-3 py-2 text-center">
                          <span :class="op.manage_permission ? 'text-green-600' : 'text-slate-300'">{{ op.manage_permission ? '✓' : '×' }}</span>
                        </td>
                        <td class="border border-slate-300 px-3 py-2 text-center">
                          <span :class="op.other_permission ? 'text-green-600' : 'text-slate-300'">{{ op.other_permission ? '✓' : '×' }}</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </template>
          </div>
        </template>

        <!-- Initial state -->
        <div v-else class="empty-state p-6 text-center">
          请在左侧选择类型并上传文件<br/>等待 AI 进行提取识别
        </div>
      </div>
    </main>
  </div>
</template>
