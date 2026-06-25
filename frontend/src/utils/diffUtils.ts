import type { DiffHighlightKind, DiffRecord } from "../types";

export const isOnlyInDiff = (diff: DiffRecord): boolean =>
  diff.payload.diff_type.includes("only_in") || diff.payload.diff_category === "only_in";

export const isPairedDiff = (diff: DiffRecord): boolean =>
  !isOnlyInDiff(diff) && diff.loc_a !== null && diff.loc_b !== null;

export const getHighlightKind = (diff: DiffRecord): DiffHighlightKind =>
  isOnlyInDiff(diff) ? "only-in" : "other";

export const getDiffSummary = (diff: DiffRecord): string => {
  const payload = diff.payload;
  if (payload.a_value || payload.b_value) {
    return `A: ${payload.a_value ?? ""} | B: ${payload.b_value ?? ""}`;
  }
  if (payload.a_row_content) return payload.a_row_content;
  if (payload.b_row_content) return payload.b_row_content;
  if (payload.a_text) return payload.a_text;
  if (payload.b_text) return payload.b_text;
  if (payload.diff?.length) {
    return payload.diff.map((item) => `${item.A} ↔ ${item.B}`).join("; ");
  }
  return diff.scope.path_a;
};
