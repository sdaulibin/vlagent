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
    highlightColor?: string;
}

const props = withDefaults(defineProps<Props>(), {
    highlightText: '',
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

// 检测并转换表格格式 (管道分隔格式)
const convertTableFormat = (text: string): string => {
    const lines = text.split('\n');
    const result: string[] = [];
    let inTable = false;
    let tableRows: string[][] = [];
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        
        // 检测是否是表格行 (包含 |)
        if (line.includes(' | ') || (line.startsWith('|') && line.endsWith('|'))) {
            if (!inTable) {
                inTable = true;
                tableRows = [];
            }
            // 解析表格行
            const cells = line.split(/\s*\|\s*/).filter(c => c.trim());
            if (cells.length > 0) {
                tableRows.push(cells);
            }
        } else {
            // 结束表格
            if (inTable && tableRows.length > 0) {
                result.push(buildTableHtml(tableRows));
                tableRows = [];
                inTable = false;
            }
            // 普通行
            if (line) {
                const escapedLine = line
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;');
                result.push(`<p>${escapedLine}</p>`);
            } else {
                result.push('<p><br></p>');
            }
        }
    }
    
    // 处理末尾的表格
    if (inTable && tableRows.length > 0) {
        result.push(buildTableHtml(tableRows));
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
        
        // 提取关键词（用于表格匹配）
        const extractKeywords = (text: string): string[] => {
            // 提取数字编码（如 Z7003525000319）
            const codes = text.match(/[A-Za-z0-9]{6,}/g) || [];
            // 提取中文关键词（2字以上）
            const chinese = text.match(/[\u4e00-\u9fa5]{2,}/g) || [];
            return [...codes, ...chinese];
        };
        
        // 尝试不同的搜索策略
        const searchStrategies = [
            // 策略1: 完整文本
            searchText,
            // 策略2: 前50个字符
            searchText.length > 50 ? searchText.substring(0, 50) : null,
            // 策略3: 前30个字符
            searchText.length > 30 ? searchText.substring(0, 30) : null,
            // 策略4: 关键词匹配（用于表格）
            ...extractKeywords(searchText),
        ].filter(Boolean) as string[];
        
        // 尝试每个策略直到找到匹配
        for (const variant of searchStrategies) {
            matches = [];
            doc.descendants((node, pos) => {
                if (node.isText && node.text) {
                    const text = node.text;
                    let index = text.indexOf(variant);
                    while (index !== -1) {
                        matches.push({
                            from: pos + index,
                            to: pos + index + variant.length
                        });
                        index = text.indexOf(variant, index + 1);
                    }
                }
            });
            
            if (matches.length > 0) {
                console.log(`[TiptapViewer] 使用策略 "${variant.substring(0, 20)}..." 找到 ${matches.length} 个匹配`);
                break;
            }
        }
        
        console.log(`[TiptapViewer] 最终匹配数: ${matches.length}, 搜索: "${searchText.substring(0, 30)}..."`);
        
        // 应用高亮（从后往前，避免位置偏移问题）
        const highlightColor = props.highlightColor === 'red' ? '#fecaca' : '#bbf7d0';
        matches.reverse().forEach(match => {
            editor.value!
                .chain()
                .setTextSelection(match)
                .setHighlight({ color: highlightColor })
                .run();
        });
        
        // 滚动到第一个匹配位置
        if (matches.length > 0) {
            const firstMatch = matches[matches.length - 1]; // 因为已经反转，最后一个是原来的第一个
            if (firstMatch) {
                editor.value.commands.setTextSelection(firstMatch.from);
                
                // 延迟滚动以确保 DOM 更新
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

<style scoped>
.tiptap-viewer {
    height: 100%;
    overflow: auto;
    padding: 24px;
    background: #f8fafc;
}

.tiptap-viewer :deep(.ProseMirror) {
    outline: none;
    background: white;
    padding: 32px 40px;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    min-height: 100%;
    font-size: 14px;
    line-height: 1.8;
    color: #334155;
}

.tiptap-viewer :deep(.ProseMirror p) {
    margin: 0 0 0.5em 0;
}

.tiptap-viewer :deep(.ProseMirror mark) {
    padding: 2px 4px;
    border-radius: 3px;
}

/* 表格样式 */
.tiptap-viewer :deep(.ProseMirror table) {
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
    font-size: 13px;
}

.tiptap-viewer :deep(.ProseMirror th),
.tiptap-viewer :deep(.ProseMirror td) {
    border: 1px solid #e2e8f0;
    padding: 8px 12px;
    text-align: left;
    vertical-align: top;
}

.tiptap-viewer :deep(.ProseMirror th) {
    background: #f1f5f9;
    font-weight: 600;
    color: #475569;
}

.tiptap-viewer :deep(.ProseMirror tr:nth-child(even) td) {
    background: #f8fafc;
}

.tiptap-viewer :deep(.ProseMirror th p),
.tiptap-viewer :deep(.ProseMirror td p) {
    margin: 0;
}
</style>
