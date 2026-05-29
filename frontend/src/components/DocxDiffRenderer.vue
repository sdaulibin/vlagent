<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue';
import { renderAsync } from 'docx-preview';
import { api } from '../api';
import type { SectionItem } from '../types';

interface DiffOp {
  op: number;
  text: string;
  offsetA?: number;
  offsetB?: number;
}

interface Props {
  taskId: number;
  fileAName: string;
  fileBName: string;
  sectionsA: SectionItem[];
  sectionsB: SectionItem[];
}

const props = defineProps<Props>();

const containerA = ref<HTMLDivElement | null>(null);
const containerB = ref<HTMLDivElement | null>(null);
const loading = ref(false);

async function loadDocx(docType: 'a' | 'b', container: HTMLDivElement) {
  const response = await api.get(
    `/documents/${props.taskId}/file/${docType}?raw=true`,
    { responseType: 'blob' },
  );
  await renderAsync(response.data, container, undefined, {
    className: 'docx-diff-preview',
    inWrapper: true,
    breakPages: true,
    ignoreWidth: false,
    ignoreHeight: false,
    ignoreFonts: false,
    renderHeaders: true,
    renderFooters: true,
    renderFootnotes: true,
    renderEndnotes: true,
  });
}

// Parse diff_ops_json from backend
function parseDiffOps(json: string | null): DiffOp[] {
  if (!json) return [];
  try {
    const raw = JSON.parse(json);
    if (!Array.isArray(raw)) return [];
    return raw.map((item: any) => {
      if (Array.isArray(item)) {
        const entry: Record<string, any> = { op: item[0] as number, text: item[1] as string };
        if (item.length >= 4) {
          entry.offsetA = item[2] as number;
          entry.offsetB = item[3] as number;
        }
        return entry as DiffOp;
      }
      return item as DiffOp;
    });
  } catch {
    return [];
  }
}

// Collect all text nodes in DOM order
function collectTextNodes(container: HTMLElement): Text[] {
  const nodes: Text[] = [];
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
  let node: Text | null;
  while ((node = walker.nextNode() as Text | null)) {
    if (node.textContent && node.textContent.trim()) {
      nodes.push(node);
    }
  }
  return nodes;
}

// Build normalized text (strip whitespace) → char position map
interface CharEntry { nodeIdx: number; charOffset: number }

function buildCharMap(textNodes: Text[]): { normalizedText: string; charMap: CharEntry[] } {
  let normalizedText = '';
  const charMap: CharEntry[] = [];
  for (let i = 0; i < textNodes.length; i++) {
    const text = textNodes[i].textContent!;
    for (let c = 0; c < text.length; c++) {
      const ch = text[c];
      if (/\s/.test(ch)) continue;
      charMap.push({ nodeIdx: i, charOffset: c });
      normalizedText += ch;
    }
  }
  return { normalizedText, charMap };
}

// Find segment positions using context-window matching (same strategy as PDF.js)
interface SegmentMatch { start: number; end: number }

function normalizeDiffText(text: string | undefined | null): string {
  return (text || '').replace(/\s/g, '');
}

function collectEqualContext(ops: DiffOp[], opIdx: number, direction: 'before' | 'after', maxLen = 40): string {
  let text = '';
  if (direction === 'before') {
    for (let i = opIdx - 1; i >= 0 && text.length < maxLen; i--) {
      const op = ops[i];
      if (!op || op.op !== 0) continue;
      text = normalizeDiffText(op.text) + text;
    }
    return text.slice(-maxLen);
  }

  for (let i = opIdx + 1; i < ops.length && text.length < maxLen; i++) {
    const op = ops[i];
    if (!op || op.op !== 0) continue;
    text += normalizeDiffText(op.text);
  }
  return text.slice(0, maxLen);
}

function pickDeletionContextText(after: string, before: string): { text: string; anchor: 'after' | 'before' } | null {
  if (after) {
    const slashIdx = after.indexOf('/');
    if (slashIdx >= 0 && slashIdx <= 2 && slashIdx + 2 <= after.length) {
      return { text: after.slice(0, slashIdx + 2), anchor: 'after' };
    }
    return { text: after.slice(0, Math.min(4, after.length)), anchor: 'after' };
  }
  if (before) {
    return { text: before.slice(-Math.min(4, before.length)), anchor: 'before' };
  }
  return null;
}

function suffixMatchLength(text: string, suffix: string): number {
  const max = Math.min(text.length, suffix.length);
  for (let len = max; len > 0; len--) {
    if (text.slice(text.length - len) === suffix.slice(suffix.length - len)) {
      return len;
    }
  }
  return 0;
}

function prefixMatchLength(text: string, prefix: string): number {
  const max = Math.min(text.length, prefix.length);
  for (let len = max; len > 0; len--) {
    if (text.slice(0, len) === prefix.slice(0, len)) {
      return len;
    }
  }
  return 0;
}

function findBestContextRange(
  normalizedText: string,
  target: string,
  before: string,
  after: string,
): SegmentMatch | null {
  if (!target) return null;

  let best: { start: number; score: number } | null = null;
  let searchFrom = 0;

  while (searchFrom < normalizedText.length) {
    const idx = normalizedText.indexOf(target, searchFrom);
    if (idx === -1) break;

    const left = normalizedText.slice(Math.max(0, idx - before.length), idx);
    const right = normalizedText.slice(idx + target.length, idx + target.length + after.length);
    const score = suffixMatchLength(left, before) + prefixMatchLength(right, after);

    if (!best || score > best.score) {
      best = { start: idx, score };
    }

    searchFrom = idx + 1;
  }

  if (!best) return null;
  return { start: best.start, end: best.start + target.length };
}

function locateDiffOpRange(ops: DiffOp[], opIdx: number, normalizedText: string): SegmentMatch | null {
  const op = ops[opIdx];
  if (!op) return null;

  const target = normalizeDiffText(op.text);
  if (!target) return null;

  const before = collectEqualContext(ops, opIdx, 'before', 80);
  const after = collectEqualContext(ops, opIdx, 'after', 80);
  return findBestContextRange(normalizedText, target, before, after);
}

function locateDeletionContextRange(ops: DiffOp[], normalizedText: string): SegmentMatch | null {
  for (let opIdx = 0; opIdx < ops.length; opIdx++) {
    const op = ops[opIdx];
    if (!op || op.op !== -1 || !normalizeDiffText(op.text)) continue;

    const before = collectEqualContext(ops, opIdx, 'before');
    const after = collectEqualContext(ops, opIdx, 'after');
    const picked = pickDeletionContextText(after, before);
    if (!picked) continue;

    const beforeForTarget = picked.anchor === 'after'
      ? before
      : before.slice(0, Math.max(0, before.length - picked.text.length));
    const afterForTarget = picked.anchor === 'after'
      ? after.slice(picked.text.length)
      : after;

    const range = findBestContextRange(
      normalizedText,
      picked.text,
      beforeForTarget,
      afterForTarget,
    );
    if (range) return range;
  }
  return null;
}

function findSegmentMatches(
  segments: DiffOp[],
  allOps: DiffOp[],
  normalizedText: string,
  offsetKey: 'offsetA' | 'offsetB',
): SegmentMatch[] {
  const matches: SegmentMatch[] = [];

  for (let segI = 0; segI < segments.length; segI++) {
    const seg = segments[segI];
    const segNorm = seg.text.replace(/\s/g, '');
    if (!segNorm) continue;

    const expectedOffset: number = (seg as any)[offsetKey] ?? 0;

    // Find this segment's position in allOps for context window
    let opIdx = -1;
    for (let k = 0; k < allOps.length; k++) {
      if (allOps[k] === seg) { opIdx = k; break; }
    }

    const windowStart = Math.max(0, opIdx - 3);
    const windowEnd = Math.min(allOps.length - 1, opIdx + 3);

    let contextStr = '';
    let segStartInContext = -1;
    for (let k = windowStart; k <= windowEnd; k++) {
      const opText = allOps[k].text ? allOps[k].text.replace(/\s/g, '') : '';
      if (!opText) continue;
      if (k === opIdx) {
        segStartInContext = contextStr.length;
      }
      contextStr += opText;
    }
    const segEndInContext = segStartInContext === -1 ? -1 : segStartInContext + segNorm.length;

    if (segStartInContext === -1 || contextStr.length === 0) {
      const idx = normalizedText.indexOf(segNorm, Math.max(0, expectedOffset - 20));
      if (idx !== -1) {
        matches.push({ start: idx, end: idx + segNorm.length });
      }
      continue;
    }

    let bestIdx = -1;
    let bestDist = Infinity;
    let searchFrom = 0;
    while (searchFrom < normalizedText.length) {
      const idx = normalizedText.indexOf(contextStr, searchFrom);
      if (idx === -1) break;
      const segActualPos = idx + segStartInContext;
      const dist = Math.abs(segActualPos - expectedOffset);
      if (dist < bestDist) {
        bestDist = dist;
        bestIdx = segActualPos;
      }
      searchFrom = idx + 1;
    }

    if (bestIdx === -1) {
      const idx = normalizedText.indexOf(segNorm, Math.max(0, expectedOffset - 20));
      if (idx !== -1) {
        bestIdx = idx;
      }
    }

    if (bestIdx !== -1) {
      matches.push({ start: bestIdx, end: bestIdx + segNorm.length });
    }
  }

  return matches;
}

// Check if a text node is inside a non-content element (style, script, header, footer)
function isInsideNonContentElement(node: Node, container: HTMLElement): boolean {
  let el = node.parentElement;
  while (el && el !== container) {
    const tag = el.tagName.toUpperCase();
    if (tag === 'STYLE' || tag === 'SCRIPT' || tag === 'HEADER' || tag === 'FOOTER') return true;
    const cls = el.getAttribute('class') || '';
    if (/(?:^|\s)(?:\w*-)?header(?:\s|$)/i.test(cls) || /(?:^|\s)(?:\w*-)?footer(?:\s|$)/i.test(cls)) return true;
    el = el.parentElement;
  }
  return false;
}

// Highlight diffs by building a full DOM text index and directly locating diff segments
function highlightSide(container: HTMLElement, sections: SectionItem[], side: 'a' | 'b') {
  // Collect text nodes, skipping non-content elements (style, script, header, footer)
  const allTextNodes = collectTextNodes(container);
  const textNodes = allTextNodes.filter(n => !isInsideNonContentElement(n, container));
  if (textNodes.length === 0) return;

  // Build full normalized text → (nodeIndex, charOffset) mapping
  let fullText = '';
  const charMap: { nodeIdx: number; charOffset: number }[] = [];
  for (let ni = 0; ni < textNodes.length; ni++) {
    const text = textNodes[ni].textContent!;
    for (let c = 0; c < text.length; c++) {
      if (/\s/.test(text[c])) continue;
      charMap.push({ nodeIdx: ni, charOffset: c });
      fullText += text[c];
    }
  }

  const targetOp = side === 'a' ? -1 : 1;
  const cssClass = side === 'a' ? 'diff-del-highlight' : 'diff-ins-highlight';

  const allModifiedSections = sections.filter(
    s => s.diff_type === 'modified' && s.diff_ops_json,
  );

  console.log('[DocxDiff] highlightSide', side,
    'allTextNodes:', allTextNodes.length, 'bodyTextNodes:', textNodes.length,
    'normalizedText length:', fullText.length);

  // Collect all char ranges to highlight across all sections, tagged with section ID
  const allRanges: { start: number; end: number; sectionId: number }[] = [];
  const inlineContextSections = new Set<number>();

  for (const section of allModifiedSections) {
    const allOps = parseDiffOps(section.diff_ops_json);
    const targetSegments = allOps.filter(d => d.op === targetOp && d.text?.trim());
    if (targetSegments.length === 0) {
      if (side === 'b') {
        const contextRange = locateDeletionContextRange(allOps, fullText);
        if (contextRange) {
          allRanges.push({ ...contextRange, sectionId: section.id });
          inlineContextSections.add(section.id);
        }
      }
      continue;
    }

    // Find this section's position in the DOM text using the section anchor
    // (title for headings, first line for body/table) — NOT the full text_content
    // which includes children and isn't contiguous in the rendered DOM.
    const sectionNorm = (section.text_content || '').replace(/\s/g, '');
    const sectionAnchor = getSectionAnchor(section, getParentText(section));
    const sectionDomStart = findBlockByAnchor(container, fullText, sectionAnchor, section);
    console.log('[DocxDiff] section', section.id, 'role:', section.role, 'title:', section.title,
      'anchor:', sectionAnchor.substring(0, 20), 'sectionDomStart:', sectionDomStart);

    for (const seg of targetSegments) {
      const segNorm = seg.text.replace(/\s/g, '');
      if (!segNorm) continue;

      const opIdx = allOps.indexOf(seg);

      // Strategy 1: Context-scored match scoped to section range.
      // Validate against expected offset to reject false matches at wrong positions
      // (e.g. "151" matching at (续) heading instead of first page).
      let contextMatch: SegmentMatch | null = null;
      if (sectionDomStart >= 0) {
        const scopedEnd = Math.min(fullText.length, sectionDomStart + sectionNorm.length + 100);
        const scopedText = fullText.substring(sectionDomStart, scopedEnd);
        const scopedMatch = locateDiffOpRange(allOps, opIdx, scopedText);
        if (scopedMatch) {
          const offsetKey = side === 'a' ? 'offsetA' : 'offsetB';
          const expectedOffset = (seg as any)[offsetKey] ?? 0;
          const matchedOffset = scopedMatch.start;
          // Accept only if within 50 chars of expected offset (allows for minor rendering diffs)
          if (Math.abs(matchedOffset - expectedOffset) <= 50) {
            contextMatch = { start: scopedMatch.start + sectionDomStart, end: scopedMatch.end + sectionDomStart };
          } else {
            console.log('[DocxDiff] context match rejected: offset', matchedOffset, 'vs expected', expectedOffset);
          }
        }
      }

      if (contextMatch) {
        console.log('[DocxDiff] context scored match:', segNorm.substring(0, 20), 'at', contextMatch.start);
        allRanges.push({ ...contextMatch, sectionId: section.id });
        continue;
      }

      const offsetKey = side === 'a' ? 'offsetA' : 'offsetB';
      const rawOffset = (seg as any)[offsetKey] ?? 0;

      // Strategy 1: Direct offset mapping (offsetA/offsetB relative to section start)
      if (sectionDomStart >= 0 && sectionNorm.length > 0) {
        const domPos = sectionDomStart + rawOffset;
        // Verify: the text at this position should match the segment text
        if (domPos >= 0 && domPos + segNorm.length <= fullText.length) {
          const domText = fullText.substring(domPos, domPos + segNorm.length);
          if (domText === segNorm) {
            console.log('[DocxDiff] direct offset match:', segNorm.substring(0, 20), 'at', domPos);
            allRanges.push({ start: domPos, end: domPos + segNorm.length, sectionId: section.id });
            continue;
          }
          // Try nearby positions (offset might be slightly off due to rendering differences)
          for (let delta = -5; delta <= 5; delta++) {
            const tryPos = domPos + delta;
            if (tryPos < 0 || tryPos + segNorm.length > fullText.length) continue;
            if (fullText.substring(tryPos, tryPos + segNorm.length) === segNorm) {
              console.log('[DocxDiff] offset match with delta', delta, ':', segNorm.substring(0, 20), 'at', tryPos);
              allRanges.push({ start: tryPos, end: tryPos + segNorm.length, sectionId: section.id });
              break;
            }
          }
          if (allRanges.length > 0 && allRanges[allRanges.length - 1].sectionId === section.id) continue;
        }
      }

      // Strategy 2: Search within section range only
      if (sectionDomStart >= 0) {
        const sectionDomEnd = Math.min(fullText.length, sectionDomStart + sectionNorm.length + 100);
        const sectionRange = fullText.substring(sectionDomStart, sectionDomEnd);
        const localIdx = sectionRange.indexOf(segNorm);
        if (localIdx !== -1) {
          const globalIdx = sectionDomStart + localIdx;
          console.log('[DocxDiff] section-range match:', segNorm.substring(0, 20), 'at', globalIdx);
          allRanges.push({ start: globalIdx, end: globalIdx + segNorm.length, sectionId: section.id });
          continue;
        }
      }

      // Strategy 3: Global fallback (least accurate)
      // Skip when the section text doesn't exist in this DOM — otherwise
      // a random substring match can place a highlight (and scroll target)
      // in completely the wrong location (e.g. deleted tables in doc A
      // accidentally matching unrelated text in doc B).
      if (sectionDomStart < 0) continue;
      const idx = fullText.indexOf(segNorm);
      if (idx !== -1) {
        console.log('[DocxDiff] global fallback match:', segNorm.substring(0, 20), 'at', idx);
        allRanges.push({ start: idx, end: idx + segNorm.length, sectionId: section.id });
      }
    }
  }

  // Apply text-level highlights (only if there are ranges)
  if (allRanges.length > 0) {
    console.log('[DocxDiff] highlightSide', side, '- matched', allRanges.length, 'ranges');

    const nodeHighlightRanges = new Map<number, { range: [number, number]; sectionId: number }[]>();
    for (const range of allRanges) {
      for (let c = range.start; c < range.end && c < charMap.length; c++) {
        const entry = charMap[c];
        if (!entry) continue;
        if (!nodeHighlightRanges.has(entry.nodeIdx)) {
          nodeHighlightRanges.set(entry.nodeIdx, []);
        }
        const ranges = nodeHighlightRanges.get(entry.nodeIdx)!;
        const last = ranges[ranges.length - 1];
        if (last && entry.charOffset <= last.range[1] + 1 && last.sectionId === range.sectionId) {
          last.range[1] = Math.max(last.range[1], entry.charOffset);
        } else {
          ranges.push({ range: [entry.charOffset, entry.charOffset], sectionId: range.sectionId });
        }
      }
    }

    // Apply: build replacement DOM for each text node from its original content and all ranges at once
    const sortedNodes = Array.from(nodeHighlightRanges.entries()).sort((a, b) => a[0] - b[0]);
    for (const [nodeIdx, rangeEntries] of sortedNodes) {
      const textNode = textNodes[nodeIdx];
      if (!textNode || !textNode.textContent || !textNode.parentNode) continue;

      const originalText = textNode.textContent;
      const parent = textNode.parentNode;
      const fragment = document.createDocumentFragment();

      const sortedRanges = rangeEntries.map(e => ({ ...e })).sort((a, b) => a.range[0] - b.range[0]);
      let pos = 0;

      for (const { range: [start, end], sectionId } of sortedRanges) {
        if (start > pos) {
          fragment.appendChild(document.createTextNode(originalText.substring(pos, start)));
        }
        const span = document.createElement('span');
        span.className = cssClass;
        span.setAttribute('data-section-id', String(sectionId));
        span.textContent = originalText.substring(start, end + 1);
        fragment.appendChild(span);
        pos = end + 1;
      }

      if (pos < originalText.length) {
        fragment.appendChild(document.createTextNode(originalText.substring(pos)));
      }

      parent.replaceChild(fragment, textNode);
    }
  }

  // For side B: mark block-level elements for deletion-only sections (no INSERT ops)
  // This provides a visual indicator where text was removed, using offset positioning
  if (side === 'b') {
    const deletionOnlySections = allModifiedSections.filter(s => {
      const ops = parseDiffOps(s.diff_ops_json);
      const hasDel = ops.some(d => d.op === -1 && d.text?.trim());
      const hasIns = ops.some(d => d.op === 1 && d.text?.trim());
      return hasDel && !hasIns;
    });

    if (deletionOnlySections.length > 0) {
      console.log('[DocxDiff] marking', deletionOnlySections.length, 'deletion-only sections on side B');
      for (const section of deletionOnlySections) {
        if (inlineContextSections.has(section.id)) continue;
        const ops = parseDiffOps(section.diff_ops_json);
        const sectionNorm = (section.text_content || '').replace(/\s/g, '');
        if (sectionNorm.length < 5) continue;

        // Find section start in DOM text using anchor (title or first line)
        const sectionAnchor = getSectionAnchor(section, getParentText(section));
        const sectionDomStart = findBlockByAnchor(container, fullText, sectionAnchor, section);
        if (sectionDomStart === -1) continue;

        // Use offsetB from first non-equal op to find diff position
        // For deletion-only sections, offsetB may point past section text in B, so clamp
        let diffOffset = 0;
        for (const op of ops) {
          if (op.op !== 0 && op.offsetB !== undefined) {
            diffOffset = op.offsetB;
            break;
          }
        }

        const sectionEnd = Math.min(sectionDomStart + sectionNorm.length, charMap.length) - 1;
        const targetIdx = Math.min(Math.max(sectionDomStart, sectionDomStart + diffOffset), sectionEnd);
        if (targetIdx < 0 || targetIdx >= charMap.length) continue;

        const entry = charMap[targetIdx];
        if (!entry) continue;

        // Find block-level element at this position
        const blockEl = getElementAtCharIndexFromNodes(textNodes, entry.nodeIdx);
        if (blockEl) {
          blockEl.classList.add('diff-del-context');
          blockEl.setAttribute('data-section-id', String(section.id));
          console.log('[DocxDiff] marked deletion context for section', section.id, 'at', blockEl.tagName);
        }
      }
    }
  }

  if (allRanges.length === 0) {
    console.warn('[DocxDiff] highlightSide', side, '- no ranges matched');
  }
}

// Find block-level element from a text node index
function getElementAtCharIndexFromNodes(textNodes: Text[], nodeIdx: number): HTMLElement | null {
  const textNode = textNodes[nodeIdx];
  if (!textNode?.parentElement) return null;
  let blockEl: HTMLElement | null = textNode.parentElement;
  for (let i = 0; i < 5 && blockEl; i++) {
    const display = getComputedStyle(blockEl).display;
    if (display === 'block' || display === 'flex' || display.startsWith('table')) break;
    blockEl = blockEl.parentElement;
  }
  return (blockEl || textNode.parentElement) as HTMLElement;
}

async function render() {
  if (!containerA.value || !containerB.value) return;
  loading.value = true;
  try {
    await Promise.all([
      loadDocx('a', containerA.value),
      loadDocx('b', containerB.value),
    ]);

    // Apply highlights after rendering. Modified/deleted sections are carried by A;
    // added sections are carried by B so newly inserted DOCX blocks are visible.
    await nextTick();
    const diffCarrierSections = [
      ...props.sectionsA.filter(s => s.diff_type && s.diff_type !== 'equal' && s.diff_type !== 'added'),
      ...props.sectionsB.filter(s => s.diff_type === 'added'),
    ];
    highlightSide(containerA.value!, diffCarrierSections, 'a');
    highlightSide(containerB.value!, diffCarrierSections, 'b');
  } catch (e) {
    console.error('Failed to render DOCX:', e);
  }
  loading.value = false;
}

// Helper: build text index for a container (body text nodes only)
function buildBodyTextIndex(container: HTMLElement): {
  fullText: string;
  charNodeMap: { node: Text; offset: number }[];
} {
  const textNodes = collectTextNodes(container);
  const bodyNodes = textNodes.filter(n => !isInsideNonContentElement(n, container));
  let fullText = '';
  const charNodeMap: { node: Text; offset: number }[] = [];
  for (const node of bodyNodes) {
    const t = node.textContent!.replace(/\s/g, '');
    for (let i = 0; i < t.length; i++) {
      charNodeMap.push({ node, offset: i });
    }
    fullText += t;
  }
  return { fullText, charNodeMap };
}

// Find section start in DOM text, return the char index
function findSectionStartInText(fullText: string, sectionNorm: string): number {
  const keys = [
    sectionNorm.substring(0, Math.min(40, sectionNorm.length)),
    sectionNorm.substring(0, Math.min(20, sectionNorm.length)),
    sectionNorm.substring(0, Math.min(10, sectionNorm.length)),
  ];
  if (sectionNorm.length > 20) {
    keys.push(sectionNorm.substring(Math.floor(sectionNorm.length / 2), Math.floor(sectionNorm.length / 2) + 20));
  }
  for (const key of keys) {
    if (key.length < 5) continue;
    const idx = fullText.indexOf(key);
    if (idx !== -1) return idx;
  }
  return -1;
}

// Get the parent section's text for a given section (from A-side data).
function getParentText(section: { parent_id: number | null }): string {
  if (!section.parent_id) return '';
  const parent = props.sectionsA.find(s => s.id === section.parent_id);
  return parent?.text_content || '';
}

// Extract the DOM-searchable anchor from a section.
// For headings, use the title. For body/table sections (no title),
// prepend the parent heading text to make the anchor unique — many
// tables share similar header rows (e.g. "附注 2024年 2023年").
function getSectionAnchor(
  section: { title: string; text_content: string; parent_id: number | null },
  parentText?: string,
): string {
  if (section.title) {
    return (section.title || '').replace(/\s/g, '');
  }
  const firstLine = (section.text_content || '').split('\n')[0] || '';
  const lineNorm = firstLine.replace(/\s/g, '');
  if (!lineNorm) return '';
  // Prepend parent heading (first ~20 chars) for uniqueness
  if (parentText) {
    const pNorm = parentText.replace(/\s/g, '').substring(0, 20);
    if (pNorm) return pNorm + lineNorm;
  }
  return lineNorm;
}

// Find section anchor by matching block-level elements in DOM order.
// This avoids false matches from unrelated sections (e.g. audit report
// referencing "合并股东权益变动表" in body text matching the heading).
function findSectionAnchorInText(fullText: string, anchor: string): number {
  if (anchor.length < 3) return -1;
  // Fallback: search in flat text (used by scrollToSection for char-index computation)
  const keys = [
    anchor.substring(0, Math.min(40, anchor.length)),
    anchor.substring(0, Math.min(20, anchor.length)),
    anchor.substring(0, Math.min(10, anchor.length)),
  ];
  for (const key of keys) {
    if (key.length < 3) continue;
    const idx = fullText.indexOf(key);
    if (idx !== -1) return idx;
  }
  return -1;
}

// Find the block-level element matching the section anchor.
// For heading sections: match block that starts with the title.
// For body/table sections: match the parent heading block (anchor = parentHeading + firstLine,
// but heading and table are in different blocks, so only match the parentHeading part).
// When nearTarget is provided, returns the MATCHING block closest to that position
// (handles multi-page sections with repeated headings like "(续)").
// Returns the char index in fullText, or -1.
function findBlockByAnchor(
  container: HTMLElement,
  fullText: string,
  anchor: string,
  section: { title: string },
  nearTarget?: number,
): number {
  if (anchor.length < 3) return -1;
  const key = anchor.substring(0, Math.min(20, anchor.length));
  if (key.length < 3) return -1;

  // For non-heading sections, also extract just the parent heading part
  const headingKey = !section.title && anchor.length > 20
    ? anchor.substring(0, 20)
    : null;

  const blocks = container.querySelectorAll('p, h1, h2, h3, h4, h5, h6, li, td, th, div, caption');

  let bestIdx = -1;
  let bestDist = Infinity;
  const hasTarget = nearTarget !== undefined && nearTarget >= 0;

  for (const block of Array.from(blocks)) {
    if (!(block as HTMLElement).innerText) continue;
    const blockNorm = (block as HTMLElement).innerText.replace(/\s/g, '');
    if (blockNorm.length < 3) continue;

    if (blockNorm.startsWith(key) || (headingKey && blockNorm.startsWith(headingKey))) {
      const idx = fullText.indexOf(blockNorm.substring(0, Math.min(10, blockNorm.length)));
      if (idx === -1) continue;

      if (!hasTarget) return idx; // No target — return first match

      const dist = Math.abs(idx - nearTarget!);
      if (dist < bestDist) {
        bestDist = dist;
        bestIdx = idx;
      }
    }
  }
  return bestIdx;
}

// Walk up the ancestor chain to find a scrollable position in the DOM.
// Used when the section's own text can't be found (e.g. deleted tables).
function scrollToAncestor(
  el: HTMLElement,
  section: { parent_id: number | null; doc_type?: 'a' | 'b'; order_index: number },
  label: string,
): boolean {
  const ancestorChain: { id: number; text_content: string }[] = [];
  const lookupSections = label === 'A' ? props.sectionsA : props.sectionsB;
  let curPid = section.parent_id;
  for (let depth = 0; depth < 5 && curPid; depth++) {
    const ancA = props.sectionsA.find(s => s.id === curPid);
    if (!ancA) break;
    const ancForDom = label === 'B'
      ? lookupSections.find(s => (s.text_content || '').replace(/\s/g, '').substring(0, 20) === (ancA.text_content || '').replace(/\s/g, '').substring(0, 20))
      : ancA;
    ancestorChain.push({ id: ancForDom?.id ?? ancA.id, text_content: ancA.text_content });
    curPid = ancA.parent_id;
  }

  let cachedFullText: string | null = null;
  let cachedCharNodeMap: any = null;

  for (const anc of ancestorChain) {
    const marker = el.querySelector(`[data-section-id="${anc.id}"]`) as HTMLElement | null;
    if (marker) {
      console.log('[DocxDiff] scroll', label, 'ancestor DOM marker, ancId:', anc.id);
      scrollToElement(el, marker);
      return true;
    }
    const ancNorm = (anc.text_content || '').replace(/\s/g, '');
    if (ancNorm.length < 5) continue;
    if (!cachedFullText) {
      const idx = buildBodyTextIndex(el);
      cachedFullText = idx.fullText;
      cachedCharNodeMap = idx.charNodeMap;
    }
    const keys = [
      ancNorm.substring(0, Math.min(40, ancNorm.length)),
      ancNorm.substring(0, Math.min(20, ancNorm.length)),
    ];
    let found = -1;
    for (const key of keys) {
      if (key.length < 5) continue;
      found = cachedFullText!.indexOf(key);
      if (found !== -1) break;
    }
    if (found !== -1) {
      const target = getElementAtCharIndex(cachedCharNodeMap, found);
      if (target) {
        console.log('[DocxDiff] scroll', label, 'ancestor text at', found, 'ancId:', anc.id);
        scrollToElement(el, target);
        return true;
      }
    }
  }

  // Last resort: order_index ratio
  const allSections = section.doc_type === 'b' ? props.sectionsB : props.sectionsA;
  const maxOrder = Math.max(...allSections.map(s => s.order_index), 1);
  const ratio = section.order_index / maxOrder;
  const targetY = el.scrollHeight * Math.min(ratio, 0.98);
  console.log('[DocxDiff] scroll', label, 'fallback order_index ratio:', ratio.toFixed(3));
  el.scrollTo({ top: Math.max(0, targetY - el.clientHeight / 3), behavior: 'smooth' });
  return true;
}

// Get the block-level element at a character index in the text index
function getElementAtCharIndex(charNodeMap: { node: Text; offset: number }[], idx: number): HTMLElement | null {
  const entry = charNodeMap[idx];
  if (!entry?.node.parentElement) return null;
  let blockEl: HTMLElement | null = entry.node.parentElement;
  for (let i = 0; i < 5 && blockEl; i++) {
    const display = getComputedStyle(blockEl).display;
    if (display === 'block' || display === 'flex' || display.startsWith('table')) break;
    blockEl = blockEl.parentElement;
  }
  return (blockEl || entry.node.parentElement) as HTMLElement;
}

function scrollToElement(container: HTMLElement, target: HTMLElement) {
  const containerRect = container.getBoundingClientRect();
  const targetRect = target.getBoundingClientRect();
  const scrollTop = container.scrollTop + targetRect.top - containerRect.top - containerRect.height / 3;
  container.scrollTo({ top: Math.max(0, scrollTop), behavior: 'smooth' });
  target.classList.add('section-scroll-target');
  setTimeout(() => target.classList.remove('section-scroll-target'), 2000);
}

// Scroll to a section's diff position in the rendered DOM
function scrollToSection(section: { id: number; title: string; diff_type: string; diff_ops_json: string | null; text_content: string; doc_type?: 'a' | 'b' }) {
  console.log('[DocxDiff] scrollToSection:', section.title, 'id:', section.id, 'doc_type:', section.doc_type, 'diff_type:', section.diff_type);

  // Build container list: prioritize the section's own document side
  const allContainers = [
    { el: containerA.value, cssClass: 'diff-del-highlight', label: 'A' },
    { el: containerB.value, cssClass: 'diff-ins-highlight', label: 'B' },
  ];

  // deleted sections live on A, added sections live on B
  const prioritySide = section.diff_type === 'deleted' ? 'A' : section.diff_type === 'added' ? 'B' : section.doc_type;
  const containers = prioritySide === 'A'
    ? [allContainers[0], allContainers[1]]
    : prioritySide === 'B'
      ? [allContainers[1], allContainers[0]]
      : allContainers;

  // Parse diff ops once to find the offset of the first diff
  const ops = section.diff_ops_json ? parseDiffOps(section.diff_ops_json) : [];

  for (const { el, cssClass, label } of containers) {
    if (!el) continue;

    const sectionNorm = (section.text_content || '').replace(/\s/g, '');
    const { fullText, charNodeMap } = buildBodyTextIndex(el);

    // Strategy 1: offset-based positioning (most reliable — uses section anchor
    // in DOM + diff offset from diff_ops to compute the exact target position)
    let scrolled = false;
    if (sectionNorm.length >= 5) {
      // Deletion-only on side B: use context range
      if (label === 'B' && ops.some(op => op.op === -1) && !ops.some(op => op.op === 1)) {
        const contextRange = locateDeletionContextRange(ops, fullText);
        if (contextRange) {
          const target = getElementAtCharIndex(charNodeMap, contextRange.start);
          if (target) {
            console.log('[DocxDiff] scroll', label, 'via deletion context range');
            scrollToElement(el, target);
            scrolled = true;
          }
        }
      }

      if (!scrolled) {
        const sectionAnchor = getSectionAnchor(section, getParentText(section));
        let diffOffset = 0;
        const offsetKey = label === 'A' ? 'offsetA' : 'offsetB';
        for (const op of ops) {
          if (op.op !== 0) {
            diffOffset = (op as any)[offsetKey] ?? 0;
            break;
          }
        }

        const sectionStart = findBlockByAnchor(el, fullText, sectionAnchor, section, diffOffset);
        if (sectionStart !== -1) {
          const sectionEnd = Math.min(sectionStart + sectionNorm.length, charNodeMap.length) - 1;
          const targetIdx = Math.min(Math.max(sectionStart, sectionStart + diffOffset), sectionEnd);
          const target = getElementAtCharIndex(charNodeMap, targetIdx);
          if (target) {
            console.log('[DocxDiff] scroll', label, 'via offset: sectionStart:', sectionStart, 'diffOffset:', diffOffset, 'targetIdx:', targetIdx);
            scrollToElement(el, target);
            scrolled = true;
          }
        }
      }
    }

    if (scrolled) continue;

    // Strategy 2: find highlight span for this section (less reliable —
    // highlightSide can misplace spans for short/generic diff text)
    const selector = `.${cssClass}[data-section-id="${section.id}"]`;
    const highlight = el.querySelector(selector) as HTMLElement | null;
    if (highlight) {
      console.log('[DocxDiff] scroll', label, 'via highlight span (fallback)');
      scrollToElement(el, highlight);
      continue;
    }

    // Strategy 2b: for side B, also check deletion context block marker
    if (label === 'B') {
      const contextEl = el.querySelector(`.diff-del-context[data-section-id="${section.id}"]`) as HTMLElement | null;
      if (contextEl) {
        console.log('[DocxDiff] scroll', label, 'via deletion context block');
        scrollToElement(el, contextEl);
        continue;
      }
    }

    // Strategy 3: ancestor chain fallback
    console.log('[DocxDiff] no match in', label, '- using ancestor fallback');
    scrollToAncestor(el, section, label);
  }
}

defineExpose({ scrollToSection });

onMounted(render);

watch(() => props.taskId, render);
</script>

<template>
  <div class="docx-diff-container">
    <!-- Document A -->
    <div class="docx-diff-pane">
      <div class="document-doc-header document-doc-header-original">
        <span class="document-doc-badge document-badge-original">原文档</span>
        <span class="text-xs text-slate-500">{{ fileAName }}</span>
      </div>
      <div ref="containerA" class="docx-diff-content" />
    </div>

    <!-- Document B -->
    <div class="docx-diff-pane">
      <div class="document-doc-header document-doc-header-compare">
        <span class="document-doc-badge document-badge-compare">比对文档</span>
        <span class="text-xs text-slate-500">{{ fileBName }}</span>
      </div>
      <div ref="containerB" class="docx-diff-content" />
    </div>
  </div>

  <!-- Loading overlay -->
  <div v-if="loading" class="docx-diff-loading">
    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500 mx-auto mb-3"></div>
    <p class="text-slate-500 text-sm">正在渲染文档...</p>
  </div>
</template>

