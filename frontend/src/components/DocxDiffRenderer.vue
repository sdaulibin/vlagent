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

// Apply DOM highlights: split text nodes and wrap highlighted ranges in <span>
function applyDomHighlights(
  container: HTMLElement,
  textNodes: Text[],
  charMap: CharEntry[],
  matches: SegmentMatch[],
  cssClass: string,
) {
  // Collect character positions to highlight, grouped by nodeIdx
  const nodeHighlightChars = new Map<number, number[]>();
  for (const match of matches) {
    for (let c = match.start; c < match.end && c < charMap.length; c++) {
      const entry = charMap[c];
      if (!entry) continue;
      if (!nodeHighlightChars.has(entry.nodeIdx)) {
        nodeHighlightChars.set(entry.nodeIdx, []);
      }
      nodeHighlightChars.get(entry.nodeIdx)!.push(entry.charOffset);
    }
  }

  // For each affected text node, split and wrap contiguous ranges
  // Process left-to-right, progressively splitting the text node
  const nodeEntries = Array.from(nodeHighlightChars.entries()).sort((a, b) => a[0] - b[0]);

  for (const [nodeIdx, chars] of nodeEntries) {
    let textNode = textNodes[nodeIdx];
    if (!textNode || !textNode.textContent || !textNode.parentNode) continue;

    chars.sort((a, b) => a - b);
    const ranges: [number, number][] = [];
    let rs = chars[0]!, re = chars[0]!;
    for (let i = 1; i < chars.length; i++) {
      if (chars[i]! <= re + 1) {
        re = chars[i]!;
      } else {
        ranges.push([rs, re]);
        rs = chars[i]!;
        re = chars[i]!;
      }
    }
    ranges.push([rs, re]);

    for (const [start, end] of ranges) {
      if (!textNode.parentNode) break;

      const remaining = textNode.textContent;
      const highlightText = remaining.substring(start, end + 1);
      if (!highlightText) continue;

      const matchIdx = remaining.indexOf(highlightText);
      if (matchIdx === -1) continue;

      const beforeText = remaining.substring(0, matchIdx);
      const afterText = remaining.substring(matchIdx + highlightText.length);
      const parent = textNode.parentNode;

      const span = document.createElement('span');
      span.className = cssClass;
      span.textContent = highlightText;

      if (beforeText) {
        parent.insertBefore(document.createTextNode(beforeText), textNode);
      }
      parent.insertBefore(span, textNode);

      if (afterText) {
        textNode.textContent = afterText;
      } else {
        parent.removeChild(textNode);
        break;
      }
    }
  }
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

  for (const section of allModifiedSections) {
    const allOps = parseDiffOps(section.diff_ops_json);
    const targetSegments = allOps.filter(d => d.op === targetOp && d.text?.trim());
    if (targetSegments.length === 0) continue;

    const sectionNorm = (section.text_content || '').replace(/\s/g, '');

    // Anchor-based section finding: use diff segment context to locate the section
    // in DOM text, then walk backward to find section start. This handles table cells
    // where flatten_section joins cells with spaces, causing offsets to span cell
    // boundaries that don't exist in the docx-preview DOM rendering.
    const offsetKey = side === 'a' ? 'offsetA' : 'offsetB';
    let sectionDomStart = -1;

    if (sectionNorm.length >= 5) {
      // Build anchor candidates from diff segments using context-window matching
      const anchorCandidates: { pos: number; charsBefore: number }[] = [];

      for (const seg of targetSegments) {
        const segNorm = seg.text.replace(/\s/g, '');
        if (segNorm.length < 2) continue;

        const segIdx = allOps.indexOf(seg);
        const winStart = Math.max(0, segIdx - 3);
        const winEnd = Math.min(allOps.length - 1, segIdx + 3);

        let contextStr = '';
        let segStartInCtx = -1;
        for (let k = winStart; k <= winEnd; k++) {
          const opText = allOps[k].text ? allOps[k].text.replace(/\s/g, '') : '';
          if (!opText) continue;
          if (k === segIdx) segStartInCtx = contextStr.length;
          contextStr += opText;
        }

        if (segStartInCtx === -1 || contextStr.length < 6) continue;

        let searchFrom = 0;
        while (searchFrom < fullText.length) {
          const idx = fullText.indexOf(contextStr, searchFrom);
          if (idx === -1) break;
          anchorCandidates.push({ pos: idx + segStartInCtx, charsBefore: (seg as any)[offsetKey] ?? 0 });
          searchFrom = idx + 1;
        }
      }

      // Choose best anchor and walk backward to find section start
      if (anchorCandidates.length > 0) {
        anchorCandidates.sort((a, b) => a.pos - b.pos);
        const anchor = anchorCandidates[0]!;

        // Walk backward from anchor to find section start prefix
        const searchBack = Math.min(anchor.pos, Math.max(sectionNorm.length, anchor.charsBefore) + 50);
        const sectionKey = sectionNorm.substring(0, Math.min(40, sectionNorm.length));

        for (let back = 0; back <= searchBack; back++) {
          const candidateStart = anchor.pos - back;
          if (candidateStart < 0) break;
          if (candidateStart + sectionKey.length > fullText.length) continue;
          if (fullText.substring(candidateStart, candidateStart + sectionKey.length) === sectionKey) {
            sectionDomStart = candidateStart;
            break;
          }
        }
      }

      // Fallback: prefix-based search (original method)
      if (sectionDomStart < 0) {
        const keys = [
          sectionNorm.substring(0, Math.min(40, sectionNorm.length)),
          sectionNorm.substring(0, Math.min(20, sectionNorm.length)),
          sectionNorm.substring(0, Math.min(10, sectionNorm.length)),
        ];
        if (sectionNorm.length > 20) {
          keys.push(sectionNorm.substring(Math.floor(sectionNorm.length / 2), Math.floor(sectionNorm.length / 2) + 20));
          keys.push(sectionNorm.substring(sectionNorm.length - Math.min(30, sectionNorm.length)));
        }
        for (const key of keys) {
          if (key.length < 5) continue;
          const idx = fullText.indexOf(key);
          if (idx !== -1) { sectionDomStart = idx; break; }
        }
      }
    }

    console.log('[DocxDiff] section', section.id, 'role:', section.role, 'title:', section.title,
      'sectionNormLen:', sectionNorm.length, 'sectionDomStart:', sectionDomStart);

    for (const seg of targetSegments) {
      const segNorm = seg.text.replace(/\s/g, '');
      if (!segNorm) continue;

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

    // Apply: process each node's ranges left-to-right, splitting the text node progressively
    const sortedNodes = Array.from(nodeHighlightRanges.entries()).sort((a, b) => a[0] - b[0]);
    for (const [nodeIdx, rangeEntries] of sortedNodes) {
      let textNode = textNodes[nodeIdx];
      if (!textNode || !textNode.textContent || !textNode.parentNode) continue;

      const sortedRanges = rangeEntries.map(e => ({ ...e })).sort((a, b) => a.range[0] - b.range[0]);

      for (const { range: [start, end], sectionId } of sortedRanges) {
        // Node may have been detached from a previous split — skip
        if (!textNode.parentNode) break;

        const remaining = textNode.textContent;
        const highlightText = remaining.substring(start, end + 1);
        if (!highlightText) continue;

        const matchIdx = remaining.indexOf(highlightText);
        if (matchIdx === -1) continue;

        const beforeText = remaining.substring(0, matchIdx);
        const afterText = remaining.substring(matchIdx + highlightText.length);
        const parent = textNode.parentNode;

        const span = document.createElement('span');
        span.className = cssClass;
        span.setAttribute('data-section-id', String(sectionId));
        span.textContent = highlightText;

        if (beforeText) {
          const beforeNode = document.createTextNode(beforeText);
          parent.insertBefore(beforeNode, textNode);
        }
        parent.insertBefore(span, textNode);

        if (afterText) {
          textNode.textContent = afterText;
        } else {
          parent.removeChild(textNode);
          break;
        }
      }
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
        const ops = parseDiffOps(section.diff_ops_json);
        const sectionNorm = (section.text_content || '').replace(/\s/g, '');
        if (sectionNorm.length < 5) continue;

        // Find section start using anchor-based approach
        let sectionDomStart = -1;

        // Build anchor from first non-equal op's context window
        const firstDiff = ops.find(o => o.op !== 0 && o.text?.trim());
        if (firstDiff) {
          const firstDiffIdx = ops.indexOf(firstDiff);
          const winStart = Math.max(0, firstDiffIdx - 3);
          const winEnd = Math.min(ops.length - 1, firstDiffIdx + 3);
          let ctxStr = '';
          let segStartInCtx = -1;
          for (let k = winStart; k <= winEnd; k++) {
            const opText = ops[k]?.text ? ops[k].text.replace(/\s/g, '') : '';
            if (!opText) continue;
            if (k === firstDiffIdx) segStartInCtx = ctxStr.length;
            ctxStr += opText;
          }
          if (segStartInCtx !== -1 && ctxStr.length >= 6) {
            let searchFrom = 0;
            while (searchFrom < fullText.length) {
              const anchorPos = fullText.indexOf(ctxStr, searchFrom);
              if (anchorPos === -1) break;
              const anchorSegPos = anchorPos + segStartInCtx;
              const charsBefore = firstDiff.offsetB ?? 0;
              const searchBack = Math.min(anchorSegPos, Math.max(sectionNorm.length, charsBefore) + 50);
              const sectionKey = sectionNorm.substring(0, Math.min(40, sectionNorm.length));
              for (let back = 0; back <= searchBack; back++) {
                const cs = anchorSegPos - back;
                if (cs < 0) break;
                if (cs + sectionKey.length > fullText.length) continue;
                if (fullText.substring(cs, cs + sectionKey.length) === sectionKey) {
                  sectionDomStart = cs;
                  break;
                }
              }
              if (sectionDomStart >= 0) break;
              searchFrom = anchorPos + 1;
            }
          }
        }

        // Fallback: prefix-based search
        if (sectionDomStart < 0) {
          const keys = [
            sectionNorm.substring(0, Math.min(40, sectionNorm.length)),
            sectionNorm.substring(0, Math.min(20, sectionNorm.length)),
            sectionNorm.substring(0, Math.min(10, sectionNorm.length)),
          ];
          if (sectionNorm.length > 20) {
            keys.push(sectionNorm.substring(Math.floor(sectionNorm.length / 2), Math.floor(sectionNorm.length / 2) + 20));
            keys.push(sectionNorm.substring(sectionNorm.length - Math.min(30, sectionNorm.length)));
          }
          for (const key of keys) {
            if (key.length < 5) continue;
            const idx = fullText.indexOf(key);
            if (idx !== -1) { sectionDomStart = idx; break; }
          }
        }
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

    // Apply highlights after rendering
    // Use sectionsA for both sides since diff_ops_json is only stored on doc_type='a' sections
    await nextTick();
    highlightSide(containerA.value!, props.sectionsA, 'a');
    highlightSide(containerB.value!, props.sectionsA, 'b');
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
function scrollToSection(section: { id: number; title: string; diff_type: string; diff_ops_json: string | null; text_content: string }) {
  console.log('[DocxDiff] scrollToSection:', section.title, 'id:', section.id);

  const containers = [
    { el: containerA.value, cssClass: 'diff-del-highlight', label: 'A' },
    { el: containerB.value, cssClass: 'diff-ins-highlight', label: 'B' },
  ];

  // Parse diff ops once to find the offset of the first diff
  const ops = section.diff_ops_json ? parseDiffOps(section.diff_ops_json) : [];

  for (const { el, cssClass, label } of containers) {
    if (!el) continue;

    // Try 1: find highlight span for this section (INSERT or DELETE highlight)
    const selector = `.${cssClass}[data-section-id="${section.id}"]`;
    const highlight = el.querySelector(selector) as HTMLElement | null;
    if (highlight) {
      console.log('[DocxDiff] scroll', label, 'via highlight span');
      scrollToElement(el, highlight);
      continue;
    }

    // Try 1b: for side B, also check deletion context block marker
    if (label === 'B') {
      const contextEl = el.querySelector(`.diff-del-context[data-section-id="${section.id}"]`) as HTMLElement | null;
      if (contextEl) {
        console.log('[DocxDiff] scroll', label, 'via deletion context block');
        scrollToElement(el, contextEl);
        continue;
      }
    }

    // Try 2: fallback - find diff position using section text + offset from diff_ops
    console.log('[DocxDiff] no highlight in', label, '- falling back to offset-based search');
    const sectionNorm = (section.text_content || '').replace(/\s/g, '');
    if (sectionNorm.length < 5) continue;

    const { fullText, charNodeMap } = buildBodyTextIndex(el);

    // Use anchor-based section finding (same approach as highlightSide)
    const offsetKey = label === 'A' ? 'offsetA' : 'offsetB';
    let sectionStart = -1;

    // Build anchor from first diff op's context window
    const diffOps = ops.filter(o => o.op !== 0 && o.text?.trim());
    if (diffOps.length > 0) {
      const firstDiff = diffOps[0]!;
      const firstDiffIdx = ops.indexOf(firstDiff);
      const winStart = Math.max(0, firstDiffIdx - 3);
      const winEnd = Math.min(ops.length - 1, firstDiffIdx + 3);
      let ctxStr = '';
      let segStartInCtx = -1;
      for (let k = winStart; k <= winEnd; k++) {
        const opText = ops[k]?.text ? ops[k].text.replace(/\s/g, '') : '';
        if (!opText) continue;
        if (k === firstDiffIdx) segStartInCtx = ctxStr.length;
        ctxStr += opText;
      }
      if (segStartInCtx !== -1 && ctxStr.length >= 6) {
        const anchorPos = fullText.indexOf(ctxStr);
        if (anchorPos !== -1) {
          const anchorSegPos = anchorPos + segStartInCtx;
          const charsBefore = (firstDiff as any)[offsetKey] ?? 0;
          const searchBack = Math.min(anchorSegPos, Math.max(sectionNorm.length, charsBefore) + 50);
          const sectionKey = sectionNorm.substring(0, Math.min(40, sectionNorm.length));
          for (let back = 0; back <= searchBack; back++) {
            const cs = anchorSegPos - back;
            if (cs < 0) break;
            if (cs + sectionKey.length > fullText.length) continue;
            if (fullText.substring(cs, cs + sectionKey.length) === sectionKey) {
              sectionStart = cs;
              break;
            }
          }
        }
      }
    }

    // Fallback to prefix search
    if (sectionStart < 0) {
      sectionStart = findSectionStartInText(fullText, sectionNorm);
    }

    if (sectionStart === -1) {
      console.warn('[DocxDiff] section text not found in', label);
      continue;
    }

    // Compute the diff position within the section using offsetA/offsetB
    // For deletion ops on side B (or insertion on side A), offset may point past
    // section text in that doc — clamp to section bounds
    let diffOffset = 0;
    for (const op of ops) {
      if (op.op !== 0) {
        diffOffset = (op as any)[offsetKey] ?? 0;
        break;
      }
    }

    const sectionEnd = Math.min(sectionStart + sectionNorm.length, charNodeMap.length) - 1;
    const targetIdx = Math.min(Math.max(sectionStart, sectionStart + diffOffset), sectionEnd);
    const target = getElementAtCharIndex(charNodeMap, targetIdx);
    if (target) {
      console.log('[DocxDiff] scroll', label, 'sectionStart:', sectionStart, 'diffOffset:', diffOffset, 'targetIdx:', targetIdx);
      scrollToElement(el, target);
    } else {
      console.warn('[DocxDiff] could not locate element in', label);
    }
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

<style>
.docx-diff-container {
  display: flex;
  flex: 1;
  gap: 0;
  overflow: hidden;
}

.docx-diff-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-right: 1px solid #e2e8f0;
}

.docx-diff-pane:last-child {
  border-right: none;
}

.docx-diff-content {
  flex: 1;
  overflow: auto;
  background: #f8fafc;
  padding: 16px;
}

.docx-diff-content .docx-diff-preview {
  margin: 0 auto;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
  border-radius: 2px;
}

.docx-diff-loading {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.8);
  z-index: 20;
}

/* Diff highlight styles - match PDF mode colors */
.diff-del-highlight {
  background-color: rgba(239, 68, 68, 0.35);
  border-radius: 2px;
}

.diff-ins-highlight {
  background-color: rgba(34, 197, 94, 0.35);
  border-radius: 2px;
}

/* Deletion context marker on side B: subtle left border on block element */
.diff-del-context {
  border-left: 3px solid rgba(239, 68, 68, 0.5);
  background-color: rgba(239, 68, 68, 0.06);
  padding-left: 4px;
}

.section-scroll-target {
  outline: 2px solid #f97316;
  outline-offset: 2px;
  border-radius: 2px;
  transition: outline-color 0.5s ease;
}
</style>
