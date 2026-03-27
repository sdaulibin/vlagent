<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { ArrowLeft, Upload, Loader2, FileCheck2 } from 'lucide-vue-next';
import { extractCredential } from '../api';
import PowerOfAttorneyResult from '../components/PowerOfAttorneyResult.vue';

const router = useRouter();

const CREDENTIAL_TYPES = [
  { value: 'id_card', label: '身份证' },
  { value: 'electronic_seal', label: '电子印章' },
  { value: 'bank_card', label: '银行卡' },
  { value: 'electronic_credential', label: '电子凭证' },
  { value: 'online_banking_app', label: '网银申请书' },
  { value: 'notice_illegal_activity', label: '违法犯罪告知书' },
  { value: 'account_opening_app', label: '开户申请书' },
  { value: 'power_of_attorney', label: '授权委托书' }
];

const selectedType = ref('id_card');
const isUploading = ref(false);
const resultData = ref<any>(null);
const errorMsg = ref('');

const FIELD_LABELS: Record<string, string> = {
  // Common / Boolean
  is_front_side: '是否为正面(人像面)',
  has_face_photo: '是否包含人脸照片',
  is_bank_card_image: '是否为银行卡影像',
  has_cut_corner: '是否剪角',
  has_handwritten_signature: '是否有手写签字',
  has_fingerprint: '是否有手印',
  is_online_banking_app: '是否为网银/手机表单',
  is_illegal_activity_notice: '是否为违法告知书',

  // ID Card
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

  // Electronic Seal
  header: '文件类型',
  seal_codes: '电子印章编码',

  // Bank Card
  card_number: '银行卡号',

  // Electronic Credential
  payer_name: '付款人',
  payer_account: '付款人账号',
  payee_name: '收款人',
  payee_account: '收款人账号',
  amount: '交易金额',
  transaction_date: '交易时间',
  serial_number: '流水号/回单号',
  purpose: '用途/附言',
  signature_content: '手写签字内容',

  // Online Banking App
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

  // Illegal Activity Notice
  bank_account: '银行账号',
  applicant_signature: '开户申请人签名',
  sign_date: '日期',

  // Account Opening App
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

  // Power of Attorney
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

const handleFileUpload = async (event: Event) => {
  const target = event.target as HTMLInputElement;
  const fileList = target.files;
  if (!fileList || fileList.length === 0) return;

  const file = fileList[0];
  if (!file) return;

  isUploading.value = true;
  resultData.value = null;
  errorMsg.value = '';

  try {
    const data = await extractCredential(file, selectedType.value);
    resultData.value = data.extracted_data;
  } catch (e: any) {
    console.error("提取失败", e);
    errorMsg.value = e.response?.data?.detail || e.message || "由于网络或服务异常，提取失败";
  } finally {
    isUploading.value = false;
    target.value = '';
  }
};
</script>

<template>
  <div class="min-h-screen p-4 md:p-8 flex flex-col">
    <!-- Header -->
    <header class="w-full max-w-7xl mx-auto mb-6">
      <button @click="goBack" class="flex items-center gap-2 text-slate-500 hover:text-slate-700 mb-4">
        <ArrowLeft class="w-5 h-5" />
        返回首页
      </button>
      <div class="flex items-center gap-3">
        <div class="bg-gradient-to-br from-indigo-500 to-purple-600 p-3 rounded-xl shadow-lg">
          <FileCheck2 class="text-white w-7 h-7" />
        </div>
        <div>
          <h1 class="text-2xl font-bold text-slate-900">类凭证识别</h1>
          <p class="text-sm text-slate-500">上传指定格式凭证类文件，自动提取关键要素及签字信息</p>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="w-full max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-12 gap-6 flex-1">

      <!-- Left: Upload & Config -->
      <div class="md:col-span-4 flex flex-col gap-4">
        <div class="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
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

        <div class="bg-white rounded-xl shadow-sm border border-slate-200 p-4 flex-1">
          <h3 class="font-medium text-slate-700 mb-4">2. 上传文件</h3>
          <!-- Upload -->
          <label class="flex flex-col items-center justify-center gap-2 border-2 border-dashed border-slate-300 hover:border-indigo-400 rounded-xl p-8 cursor-pointer transition-colors bg-slate-50">
            <template v-if="isUploading">
              <Loader2 class="w-8 h-8 text-indigo-400 animate-spin" />
              <span class="text-slate-600 mt-2">智能解析中，请稍候...</span>
            </template>
            <template v-else>
              <Upload class="w-8 h-8 text-slate-400" />
              <span class="text-slate-600 mt-2 text-center text-sm">点击或拖拽上传<br/>(PDF / JPG / PNG)</span>
            </template>
            <input type="file" accept=".pdf,.jpg,.jpeg,.png" class="hidden" @change="handleFileUpload" :disabled="isUploading" />
          </label>
        </div>
      </div>

      <!-- Right: Recognition Results -->
      <div class="md:col-span-8 bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col">
        <div class="p-4 border-b border-slate-100 flex items-center justify-between">
          <h3 class="font-medium text-slate-700">提取结果</h3>
        </div>

        <!-- Initial state -->
        <div v-if="!resultData && !errorMsg && !isUploading" class="flex-1 flex items-center justify-center text-slate-400 p-6 text-center">
          请在左侧选择类型并上传文件<br/>等待 AI 进行提取识别
        </div>

        <!-- Error State -->
        <div v-if="errorMsg" class="flex-1 flex flex-col items-center justify-center gap-3 text-red-500 p-6 text-center">
          <p class="text-lg font-medium">识别失败</p>
          <p class="text-sm bg-red-50 p-3 rounded-lg border border-red-100">{{ errorMsg }}</p>
        </div>

        <!-- Results Display -->
        <div v-if="resultData" class="flex-1 p-6 overflow-auto">
          <!-- 授权委托书特殊展示 -->
          <template v-if="selectedType === 'power_of_attorney'">
            <PowerOfAttorneyResult :data="resultData" />
          </template>

          <!-- 其他凭证类型：通用展示 -->
          <template v-else>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <template v-for="(val, key) in resultData" :key="key">
                <div v-if="String(key) !== 'operators' && String(key) !== 'authorized_items_by_category' && val !== null" class="bg-slate-50 p-3 rounded-lg border border-slate-100">
                  <p class="text-xs text-slate-400 font-mono mb-1">{{ FIELD_LABELS[key] || key }}</p>
                  <p class="text-sm font-medium text-slate-800 break-words">
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

            <!-- Operators Array Display for Online Banking App -->
            <div v-if="resultData.operators && resultData.operators.length > 0" class="mt-6">
              <h4 class="font-medium text-slate-700 mb-3 border-b pb-2">操作人员列表</h4>
              <div class="space-y-3">
                <div v-for="(op, idx) in resultData.operators" :key="idx" class="bg-blue-50 p-3 rounded-lg border border-blue-100 flex justify-between">
                  <div>
                    <p class="text-xs text-blue-400 mb-1">姓名: <span class="text-sm font-medium text-slate-800">{{ op.name || '-' }}</span></p>
                    <p class="text-xs text-blue-400">身份证: <span class="font-mono text-slate-800">{{ op.id_number || '-' }}</span></p>
                  </div>
                  <div class="text-right">
                    <p class="text-xs text-blue-400 mb-1">手机:</p>
                    <p class="text-sm font-medium text-slate-800">{{ op.phone || '-' }}</p>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </main>
  </div>
</template>
