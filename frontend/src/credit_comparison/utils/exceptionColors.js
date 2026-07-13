const exceptionColorPalette = {
  1: {
    color: "#3b82f6",
    borderColor: "#93c5fd",
    softColor: "rgba(59, 130, 246, 0.14)",
    solidSoftColor: "#e9f2ff",
    strongColor: "rgba(59, 130, 246, 0.24)",
    textColor: "#2563eb",
  },
  2: {
    color: "#f59e0b",
    borderColor: "#fcd34d",
    softColor: "rgba(245, 158, 11, 0.15)",
    solidSoftColor: "#fff3df",
    strongColor: "rgba(245, 158, 11, 0.24)",
    textColor: "#b45309",
  },
  3: {
    color: "#ef4444",
    borderColor: "#fca5a5",
    softColor: "rgba(239, 68, 68, 0.14)",
    solidSoftColor: "#fdecec",
    strongColor: "rgba(239, 68, 68, 0.24)",
    textColor: "#dc2626",
  },
  5: {
    color: "#8b5cf6",
    borderColor: "#c4b5fd",
    softColor: "rgba(139, 92, 246, 0.14)",
    solidSoftColor: "#f2ebff",
    strongColor: "rgba(139, 92, 246, 0.24)",
    textColor: "#7c3aed",
  },
  7: {
    color: "#ec4899",
    borderColor: "#f9a8d4",
    softColor: "rgba(236, 72, 153, 0.14)",
    solidSoftColor: "#fdeaf3",
    strongColor: "rgba(236, 72, 153, 0.24)",
    textColor: "#db2777",
  },
  8: {
    color: "#b7791f",
    borderColor: "#e7c27b",
    softColor: "rgba(183, 121, 31, 0.15)",
    solidSoftColor: "#f8efe2",
    strongColor: "rgba(183, 121, 31, 0.24)",
    textColor: "#8b5e16",
  },
  9: {
    color: "#14b8a6",
    borderColor: "#5eead4",
    softColor: "rgba(20, 184, 166, 0.14)",
    solidSoftColor: "#e2f8f5",
    strongColor: "rgba(20, 184, 166, 0.24)",
    textColor: "#0f766e",
  },
  10: {
    color: "#06b6d4",
    borderColor: "#67e8f9",
    softColor: "rgba(6, 182, 212, 0.15)",
    solidSoftColor: "#e1f8fc",
    strongColor: "rgba(6, 182, 212, 0.24)",
    textColor: "#0e7490",
  },
  12: {
    color: "#6366f1",
    borderColor: "#a5b4fc",
    softColor: "rgba(99, 102, 241, 0.15)",
    solidSoftColor: "#ececff",
    strongColor: "rgba(99, 102, 241, 0.24)",
    textColor: "#4f46e5",
  },
  13: {
    color: "#f97316",
    borderColor: "#fdba74",
    softColor: "rgba(249, 115, 22, 0.14)",
    solidSoftColor: "#fff7ed",
    strongColor: "rgba(249, 115, 22, 0.24)",
    textColor: "#ea580c",
  },
  15: {
    color: "#10b981",
    borderColor: "#6ee7b7",
    softColor: "rgba(16, 185, 129, 0.14)",
    solidSoftColor: "#ecfdf5",
    strongColor: "rgba(16, 185, 129, 0.22)",
    textColor: "#059669",
  },
  16: {
    color: "#7c3aed",
    borderColor: "#c4b5fd",
    softColor: "rgba(124, 58, 237, 0.14)",
    solidSoftColor: "#f3e8ff",
    strongColor: "rgba(124, 58, 237, 0.22)",
    textColor: "#6d28d9",
  },
  default: {
    color: "#64748b",
    borderColor: "#cbd5e1",
    softColor: "rgba(100, 116, 139, 0.12)",
    solidSoftColor: "#eef2f7",
    strongColor: "rgba(100, 116, 139, 0.18)",
    textColor: "#475569",
  },
};

const exceptionTypeAliases = {
  指标代码异常: 1,
  指标代码未找到: 1,
  指标名称异常: 2,
  指标名称不匹配: 2,
  指标数值异常: 3,
  指标金额计算有误: 3,
  表单无对应异常: 5,
  无关联表单: 5,
  关联公司数值异常: 7,
  关联公司增减金额不一致: 7,
  余额缺失异常: 8,
  余额缺失: 8,
  计算要求异常: 9,
  无合适计算币种: 9,
  excel异常: 10,
  对应多条excel记录: 10,
  格式异常: 12,
  格式待核对: 12,
  关联公司方向不一致: 13,
  关联公司增减方向与当前主句不一致: 13,
  同一记录关联公司重复出现: 15,
  标点符号异常: 16,
  标点符号待核对: 16,
};

export function resolveExceptionTypeId(typeId, typeName) {
  const numericTypeId = Number(typeId || 0);
  if (numericTypeId > 0) {
    return numericTypeId;
  }
  return exceptionTypeAliases[String(typeName || "").trim()] || 0;
}

export function getExceptionColorMeta(typeId, typeName = "") {
  const resolvedTypeId = resolveExceptionTypeId(typeId, typeName);
  return {
    typeId: resolvedTypeId,
    ...((resolvedTypeId && exceptionColorPalette[resolvedTypeId]) || exceptionColorPalette.default),
  };
}

export function buildExceptionColorStyle(typeId, typeName = "") {
  const colorMeta = getExceptionColorMeta(typeId, typeName);
  return {
    "--exception-color": colorMeta.color,
    "--exception-border-color": colorMeta.borderColor,
    "--exception-soft-color": colorMeta.softColor,
    "--exception-solid-soft-color": colorMeta.solidSoftColor,
    "--exception-strong-color": colorMeta.strongColor,
    "--exception-text-color": colorMeta.textColor,
  };
}
