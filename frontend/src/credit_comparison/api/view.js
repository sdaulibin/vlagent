import { resolveExceptionTypeId } from "../utils/exceptionColors";
import { api } from "../../api";

// 用宿主 axios 实例统一发起请求（已内置 token 注入与 401 拦截）。
// 路径前缀 /credit-comparison 与后端 router 对齐。
const API_PREFIX = "/credit-comparison";

async function fetchJson(url, options = {}) {
  // 宿主 axios 实例 baseURL 已含 /api，故剥离 url 开头的 /api 前缀避免重复。
  const normalizedUrl = String(url || "").replace(/^\/api\//, "/");
  const method = (options.method || "GET").toUpperCase();
  const axiosConfig = { method };
  if (options.body instanceof FormData) {
    // FormData 上传：交由 axios 自动设置 Content-Type。
    axiosConfig.data = options.body;
  } else if (options.body !== undefined) {
    axiosConfig.data = options.body;
  }
  const response = await api.request(normalizedUrl, axiosConfig);
  return response.data;
}

const exceptionDisplayNameMap = {
  指标代码异常: "指标代码未找到",
  指标名称异常: "指标名称不匹配",
  指标数值异常: "指标金额计算有误",
  表单无对应异常: "无关联表单",
  关联公司数值异常: "关联公司增减金额不一致",
  关联公司方向不一致: "关联公司增减方向与当前主句不一致",
  余额缺失异常: "余额缺失",
  计算要求异常: "无合适计算币种",
  标点符号异常: "格式待核对",
  格式异常: "格式待核对",
  excel异常: "对应多条excel记录",
};

function getExceptionDisplayName(name) {
  return exceptionDisplayNameMap[String(name || "").trim()] || String(name || "");
}

function buildExceptionMeta(typeId, typeName) {
  const displayName = getExceptionDisplayName(typeName);
  return {
    typeId: resolveExceptionTypeId(typeId, typeName || displayName),
    typeName: displayName,
  };
}

function buildExceptionTypeListFromSummary(summary) {
  return [
    ...new Map(
      String(summary || "")
        .split("|")
        .map((name) => name.trim())
        .filter(Boolean)
        .map((name) => {
          const exceptionMeta = buildExceptionMeta(0, name);
          return [`${exceptionMeta.typeId}-${exceptionMeta.typeName}`, exceptionMeta];
        }),
    ).values(),
  ];
}

function formatBatchAsTime(batchId) {
  const text = String(batchId || "");
  if (!/^\d{14}$/.test(text)) {
    return text;
  }
  return `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)} ${text.slice(8, 10)}:${text.slice(10, 12)}:${text.slice(12, 14)}`;
}

function parseSourceRefStart(value) {
  const text = String(value || "").trim();
  if (!text) {
    return null;
  }
  const match = text.match(/^(\d+)/);
  return match ? Number(match[1]) : null;
}

function isLikelyAnchorMatch(paragraph, anchor) {
  const text = String(paragraph?.text || "");
  const code = String(anchor?.code || "");
  const name = String(anchor?.name || "");
  const context = String(anchor?.context || "");
  return (code && text.includes(code)) || (name && text.includes(name)) || (context && (text === context || text.includes(context)));
}

function isParaindexUnique(paragraphs, paraindex) {
  if (!paraindex) {
    return false;
  }
  return paragraphs.filter((item) => item.paraindex === paraindex).length === 1;
}

function buildWordParagraphTargetMap(paragraphs, anchors) {
  const targetMap = new Map();

  for (const anchor of anchors || []) {
    const anchorSheet = String(anchor.sheet || "");
    const scopedParagraphs = anchorSheet ? paragraphs.filter((item) => String(item.sheet || "") === anchorSheet) : paragraphs;
    const sourceRefStart = parseSourceRefStart(anchor.source_ref);
    const targetFromRef = sourceRefStart
      ? scopedParagraphs.find((item) => Number(item.paragraph_index) === Number(sourceRefStart))
      : null;

    const target =
      (targetFromRef && isLikelyAnchorMatch(targetFromRef, anchor) ? targetFromRef : null) ||
      scopedParagraphs.find((item) => item.text === anchor.context) ||
      scopedParagraphs.find((item) => String(item.text || "").includes(String(anchor.context || ""))) ||
      scopedParagraphs.find(
        (item) =>
          String(item.text || "").includes(String(anchor.code || "")) &&
          String(item.text || "").includes(String(anchor.name || "")),
      ) ||
      (anchor.paraindex && isParaindexUnique(scopedParagraphs, anchor.paraindex)
        ? scopedParagraphs.find((item) => item.paraindex === anchor.paraindex)
        : null) ||
      (sourceRefStart
        ? paragraphs.find(
            (item) =>
              Number(item.paragraph_index) === Number(sourceRefStart) && isLikelyAnchorMatch(item, anchor),
          )
        : null) ||
      paragraphs.find((item) => item.text === anchor.context) ||
      paragraphs.find((item) => String(item.text || "").includes(String(anchor.context || ""))) ||
      paragraphs.find(
        (item) =>
          String(item.text || "").includes(String(anchor.code || "")) &&
          String(item.text || "").includes(String(anchor.name || "")),
      ) ||
      (anchor.paraindex && isParaindexUnique(paragraphs, anchor.paraindex)
        ? paragraphs.find((item) => item.paraindex === anchor.paraindex)
        : null);

    if (target) {
      targetMap.set(Number(anchor.word_record_id), target.node_id);
    }
  }

  return targetMap;
}

function normalizeHighlightTokens(item, exceptionMeta = null) {
  const tokens = item?.highlightTokens || item?.highlight_tokens || [];
  const firstOnly = Boolean(item?.highlightFirstOnly || item?.highlight_first_only);
  return [
    ...new Map(
      (tokens || [])
        .map((token) =>
          typeof token === "string"
            ? {
                text: String(token || "").trim(),
                firstOnly,
                variant: "",
                withinText: "",
              }
            : {
                text: String(token?.text || "").trim(),
                firstOnly: token?.first_only === undefined ? firstOnly : Boolean(token?.first_only),
                variant: String(token?.variant || ""),
                withinText: String(token?.within_text || ""),
                withinOffset:
                  token?.within_offset === undefined || token?.within_offset === null
                    ? null
                    : Number(token?.within_offset),
              },
        )
        .filter((token) => token.text)
        .map((token) => [
          `${token.text}::${exceptionMeta?.typeId || item?.exceptionTypeId || item?.type_id || 0}::${token.variant}::${token.withinText}::${token.withinOffset ?? ""}`,
          {
            text: token.text,
            firstOnly: token.firstOnly,
            typeId: exceptionMeta?.typeId || item?.exceptionTypeId || item?.type_id || 0,
            typeName: exceptionMeta?.typeName || item?.exceptionTypeName || item?.type_name || "",
            variant: token.variant,
            withinText: token.withinText,
            withinOffset: token.withinOffset,
          },
        ]),
    ).values(),
  ];
}

function buildTextHighlightSegments(text, tokens) {
  const sourceText = String(text || "");
  const escapePatternText = (value) => String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const buildLooseRegex = (value) => {
    const tokenText = String(value || "");
    if (!tokenText) {
      return null;
    }
    const pattern = [...tokenText].map((char) => `${escapePatternText(char)}\\s*`).join("");
    try {
      return new RegExp(pattern, "gu");
    } catch (error) {
      return null;
    }
  };
  const normalizedTokens = (tokens || [])
    .map((item) =>
      typeof item === "string"
        ? { text: String(item || "").trim(), firstOnly: false, typeId: 0, typeName: "" }
        : {
            text: String(item?.text || "").trim(),
            firstOnly: Boolean(item?.firstOnly),
            typeId: Number(item?.typeId || 0),
            typeName: String(item?.typeName || ""),
            variant: String(item?.variant || ""),
            withinText: String(item?.withinText || ""),
            withinOffset:
              item?.withinOffset === undefined || item?.withinOffset === null ? null : Number(item?.withinOffset),
          },
    )
    .filter((item) => item.text && (sourceText.includes(item.text) || (item.withinText && sourceText.includes(item.withinText))))
    .sort((left, right) => right.text.length - left.text.length);

  if (!normalizedTokens.length) {
    return [{ text: sourceText, highlight: false }];
  }

  const ranges = [];
  for (const token of normalizedTokens) {
    if (token.withinText && sourceText.includes(token.withinText)) {
      let scopeStart = 0;
      while (scopeStart < sourceText.length) {
        const withinStart = sourceText.indexOf(token.withinText, scopeStart);
        if (withinStart < 0) {
          break;
        }
        const localStart =
          token.withinOffset !== null && token.withinOffset >= 0 ? token.withinOffset : token.withinText.indexOf(token.text);
        let localMatchLength = token.text.length;
        let resolvedLocalStart = localStart;
        if (resolvedLocalStart < 0) {
          const looseRegex = buildLooseRegex(token.text);
          if (looseRegex) {
            const match = looseRegex.exec(token.withinText);
            if (match) {
              resolvedLocalStart = match.index;
              localMatchLength = match[0].length;
            }
          }
        }
        if (resolvedLocalStart >= 0) {
          const start = withinStart + resolvedLocalStart;
          const end = start + localMatchLength;
          const hasOverlap = ranges.some((range) => !(end <= range.start || start >= range.end));
          if (!hasOverlap) {
            ranges.push({
              start,
              end,
              typeId: token.typeId,
              typeName: token.typeName,
              variant: token.variant,
            });
          }
          if (token.firstOnly) {
            break;
          }
        }
        scopeStart = withinStart + token.withinText.length;
      }
      continue;
    }
    let searchStart = 0;
    while (searchStart < sourceText.length) {
      let start = sourceText.indexOf(token.text, searchStart);
      let end = start + token.text.length;
      if (start < 0 && token.text.length > 1) {
        const looseRegex = buildLooseRegex(token.text);
        if (looseRegex) {
          looseRegex.lastIndex = searchStart;
          const match = looseRegex.exec(sourceText);
          if (match) {
            start = match.index;
            end = start + match[0].length;
          }
        }
      }
      if (start < 0) {
        break;
      }
      const hasOverlap = ranges.some((range) => !(end <= range.start || start >= range.end));
      if (!hasOverlap) {
        ranges.push({
          start,
          end,
          typeId: token.typeId,
          typeName: token.typeName,
          variant: token.variant,
        });
      }
      if (token.firstOnly) {
        break;
      }
      searchStart = start + Math.max(1, end - start);
    }
  }

  ranges.sort((left, right) => left.start - right.start);
  if (!ranges.length) {
    return [{ text: sourceText, highlight: false }];
  }

  const segments = [];
  let cursor = 0;
  for (const range of ranges) {
    if (range.start > cursor) {
      segments.push({ text: sourceText.slice(cursor, range.start), highlight: false });
    }
    segments.push({
      text: sourceText.slice(range.start, range.end),
      highlight: true,
      typeId: range.typeId,
      typeName: range.typeName,
      highlightVariant: range.variant,
    });
    cursor = range.end;
  }
  if (cursor < sourceText.length) {
    segments.push({ text: sourceText.slice(cursor), highlight: false });
  }
  return segments.filter((segment) => segment.text);
}

function buildWordParagraphs(wordPreviewData, wordAnchorList, exceptionGroups) {
  const paragraphs = (wordPreviewData && wordPreviewData.paragraphs) || [];
  const targetMap = buildWordParagraphTargetMap(paragraphs, wordAnchorList || []);
  const nodeAnchorMap = new Map();
  const exceptionMap = new Map();
  const highlightTokenMap = new Map();

  for (const group of exceptionGroups || []) {
    const exceptionMeta = buildExceptionMeta(group.typeId || group.type_id, group.typeName || group.type_name || "");
    for (const item of group.items || []) {
      const targetWordRecordId = Number(item.wordRecordId || item.word_record_id || 0);
      const bucket = exceptionMap.get(targetWordRecordId) || [];
      bucket.push(exceptionMeta);
      exceptionMap.set(targetWordRecordId, bucket);

      const tokenBucket = highlightTokenMap.get(targetWordRecordId) || [];
      tokenBucket.push(...normalizeHighlightTokens(item, exceptionMeta));
      highlightTokenMap.set(targetWordRecordId, tokenBucket);
    }
  }

  for (const anchor of wordAnchorList || []) {
    const nodeId = targetMap.get(Number(anchor.word_record_id));
    if (!nodeId) {
      continue;
    }
    const bucket = nodeAnchorMap.get(nodeId) || [];
    bucket.push(anchor);
    nodeAnchorMap.set(nodeId, bucket);
  }

  return paragraphs.map((paragraph) => {
    const anchors = nodeAnchorMap.get(paragraph.node_id) || [];
    const primaryAnchor = anchors[0];
    const exceptionMetas = anchors.flatMap((anchor) => exceptionMap.get(Number(anchor.word_record_id)) || []);
    const uniqueExceptionMetas = [
      ...new Map(
        exceptionMetas
          .filter((item) => item?.typeName)
          .map((item) => [`${item.typeId}-${item.typeName}`, item]),
      ).values(),
    ];
    const highlightTokens = [
      ...new Set(
        anchors.flatMap((anchor) => highlightTokenMap.get(Number(anchor.word_record_id)) || []).filter(Boolean),
      ),
    ];
    const text = paragraph.text || "";

    return {
      id: paragraph.node_id,
      nodeId: paragraph.node_id,
      paragraphIndex: Number(paragraph.paragraph_index || 0),
      sheet: paragraph.sheet || "",
      code: primaryAnchor?.code || "",
      name: primaryAnchor?.name || "",
      text,
      textSegments: buildTextHighlightSegments(text, highlightTokens),
      tag: uniqueExceptionMetas.map((item) => item.typeName).join(" | "),
      exceptionTypes: uniqueExceptionMetas,
      primaryExceptionTypeId: uniqueExceptionMetas[0]?.typeId || 0,
      primaryExceptionTypeName: uniqueExceptionMetas[0]?.typeName || "",
      wordRecordIds: anchors.map((item) => Number(item.word_record_id)),
      anchors: anchors.map((item) => ({
        wordRecordId: Number(item.word_record_id),
        code: item.code || "",
        name: item.name || "",
        hasException: Boolean(item.has_exception),
      })),
      isSheetTitle: Boolean(paragraph.is_sheet_title),
    };
  });
}

function buildWordSections(wordParagraphs) {
  const sectionMap = new Map();
  let fallbackIndex = 0;

  for (const paragraph of wordParagraphs || []) {
    const sheet = String(paragraph.sheet || `NO_SHEET_${fallbackIndex}`);
    fallbackIndex += 1;
    const section = sectionMap.get(sheet) || {
      sheet,
      title: sheet.startsWith("NO_SHEET_") ? "未识别表单" : `${sheet} 对比内容`,
      paragraphs: [],
    };

    if (paragraph.isSheetTitle && paragraph.sheet) {
      section.title = paragraph.text;
    }

    section.paragraphs.push(paragraph);
    sectionMap.set(sheet, section);
  }

  return [...sectionMap.values()].filter((item) => item.paragraphs.length);
}

function toExcelColumnLabel(columnNumber) {
  let current = Number(columnNumber);
  let label = "";
  while (current > 0) {
    const remainder = (current - 1) % 26;
    label = String.fromCharCode(65 + remainder) + label;
    current = Math.floor((current - 1) / 26);
  }
  return label;
}

function detectExcelIndicatorCodeColumn(sheet) {
  const rows = (sheet && sheet.rows) || [];
  const scanRowLimit = Math.min(rows.length, 30);
  for (let rowIndex = 0; rowIndex < scanRowLimit; rowIndex += 1) {
    const row = rows[rowIndex];
    const cells = (row && row.cells) || [];
    for (const cell of cells) {
      const text = String(cell.text || "").replace(/\s+/g, "");
      if (text.includes("指标代码") || text.includes("指标编号") || text.includes("指标编码")) {
        return Number(cell.col_index) || 1;
      }
    }
  }
  return 1;
}

function detectExcelContentHeaderEndRowIndex(sheet) {
  const rows = (sheet && sheet.rows) || [];
  const scanRowLimit = Math.min(rows.length, 50);
  for (let rowIndex = 0; rowIndex < scanRowLimit; rowIndex += 1) {
    const row = rows[rowIndex];
    const cells = (row && row.cells) || [];
    for (const cell of cells) {
      const text = String(cell.text || "").replace(/\s+/g, "");
      if (text.includes("余额")) {
        return Number(row.row_index) || 1;
      }
    }
  }
  return Math.min(2, rows.length);
}

function normalizeExcelRowCells(row) {
  return ((row && row.cells) || []).map((cell) => ({
    text: cell.text || "",
    colIndex: Number(cell.col_index) || 1,
    colspan: Math.max(1, Number(cell.colspan) || 1),
    rowspan: Math.max(1, Number(cell.rowspan) || 1),
  }));
}

function normalizeAmountText(value) {
  const text = String(value || "");
  if (!text) {
    return "";
  }
  return text.replace(/([0-9][0-9,]*)\.0+(?=[^\d]|$)/g, "$1");
}

function buildCompanyExceptionItemKey(company, entry, index) {
  return [
    "company",
    Number(entry.exception_id || entry.exceptionId || 0),
    String(company || "").trim(),
    Number(entry.word_record_id || entry.wordRecordId || 0),
    String(entry.sheet || "").trim(),
    String(entry.code || "").trim(),
    index,
  ].join("-");
}

function isFormatExceptionGroup(typeId) {
  return Number(typeId || 0) === 12;
}

function isPunctuationToken(text) {
  const value = String(text || "");
  if (value.length !== 1) {
    return false;
  }
  try {
    return /\p{P}/u.test(value);
  } catch (error) {
    return /[，。；：、“”‘’（）()《》〈〉【】\[\]{}'"!?…—\-·]/.test(value);
  }
}

function buildFormatExceptionReason(item) {
  const fieldName = String(item?.fieldName || item?.field_name || "").trim();
  const value = String(item?.value || "").trim();
  if (fieldName === "profit_loss_unit") {
    return value ? `金额单位(${value})` : "金额单位";
  }

  if ((fieldName === "main_sentence" || fieldName === "company_detail") && isPunctuationToken(value)) {
    return "标点符号";
  }

  if (fieldName === "main_sentence") {
    return "主句格式";
  }

  if (fieldName === "company_detail") {
    return value ? `${value}格式` : "格式";
  }

  if (fieldName === "company_marker" || fieldName === "company_detail_tail") {
    return "明细段格式";
  }

  return "主句格式";
}

function buildFormatExceptionAggregatedItems(items) {
  const recordMap = new Map();
  for (const entry of items || []) {
    const wordRecordId = Number(entry.wordRecordId || entry.word_record_id || 0);
    if (!wordRecordId) {
      continue;
    }
    const bucket = recordMap.get(wordRecordId) || {
      wordRecordId,
      sheet: entry.sheet || "",
      code: entry.code || "",
      name: entry.name || "",
      reasons: [],
      excelRowIndexes: [],
      highlightTokens: [],
    };
    const reason = buildFormatExceptionReason(entry);
    if (reason && !bucket.reasons.includes(reason)) {
      bucket.reasons.push(reason);
    }
    bucket.excelRowIndexes.push(...(entry.excelRowIndexes || []));
    bucket.highlightTokens.push(...(entry.highlightTokens || []));
    recordMap.set(wordRecordId, bucket);
  }

  return [...recordMap.values()]
    .map((bucket) => {
      const reasonText = bucket.reasons.join(" | ");
      const uniqueRowIndexes = [...new Set(bucket.excelRowIndexes.map((value) => Number(value)).filter((value) => value > 0))].sort(
        (left, right) => left - right,
      );
      const uniqueTokens = [
        ...new Map(
          bucket.highlightTokens
            .filter((token) => token && String(token.text || "").trim())
            .map((token) => [`${String(token.text || "").trim()}::${String(token.variant || "")}::${String(token.withinText || "")}::${token.withinOffset ?? ""}`, token]),
        ).values(),
      ];
      const itemKey = `format-${bucket.wordRecordId}-${String(bucket.sheet || "").trim()}-${String(bucket.code || "").trim()}`;
      return {
        id: itemKey,
        itemKey,
        wordRecordId: bucket.wordRecordId,
        sheet: bucket.sheet,
        code: bucket.code,
        name: bucket.name,
        fieldName: "format_reason",
        value: reasonText,
        excelRowIndexes: uniqueRowIndexes,
        highlightTokens: uniqueTokens,
      };
    })
    .sort((left, right) => {
      const sheetCompare = String(left.sheet || "").localeCompare(String(right.sheet || ""), "zh-CN");
      if (sheetCompare !== 0) {
        return sheetCompare;
      }
      const codeCompare = String(left.code || "").localeCompare(String(right.code || ""), "zh-CN");
      if (codeCompare !== 0) {
        return codeCompare;
      }
      return Number(left.wordRecordId || 0) - Number(right.wordRecordId || 0);
    });
}

function buildCompanyNameMergedItems(items, typeId) {
  const mergedMap = new Map();
  for (const entry of items || []) {
    const wordRecordId = Number(entry.wordRecordId || entry.word_record_id || 0);
    const sheet = String(entry.sheet || "");
    const code = String(entry.code || "");
    const name = String(entry.name || "");
    const company = String(entry.value || entry.company || "").trim();
    if (!wordRecordId || !company) {
      continue;
    }
    const key = `${wordRecordId}::${sheet}::${code}::${company}`;
    const bucket = mergedMap.get(key) || {
      wordRecordId,
      sheet,
      code,
      name,
      company,
      excelRowIndexes: [],
      highlightTokens: [],
    };
    bucket.excelRowIndexes.push(...(entry.excelRowIndexes || []));
    bucket.highlightTokens.push(...(entry.highlightTokens || []));
    mergedMap.set(key, bucket);
  }

  return [...mergedMap.values()]
    .map((bucket) => {
      const uniqueRowIndexes = [
        ...new Set(bucket.excelRowIndexes.map((value) => Number(value)).filter((value) => value > 0)),
      ].sort((left, right) => left - right);
      const uniqueTokens = [
        ...new Map(
          bucket.highlightTokens
            .filter((token) => token && String(token.text || "").trim())
            .map((token) => [
              `${String(token.text || "").trim()}::${String(token.variant || "")}::${String(token.withinText || "")}::${token.withinOffset ?? ""}`,
              token,
            ]),
        ).values(),
      ];
      const itemKey = `company-merge-${Number(typeId || 0)}-${bucket.wordRecordId}-${bucket.sheet}-${bucket.code}-${bucket.company}`;
      return {
        id: itemKey,
        itemKey,
        wordRecordId: bucket.wordRecordId,
        sheet: bucket.sheet,
        code: bucket.code,
        name: bucket.name,
        fieldName: "company",
        value: bucket.company,
        excelRowIndexes: uniqueRowIndexes,
        highlightTokens: uniqueTokens,
      };
    })
    .sort((left, right) => {
      const sheetCompare = String(left.sheet || "").localeCompare(String(right.sheet || ""), "zh-CN");
      if (sheetCompare !== 0) {
        return sheetCompare;
      }
      const codeCompare = String(left.code || "").localeCompare(String(right.code || ""), "zh-CN");
      if (codeCompare !== 0) {
        return codeCompare;
      }
      const nameCompare = String(left.name || "").localeCompare(String(right.name || ""), "zh-CN");
      if (nameCompare !== 0) {
        return nameCompare;
      }
      const companyCompare = String(left.value || "").localeCompare(String(right.value || ""), "zh-CN");
      if (companyCompare !== 0) {
        return companyCompare;
      }
      return Number(left.wordRecordId || 0) - Number(right.wordRecordId || 0);
    });
}

function buildExceptionGroups(exceptionGroups, exceptionCompanyList) {
  const companyExceptionTypeMap = new Map();
  for (const companyGroup of exceptionCompanyList || []) {
    const companyName = String(companyGroup.company || "").trim();
    if (!companyName) {
      continue;
    }
    for (const [index, entry] of (companyGroup.entries || []).entries()) {
      const { typeId, typeName } = buildExceptionMeta(entry.exception_id, entry.exception_name);
      if (!typeId) {
        continue;
      }
      const typeBucket = companyExceptionTypeMap.get(typeId) || {
        typeId,
        typeName,
        companyMap: new Map(),
      };
      const companyBucket = typeBucket.companyMap.get(companyName) || {
        company: companyName,
        items: [],
      };
      companyBucket.items.push({
        id: buildCompanyExceptionItemKey(companyName, entry, index),
        itemKey: buildCompanyExceptionItemKey(companyName, entry, index),
        wordRecordId: Number(entry.word_record_id || 0),
        sheet: entry.sheet || "",
        code: entry.code || "",
        name: entry.name || "",
        fieldName: "company",
        value: companyName,
        company: companyName,
        amountText: normalizeAmountText(entry.amount_text),
        highlightTokens: normalizeHighlightTokens(entry),
        exceptionTypeId: typeId,
        exceptionTypeName: typeName,
      });
      typeBucket.companyMap.set(companyName, companyBucket);
      companyExceptionTypeMap.set(typeId, typeBucket);
    }
  }

  const normalizedGroups = (exceptionGroups || []).map((group) => {
    const { typeId, typeName } = buildExceptionMeta(group.type_id, group.type_name);
    const companyBucket = companyExceptionTypeMap.get(typeId);
    if (companyBucket && !isFormatExceptionGroup(typeId)) {
      const companyGroups = [...companyBucket.companyMap.values()]
        .map((item) => ({
          ...item,
          entryCount: Number(item.items.length || 0),
        }))
        .sort((left, right) => String(left.company || "").localeCompare(String(right.company || ""), "zh-CN"));
      return {
        typeId,
        typeName,
        items: companyGroups.flatMap((item) =>
          item.items.map((entry) => ({
            ...entry,
            exceptionTypeId: typeId,
            exceptionTypeName: typeName,
          })),
        ),
        companyGroups,
      };
    }
    return {
      typeId,
      typeName,
      items: (group.items || []).map((item) => ({
        id: item.id,
        wordRecordId: item.word_record_id,
        sheet: item.sheet,
        code: item.code,
        name: item.name,
        fieldName: item.field_name,
        value: item.value,
        excelRowIndexes: (item.excel_row_indexes || []).map((rowIndex) => Number(rowIndex)).filter((rowIndex) => rowIndex > 0),
        highlightTokens: normalizeHighlightTokens(item),
        exceptionTypeId: typeId,
        exceptionTypeName: typeName,
      })),
    };
  });

  for (const group of normalizedGroups) {
    if (isFormatExceptionGroup(group.typeId)) {
      group.items = buildFormatExceptionAggregatedItems(group.items || []);
    }
    if (Number(group.typeId || 0) === 13 || Number(group.typeId || 0) === 15) {
      group.items = buildCompanyNameMergedItems(group.items || [], group.typeId);
    }
  }

  const existingTypeIds = new Set(normalizedGroups.map((group) => Number(group.typeId || 0)));
  const extraGroups = [...companyExceptionTypeMap.values()]
    .filter((bucket) => !existingTypeIds.has(Number(bucket.typeId || 0)))
    .map((bucket) => {
      const companyGroups = [...bucket.companyMap.values()]
        .map((item) => ({
          ...item,
          entryCount: Number(item.items.length || 0),
        }))
        .sort((left, right) => String(left.company || "").localeCompare(String(right.company || ""), "zh-CN"));
      return {
        typeId: bucket.typeId,
        typeName: bucket.typeName,
        items: companyGroups.flatMap((item) =>
          item.items.map((entry) => ({
            ...entry,
            exceptionTypeId: bucket.typeId,
            exceptionTypeName: bucket.typeName,
          })),
        ),
        companyGroups,
      };
    });

  return [...normalizedGroups, ...extraGroups].sort((left, right) => Number(left.typeId || 0) - Number(right.typeId || 0));
}

function buildExcelSheets(excelPreviewData, excelAnchorList, linkList) {
  const sheets = (excelPreviewData && excelPreviewData.sheets) || [];
  const anchorMap = new Map((excelAnchorList || []).map((item) => [Number(item.excel_record_id), item]));
  const rowLinkMap = new Map();

  for (const link of linkList || []) {
    if (link.excel_record_id === null || link.excel_record_id === undefined) {
      continue;
    }
    const anchor = anchorMap.get(Number(link.excel_record_id));
    if (!anchor) {
      continue;
    }
    const key = `${anchor.sheet}::${Number(anchor.excel_row_index)}`;
    const bucket = rowLinkMap.get(key) || [];
    bucket.push(link);
    rowLinkMap.set(key, bucket);
  }

  return sheets.map((sheet) => {
    const indicatorCodeCol = detectExcelIndicatorCodeColumn(sheet);
    const headerEndRowIndex = detectExcelContentHeaderEndRowIndex(sheet);
    const headerRows = (sheet.rows || []).filter((row) => Number(row.row_index) <= Number(headerEndRowIndex || 0));
    const rows = (sheet.rows || []).filter((row) => Number(row.row_index) > Number(headerEndRowIndex || 0));
    const maxColCount = Math.max(
      0,
      ...(sheet.rows || []).map((row) =>
        Math.max(
          0,
          ...normalizeExcelRowCells(row).map((cell) => Number(cell.colIndex + cell.colspan - 1) || 0),
        ),
      ),
    );

    const normalizedRows = rows.map((row) => {
      const cells = normalizeExcelRowCells(row);
      const rowLinks = rowLinkMap.get(`${sheet.name}::${Number(row.row_index)}`) || [];
      const exceptionNames = [
        ...new Set(
          rowLinks.flatMap((item) =>
            String(item.exception_summary || "")
              .split("|")
              .map((name) => name.trim())
              .filter(Boolean),
          ),
        ),
      ];
      const exceptionTypes = buildExceptionTypeListFromSummary(exceptionNames.join("|"));
      return {
        id: `${sheet.name}-${row.row_index}`,
        rowIndex: Number(row.row_index),
        cells,
        code: cells.find((cell) => Number(cell.colIndex) === Number(indicatorCodeCol))?.text || "",
        rowLinks,
        excelRecordIds: rowLinks
          .map((item) => item.excel_record_id)
          .filter((value) => value !== null && value !== undefined)
          .map((value) => Number(value)),
        exceptionNames,
        exceptionTypes,
        primaryExceptionTypeId: exceptionTypes[0]?.typeId || 0,
        primaryExceptionTypeName: exceptionTypes[0]?.typeName || "",
        hasException: rowLinks.some((item) => Boolean(item.has_exception)),
        hasOnlyBalanceMissing:
          exceptionNames.length > 0 && exceptionNames.every((name) => name === "余额缺失异常"),
      };
    });

    return {
      sheet: sheet.name,
      codeColumnIndex: indicatorCodeCol - 1,
      columnLabels: Array.from({ length: maxColCount }, (_, index) => toExcelColumnLabel(index + 1)),
      headerRows: headerRows.map((row) => ({
        id: `${sheet.name}-header-${row.row_index}`,
        rowIndex: Number(row.row_index),
        cells: normalizeExcelRowCells(row),
      })),
      headerEndRowIndex,
      rows: normalizedRows,
    };
  });
}

function buildDetailTask(detail, wordPreviewData, excelPreviewData) {
  const linkList = detail.link_list || [];
  const matchedLinks = linkList.filter((item) => item.excel_record_id !== null && item.excel_record_id !== undefined);
  const unmatchedLinks = linkList.filter((item) => item.excel_record_id === null || item.excel_record_id === undefined);
  const exceptionGroups = detail.exception_group_list || [];
  const wordParagraphs = buildWordParagraphs(wordPreviewData, detail.word_anchor_list || [], exceptionGroups);

  return {
    taskId: `${detail.batch_id || ""}::${detail.word_file_name || ""}`,
    title: detail.word_file_name || "",
    wordFileName: detail.word_file_name || "",
    excelFileName: detail.excel_file_name || "",
    batchId: detail.batch_id || "",
    summary: {
      linkCount: matchedLinks.length,
      exceptionCount: matchedLinks.filter((item) => item.has_exception).length,
      unmatchedCount: unmatchedLinks.length,
    },
    exceptionGroups: buildExceptionGroups(exceptionGroups, detail.exception_company_list || []),
    linkList: matchedLinks.map((item) => {
      const exceptionTypes = buildExceptionTypeListFromSummary(item.exception_summary || "");
      return {
        ...(exceptionTypes[0] || {}),
        exceptionTypes,
        compareLinkId: Number(item.compare_link_id),
        wordRecordId: Number(item.word_record_id),
        excelRecordId: item.excel_record_id === null || item.excel_record_id === undefined ? null : Number(item.excel_record_id),
        wordSheet: item.word_sheet || "",
        excelSheet: item.excel_sheet || "",
        wordCode: item.word_code || "",
        wordName: item.word_name || "",
        hasException: Boolean(item.has_exception),
        exceptionSummary: item.exception_summary || "",
      };
    }),
    wordDocument: {
      fileName: detail.word_file_name || "",
      paragraphs: wordParagraphs,
    },
    wordSections: buildWordSections(wordParagraphs),
    excelSheets: buildExcelSheets(excelPreviewData, detail.excel_anchor_list || [], matchedLinks),
    wordAnchorList: (detail.word_anchor_list || []).map((item) => ({
      wordRecordId: Number(item.word_record_id),
      sheet: item.sheet || "",
      code: item.code || "",
      name: item.name || "",
      paraindex: item.paraindex,
      sourceRef: item.source_ref || "",
      context: item.context || "",
      hasException: Boolean(item.has_exception),
    })),
    excelAnchorList: (detail.excel_anchor_list || []).map((item) => ({
      excelRecordId: Number(item.excel_record_id),
      sheet: item.sheet || "",
      code: item.code || "",
      name: item.name || "",
      excelRowIndex: Number(item.excel_row_index || 0),
      hasException: Boolean(item.has_exception),
    })),
  };
}

// 后端状态（英文）→ 前端展示状态（中文）。
const STATUS_DISPLAY_MAP = {
  pending: "待处理",
  processing: "处理中",
  done: "已完成",
  failed: "处理失败",
};

function mapStatus(status) {
  return STATUS_DISPLAY_MAP[String(status || "").trim()] || "待处理";
}

export async function listTaskItems({ page = 1, pageSize = 10, keyword = "" } = {}) {
  const data = await fetchJson(`${API_PREFIX}/tasks`);
  const allItems = (data.items || []).map((item) => ({
    id: item.id,
    batchId: item.batch_id,
    wordFileName: item.word_file_name,
    excelFileName: item.excel_file_name || "未匹配",
    createdAt: item.created_at || formatBatchAsTime(item.batch_id),
    updatedAt: item.updated_at || "",
    status: mapStatus(item.status),
    errorMessage: item.error_msg || "",
    linkCount: Number(item.link_count || 0),
    exceptionCount: Number(item.exception_count || 0),
    unmatchedCount: Number(item.unmatched_count || 0),
  }));

  // 后端返回全量，前端做关键词过滤 + 本地分页。
  const keywordText = String(keyword || "").trim();
  const filtered = keywordText
    ? allItems.filter((item) => String(item.wordFileName || "").includes(keywordText))
    : allItems;

  const currentPage = Math.max(1, Number(page || 1));
  const currentPageSize = Math.max(1, Number(pageSize || 10));
  const total = filtered.length;
  const start = (currentPage - 1) * currentPageSize;
  const pageItems = filtered.slice(start, start + currentPageSize).map((item, index) => ({
    ...item,
    id: item.id || `${item.batchId}::${item.wordFileName}`,
    projectId: start + index + 1,
  }));

  return {
    items: pageItems,
    total,
    page: currentPage,
    pageSize: currentPageSize,
  };
}

export async function createTaskItem({ wordFile, excelFile }) {
  const formData = new FormData();
  formData.append("word_file", wordFile);
  formData.append("excel_file", excelFile);
  const item = await fetchJson(`${API_PREFIX}/upload`, {
    method: "POST",
    body: formData,
  });
  return {
    id: item.id,
    batchId: item.batch_id || "",
    wordFileName: item.word_file_name || "",
    excelFileName: item.excel_file_name || "",
    status: mapStatus(item.status),
  };
}

export async function deleteTaskItem(batchId) {
  return fetchJson(`${API_PREFIX}/batches/${encodeURIComponent(batchId)}`, {
    method: "DELETE",
  });
}

export async function getTaskDetail(batchId, wordFileName, excelFileName = "") {
  const params = new URLSearchParams({
    word_file_name: String(wordFileName || ""),
  });
  if (String(excelFileName || "").trim()) {
    params.set("excel_file_name", String(excelFileName));
  }

  const detail = await fetchJson(`${API_PREFIX}/batches/${encodeURIComponent(batchId)}/detail?${params.toString()}`);
  detail.batch_id = batchId;

  const [wordPreviewData, excelPreviewData] = await Promise.all([
    detail.word_structured_preview_url ? fetchJson(detail.word_structured_preview_url) : Promise.resolve(null),
    detail.excel_structured_preview_url ? fetchJson(detail.excel_structured_preview_url) : Promise.resolve(null),
  ]);

  return buildDetailTask(detail, wordPreviewData, excelPreviewData);
}
