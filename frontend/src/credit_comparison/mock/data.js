export const exceptionTypeList = [
  { id: 1, name: "指标代码异常" },
  { id: 2, name: "指标名称异常" },
  { id: 3, name: "指标数值异常" },
  { id: 4, name: "指标数值单位异常" },
  { id: 5, name: "表单无对应异常" },
  { id: 6, name: "指标无对应异常" },
  { id: 7, name: "关联公司数值异常" },
  { id: 8, name: "余额缺失异常" },
  { id: 9, name: "计算要求异常" },
  { id: 10, name: "excel异常" },
  { id: 11, name: "其他异常" },
  { id: 12, name: "格式待核对" },
];

export const mockTasks = [
  {
    id: 7153,
    wordFileName: "青岛银行2025年4季度数据变动说明3.doc",
    excelFileName: "季报202512.xls",
    createdAt: "2026-06-11 17:48:26",
    status: "已完成",
    batchId: "20260622093948",
  },
  {
    id: 7107,
    wordFileName: "青岛银行月报第二批次数据说明(202512).doc",
    excelFileName: "月报二批202512.xls",
    createdAt: "2026-06-05 09:55:06",
    status: "处理中",
    batchId: "20260622093251",
  },
  {
    id: 7012,
    wordFileName: "青岛银行存量客户月度说明.docx",
    excelFileName: "存量客户月报.xlsx",
    createdAt: "2026-06-01 10:21:09",
    status: "待处理",
    batchId: "20260601095511",
  },
];

const detailMap = {
  7153: {
    taskId: 7153,
    title: "青岛银行2025年4季度数据变动说明3.doc",
    excelFileName: "季报202512.xls",
    batchId: "20260622093948",
    summary: {
      linkCount: 52,
      exceptionCount: 11,
      unmatchedCount: 3,
    },
    exceptionGroups: [
      {
        typeId: 1,
        typeName: "指标代码异常",
        items: [
          { id: "e-1", sheet: "A3301", code: "13F22", name: "青岛分行营业利润", fieldName: "code", value: "13F22" },
          { id: "e-2", sheet: "A3301", code: "13F25", name: "青岛分行净利润", fieldName: "code", value: "13F25" },
        ],
      },
      {
        typeId: 7,
        typeName: "关联公司数值异常",
        items: [
          { id: "e-3", sheet: "G0102", code: "G010201", name: "青岛银行股份有限公司", fieldName: "company", value: "金额不一致" },
          { id: "e-4", sheet: "G0103", code: "G010305", name: "青岛银行股份有限公司", fieldName: "company", value: "金额不一致" },
        ],
      },
      {
        typeId: 8,
        typeName: "余额缺失异常",
        items: [
          { id: "e-5", sheet: "A3302", code: "A330201", name: "贷款余额变动", fieldName: "cur_rmb_balance", value: "" },
        ],
      },
    ],
    wordSections: [
      {
        sheet: "A3301",
        title: "A3301 利润表分析",
        paragraphs: [
          {
            id: "w-1",
            code: "13F22",
            name: "青岛分行营业利润",
            tag: "指标代码异常",
            text: "A3301 表中，青岛分行营业利润本期同比下降，主要受利差收窄和拨备计提影响。",
          },
          {
            id: "w-2",
            code: "13F25",
            name: "青岛分行净利润",
            tag: "指标代码异常",
            text: "13F25 对应的净利润指标与表内编码未完全匹配，需要进一步核对说明与报表口径。",
          },
          {
            id: "w-3",
            code: "A330201",
            name: "贷款余额变动",
            tag: "余额缺失异常",
            text: "贷款余额变动主要受对公业务投放节奏影响，部分余额字段缺失，需人工复核。",
          },
        ],
      },
      {
        sheet: "G0102",
        title: "G0102 关联公司情况",
        paragraphs: [
          {
            id: "w-4",
            code: "G010201",
            name: "青岛银行股份有限公司",
            tag: "关联公司数值异常",
            text: "关联公司利润表中，青岛银行股份有限公司在多个表单中的金额出现差异。",
          },
        ],
      },
    ],
    excelSheets: [
      {
        sheet: "A3301",
        columns: ["指标代码", "指标名称", "本期余额", "上期余额", "差值"],
        rows: [
          ["13F20", "营业收入", "120.5", "118.1", "2.4"],
          ["13F22", "青岛分行营业利润", "19.2", "22.6", "-3.4"],
          ["13F25", "青岛分行净利润", "16.1", "18.4", "-2.3"],
        ],
      },
      {
        sheet: "A3302",
        columns: ["指标代码", "指标名称", "本期余额", "上期余额", "差值"],
        rows: [
          ["A330201", "贷款余额变动", "", "128.0", "-128.0"],
          ["A330202", "存款余额变动", "88.2", "76.0", "12.2"],
        ],
      },
      {
        sheet: "G0102",
        columns: ["公司", "表单", "指标代码", "本期金额"],
        rows: [
          ["青岛银行股份有限公司", "G0102", "G010201", "1.25"],
          ["青岛银行股份有限公司", "G0103", "G010305", "1.11"],
        ],
      },
    ],
  },
};

export function getTaskList() {
  return mockTasks.map((item) => ({ ...item }));
}

export function getTaskDetail(taskId) {
  const numericId = Number(taskId);
  const task = mockTasks.find((item) => item.id === numericId);
  const detail = detailMap[numericId];

  if (!task) {
    return null;
  }

  return {
    ...task,
    ...(detail || {
      taskId: numericId,
      title: task.wordFileName,
      excelFileName: task.excelFileName,
      batchId: task.batchId,
      summary: {
        linkCount: 0,
        exceptionCount: 0,
        unmatchedCount: 0,
      },
      exceptionGroups: exceptionTypeList.map((type) => ({
        typeId: type.id,
        typeName: type.name,
        items: [],
      })),
      wordSections: [],
      excelSheets: [],
    }),
  };
}
