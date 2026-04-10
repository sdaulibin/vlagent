<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { useEditor, EditorContent } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import Highlight from '@tiptap/extension-highlight';
import { Table } from '@tiptap/extension-table';
import { TableRow } from '@tiptap/extension-table-row';
import { TableCell } from '@tiptap/extension-table-cell';
import { TableHeader } from '@tiptap/extension-table-header';

interface Props {
    content: string;
    highlightText?: string;
    compareText?: string;  // 对方的文本，用于找出真正差异
    highlightColor?: string;
}

const props = withDefaults(defineProps<Props>(), {
    highlightText: '',
    compareText: '',
    highlightColor: 'yellow'
});

const editorContainer = ref<HTMLElement | null>(null);

// 创建 Tiptap 编辑器
const editor = useEditor({
    extensions: [
        StarterKit,
        Highlight.configure({
            multicolor: true,
        }),
        Table.configure({
            resizable: false,
        }),
        TableRow,
        TableCell,
        TableHeader,
    ],
    content: '',
    editable: false, // 只读模式
});

// 检测是否是被框起来的段落行 (格式: |text|，只有2个|)
const isBoxedParagraphLine = (line: string): boolean => {
    if (!line.startsWith('|') || !line.endsWith('|')) return false;
    const pipeCount = (line.match(/\|/g) || []).length;
    return pipeCount === 2;
};

// 检测是否是表格行 (有多个单元格)
const isTableRow = (line: string): boolean => {
    // 格式1: col1 | col2 (带空格的管道分隔符)
    if (line.includes(' | ')) {
        return line.split(' | ').length >= 2;
    }
    // 格式2: |col1|col2| (以|包围，至少3个|)
    if (line.startsWith('|') && line.endsWith('|')) {
        const pipeCount = (line.match(/\|/g) || []).length;
        return pipeCount >= 3;
    }
    return false;
};

// 解析表格行
const parseTableRow = (line: string): string[] => {
    // 先移除行首尾的 |
    let cleaned = line.replace(/^\|+/, '').replace(/\|+$/, '').trim();
    
    // 根据分隔符拆分
    let cells: string[];
    if (cleaned.includes(' | ')) {
        cells = cleaned.split(' | ');
    } else {
        cells = cleaned.split('|');
    }
    
    // 清理每个单元格：移除多余的 | 和空白
    return cells
        .map(c => c.replace(/^\|+/, '').replace(/\|+$/, '').trim())
        .filter(c => c && c !== '-' && c !== '--' && c !== '---');
};

// 提取被框起来的内容 (去掉首尾的 |)
const extractBoxedContent = (line: string): string => {
    return line.replace(/^\|/, '').replace(/\|$/, '').trim();
};

// 检测并转换表格格式 (管道分隔格式)
const convertTableFormat = (text: string): string => {
    // 处理字面量 \n (即用户看到的 "\n" 字符)
    const normalizedText = text.replace(/\\n/g, '\n');
    const lines = normalizedText.split('\n');
    const result: string[] = [];
    let inTable = false;
    let tableRows: string[][] = [];
    let inBoxedParagraph = false;
    let boxedContent: string[] = [];
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i]?.trim() || '';
        
        if (isBoxedParagraphLine(line)) {
            // 先结束表格
            if (inTable && tableRows.length > 0) {
                result.push(buildTableHtml(tableRows));
                tableRows = [];
                inTable = false;
            }
            // 收集被框起来的段落内容
            inBoxedParagraph = true;
            boxedContent.push(extractBoxedContent(line));
        } else if (isTableRow(line)) {
            // 先结束被框起来的段落  
            if (inBoxedParagraph && boxedContent.length > 0) {
                const mergedText = boxedContent.join('');
                const escaped = mergedText.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                result.push(`<div class="boxed-paragraph"><p>${escaped}</p></div>`);
                boxedContent = [];
                inBoxedParagraph = false;
            }
            
            if (!inTable) {
                inTable = true;
                tableRows = [];
            }
            // 解析表格行
            const cells = parseTableRow(line);
            if (cells.length > 0) {
                tableRows.push(cells);
            }
        } else {
            // 空行处理：如果在表格中，跳过空行继续表格
            if (!line && inTable) {
                continue;
            }
            
            // 结束表格
            if (inTable && tableRows.length > 0) {
                result.push(buildTableHtml(tableRows));
                tableRows = [];
                inTable = false;
            }
            
            // 结束被框起来的段落
            if (inBoxedParagraph && boxedContent.length > 0) {
                const mergedText = boxedContent.join('');
                const escaped = mergedText.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                result.push(`<div class="boxed-paragraph"><p>${escaped}</p></div>`);
                boxedContent = [];
                inBoxedParagraph = false;
            }
            
            // 普通行
            if (line) {
                const escapedLine = line
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;');
                result.push(`<p>${escapedLine}</p>`);
            }
        }
    }
    
    // 处理末尾的表格
    if (inTable && tableRows.length > 0) {
        result.push(buildTableHtml(tableRows));
    }
    
    // 处理末尾的被框起来的段落
    if (inBoxedParagraph && boxedContent.length > 0) {
        const mergedText = boxedContent.join('');
        const escaped = mergedText.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        result.push(`<div class="boxed-paragraph"><p>${escaped}</p></div>`);
    }
    
    return result.join('');
};

// 构建表格 HTML
const buildTableHtml = (rows: string[][]): string => {
    if (rows.length === 0) return '';
    
    let html = '<table><tbody>';
    rows.forEach((row, rowIndex) => {
        html += '<tr>';
        row.forEach(cell => {
            const tag = rowIndex === 0 ? 'th' : 'td';
            const escapedCell = cell
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
            html += `<${tag}><p>${escapedCell}</p></${tag}>`;
        });
        html += '</tr>';
    });
    html += '</tbody></table>';
    return html;
};

// 转换纯文本为 Tiptap 可用的 HTML
const textToHtml = (text: string): string => {
    if (!text) return '<p></p>';
    return convertTableFormat(text);
};

// 应用高亮
const applyHighlight = () => {
    if (!editor.value) return;
    
    console.log(`[TiptapViewer] applyHighlight called, color=${props.highlightColor}, highlightText="${props.highlightText?.substring(0, 50) || '(empty)'}"`);
    
    // 如果没有高亮文本，设置普通内容
    if (!props.highlightText || !props.highlightText.trim()) {
        editor.value.commands.setContent(textToHtml(props.content));
        console.log(`[TiptapViewer] No highlight text, set plain content`);
        return;
    }
    
    let searchText = props.highlightText.trim();
    
    // 先设置内容
    editor.value.commands.setContent(textToHtml(props.content));
    
    // 使用 Highlight 扩展标记匹配的文本
    nextTick(() => {
        if (!editor.value) return;
        
        const { state } = editor.value;
        const { doc } = state;
        let matches: { from: number; to: number }[] = [];
        let found = false;
        
        // 收集文档中所有文本用于统计
        const allDocText: string[] = [];
        doc.descendants((node) => {
            if (node.isText && node.text) {
                allDocText.push(node.text);
            }
        });
        const fullDocText = allDocText.join(' ');
        
        // 提取关键词并按优先级排序
        const extractKeywords = (text: string): string[] => {
            // 提取各类关键词
            const decimals = text.match(/\d+\.\d+/g) || [];
            const codes = text.match(/[A-Za-z][A-Za-z0-9]{5,}/g) || [];
            const chinese = text.match(/[\u4e00-\u9fa5]{3,}/g) || [];
            const dates = text.match(/\d{2,4}[年月日]/g) || [];
            const integers = text.match(/\d{5,}/g) || [];
            
            // 合并所有关键词
            const all = [...decimals, ...integers, ...codes, ...chinese, ...dates];
            
            // 按长度降序排序（更长的关键词优先）
            all.sort((a, b) => b.length - a.length);
            
            return all;
        };
        
        // 找出两个文本中真正不同的关键词
        const findDifferentKeywords = (textA: string, textB: string): string[] => {
            if (!textB) {
                // 如果没有对比文本，返回所有关键词
                return extractKeywords(textA);
            }
            
            const keywordsA = extractKeywords(textA);
            const keywordsB = extractKeywords(textB);
            
            // 找出只在 textA 中出现的关键词（即真正的差异）
            const uniqueToA = keywordsA.filter(k => !keywordsB.includes(k));
            
            // 如果有唯一关键词，优先使用
            if (uniqueToA.length > 0) {
                console.log(`[TiptapViewer] 找到唯一关键词:`, uniqueToA);
                return uniqueToA;
            }
            
            // 否则过滤掉在文档中出现太多次的关键词
            const filtered = keywordsA.filter(keyword => {
                const count = (fullDocText.match(new RegExp(keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g')) || []).length;
                return count <= 3;
            });
            
            return filtered.length > 0 ? filtered : keywordsA.slice(0, 5);
        };
        
        // 构建忽略空格的正则
        const buildFuzzyRegex = (text: string): RegExp | null => {
            const cleanText = text.replace(/\s+/g, '');
            if (cleanText.length < 2) return null;
            const pattern = cleanText.split('').map(c => {
                return c.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            }).join('\\s*');
            return new RegExp(pattern, 'g');
        };

        // ========== 策略1: 完整文本精确匹配 ==========
        doc.descendants((node, pos) => {
            if (found) return false;
            if (node.isText && node.text) {
                const text = node.text;
                const index = text.indexOf(searchText);
                if (index !== -1) {
                    matches.push({ from: pos + index, to: pos + index + searchText.length });
                    found = true;
                    console.log(`[TiptapViewer] 策略1 精确匹配成功`);
                }
            }
        });

        // ========== 策略2: 移除管道符后匹配（表格行）==========
        if (!found && searchText.includes('|')) {
            const cleanedSearch = searchText.replace(/\|/g, ' ').replace(/\s+/g, ' ').trim();
            doc.descendants((node, pos) => {
                if (found) return false;
                if (node.isText && node.text) {
                    const text = node.text;
                    const index = text.indexOf(cleanedSearch);
                    if (index !== -1) {
                        matches.push({ from: pos + index, to: pos + index + cleanedSearch.length });
                        found = true;
                        console.log(`[TiptapViewer] 策略2 去管道符匹配成功`);
                    }
                }
            });
        }

        // ========== 策略3: 忽略空格的模糊匹配 ==========
        if (!found) {
            const fuzzyRegex = buildFuzzyRegex(searchText);
            if (fuzzyRegex) {
                doc.descendants((node, pos) => {
                    if (found) return false;
                    if (node.isText && node.text) {
                        const text = node.text;
                        fuzzyRegex.lastIndex = 0;
                        const match = fuzzyRegex.exec(text);
                        if (match) {
                            matches.push({ from: pos + match.index, to: pos + match.index + match[0].length });
                            found = true;
                            console.log(`[TiptapViewer] 策略3 模糊匹配成功`);
                        }
                    }
                });
            }
        }
        
        // ========== 策略4: 截断文本匹配 ==========
        if (!found && searchText.length > 20) {
            const variants = [
                searchText.substring(0, 50),
                searchText.substring(0, 30),
                searchText.substring(0, 20),
            ].filter(v => v.length >= 10);

            for (const variant of variants) {
                if (found) break;
                doc.descendants((node, pos) => {
                    if (found) return false;
                    if (node.isText && node.text) {
                        const text = node.text;
                        const index = text.indexOf(variant);
                        if (index !== -1) {
                            matches.push({ from: pos + index, to: pos + index + variant.length });
                            found = true;
                            console.log(`[TiptapViewer] 策略4 截断匹配成功: "${variant.substring(0, 15)}..."`);
                        }
                    }
                });
            }
        }

        // ========== 策略5: 智能关键词匹配（优先唯一关键词）==========
        if (!found) {
            // 使用对比文本找出真正不同的关键词
            const keywords = findDifferentKeywords(searchText, props.compareText || '');
            console.log(`[TiptapViewer] 策略5 尝试关键词:`, keywords.slice(0, 5));
            
            for (const keyword of keywords) {
                if (found) break;
                doc.descendants((node, pos) => {
                    if (found) return false;
                    if (node.isText && node.text) {
                        const text = node.text;
                        const index = text.indexOf(keyword);
                        if (index !== -1) {
                            matches.push({ from: pos + index, to: pos + index + keyword.length });
                            found = true;
                            console.log(`[TiptapViewer] 策略5 关键词匹配成功: "${keyword}"`);
                        }
                    }
                });
            }
        }
        
        console.log(`[TiptapViewer] 最终匹配数: ${matches.length}`);
        
        // 应用高亮
        if (matches.length > 0) {
            const highlightColor = props.highlightColor === 'red' ? '#fecaca' : '#bbf7d0';
            matches.reverse().forEach(match => {
                editor.value!
                    .chain()
                    .setTextSelection(match)
                    .setHighlight({ color: highlightColor })
                    .run();
            });
            
            // 滚动到匹配位置
            const firstMatch = matches[matches.length - 1];
            if (firstMatch) {
                editor.value.commands.setTextSelection(firstMatch.from);
                setTimeout(() => {
                    const markEl = editorContainer.value?.querySelector('mark') as HTMLElement;
                    if (markEl) {
                        markEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                }, 150);
            }
        }
    });
};

// 监听内容变化
watch(() => props.content, () => {
    applyHighlight();
}, { immediate: true });

// 监听高亮文本变化
watch(() => props.highlightText, () => {
    applyHighlight();
});

// 监听高亮颜色变化
watch(() => props.highlightColor, () => {
    applyHighlight();
});

onMounted(() => {
    if (editor.value) {
        applyHighlight();
    }
});

onBeforeUnmount(() => {
    editor.value?.destroy();
});
</script>

<template>
    <div ref="editorContainer" class="tiptap-viewer">
        <EditorContent :editor="editor" />
    </div>
</template>
