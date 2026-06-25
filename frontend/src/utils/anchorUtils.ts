import type { BBox, DiffLoc, DiffRecord, SupportedFileType } from "../types";

/** PDF 侧 loc 带 page；DOCX 侧 loc 带 stream/table 而无 page */
export const isPdfLoc = (loc: DiffLoc | null | undefined): loc is DiffLoc =>
  loc != null && typeof loc.page === "number";

const locMatches = (left: DiffLoc, right: DiffLoc): boolean => {
  if (isPdfLoc(left) && isPdfLoc(right)) {
    return left.page === right.page && left.row === right.row && left.col === right.col;
  }
  return (
    left.table_index === right.table_index &&
    left.row === right.row &&
    left.col === right.col
  );
};

/** 按当前预览文件类型选取 loc：PDF 取含 page 的一侧，DOCX 取另一侧 */
export const pickLocForFileType = (
  diff: DiffRecord,
  fileType: SupportedFileType
): DiffLoc | null => {
  if (fileType === "pdf") {
    if (isPdfLoc(diff.loc_a)) return diff.loc_a;
    if (isPdfLoc(diff.loc_b)) return diff.loc_b;
    return null;
  }
  if (fileType === "docx") {
    if (diff.loc_a && !isPdfLoc(diff.loc_a)) return diff.loc_a;
    if (diff.loc_b && !isPdfLoc(diff.loc_b)) return diff.loc_b;
    return null;
  }
  return null;
};

export const pickPayloadSide = (diff: DiffRecord, loc: DiffLoc | null): "a" | "b" => {
  if (!loc) return "a";
  if (diff.loc_a && (loc === diff.loc_a || locMatches(loc, diff.loc_a))) return "a";
  if (diff.loc_b && (loc === diff.loc_b || locMatches(loc, diff.loc_b))) return "b";
  return isPdfLoc(loc) ? (isPdfLoc(diff.loc_a) ? "a" : "b") : "b";
};

export const getSideTextQueries = (
  diff: DiffRecord,
  fileType: SupportedFileType
): string[] => {
  const payload = diff.payload;
  const payloadSide = pickPayloadSide(diff, pickLocForFileType(diff, fileType));
  const values: string[] = [];

  if (payloadSide === "a") {
    if (payload.a_value) values.push(payload.a_value);
    if (payload.a_row_content) values.push(...payload.a_row_content.split("|"));
    if (payload.a_text) values.push(payload.a_text);
    payload.diff?.forEach((item) => values.push(item.A));
  } else {
    if (payload.b_value) values.push(payload.b_value);
    if (payload.b_row_content) values.push(...payload.b_row_content.split("|"));
    if (payload.b_text) values.push(payload.b_text);
    payload.diff?.forEach((item) => values.push(item.B));
  }

  const normalized = values.map((item) => item.trim()).filter(Boolean);
  return [...new Set(normalized)];
};

export const findDocxTableCellRect = (root: HTMLElement, loc: DiffLoc): DOMRect | null => {
  if (loc.table_index === undefined || loc.table_index < 0 || loc.row === undefined) {
    return null;
  }
  const table = root.querySelectorAll("table").item(loc.table_index);
  const row = table?.rows.item(loc.row);
  if (!row) return null;

  const targets =
    loc.col !== undefined && loc.col >= 0
      ? [row.cells.item(loc.col)].filter(Boolean)
      : Array.from(row.cells);

  if (!targets.length) return null;
  return mergeDomRects(targets.map((cell) => cell!.getBoundingClientRect()));
};

export const mergeBBoxes = (boxes: BBox[]): BBox | null => {
  if (!boxes.length) return null;
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;
  for (const box of boxes) {
    x0 = Math.min(x0, box[0]);
    y0 = Math.min(y0, box[1]);
    x1 = Math.max(x1, box[2]);
    y1 = Math.max(y1, box[3]);
  }
  return [x0, y0, x1, y1];
};

export const mergeDomRects = (rects: DOMRect[]): DOMRect | null => {
  if (!rects.length) return null;
  let left = Infinity;
  let top = Infinity;
  let right = -Infinity;
  let bottom = -Infinity;

  for (const rect of rects) {
    left = Math.min(left, rect.left);
    top = Math.min(top, rect.top);
    right = Math.max(right, rect.right);
    bottom = Math.max(bottom, rect.bottom);
  }

  return new DOMRect(left, top, right - left, bottom - top);
};

export const findTextRect = (root: HTMLElement, queries: string[]): DOMRect | null => {
  for (const query of queries) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let current = walker.nextNode();
    while (current) {
      const textNode = current as Text;
      const text = textNode.nodeValue ?? "";
      const idx = text.indexOf(query);
      if (idx >= 0) {
        const range = document.createRange();
        range.setStart(textNode, idx);
        range.setEnd(textNode, idx + query.length);
        const rect = range.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) return rect;
      }
      current = walker.nextNode();
    }
  }
  return null;
};

export const findPdfTextBBox = (
  items: Array<{ text: string; bbox: BBox }>,
  queries: string[]
): BBox | null => {
  for (const query of queries) {
    const matched = items.filter(
      (item) => item.text.includes(query) || query.includes(item.text.trim())
    );
    if (matched.length) {
      const merged = mergeBBoxes(matched.map((item) => item.bbox));
      if (merged) return merged;
    }
  }
  return null;
};

export const bboxToDomRect = (
  stage: HTMLElement,
  bbox: BBox,
  scale: number
): DOMRect => {
  const stageRect = stage.getBoundingClientRect();
  const [x0, y0, x1, y1] = bbox;
  return new DOMRect(
    stageRect.left + x0 * scale,
    stageRect.top + y0 * scale,
    (x1 - x0) * scale,
    (y1 - y0) * scale
  );
};
