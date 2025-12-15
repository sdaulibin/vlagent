<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { useEditor, EditorContent } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import Highlight from '@tiptap/extension-highlight';

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
    ],
    content: '',
    editable: false, // 只读模式
});

// 转换纯文本为 Tiptap 可用的 HTML
const textToHtml = (text: string): string => {
    if (!text) return '<p></p>';
    
    // 将文本按行分割，每行转为一个段落
    const paragraphs = text.split('\n').map(line => {
        const escapedLine = line
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        return `<p>${escapedLine || '<br>'}</p>`;
    });
    
    return paragraphs.join('');
};

// 应用高亮
const applyHighlight = () => {
    if (!editor.value || !props.highlightText) {
        // 如果没有高亮文本，设置普通内容
        if (editor.value) {
            editor.value.commands.setContent(textToHtml(props.content));
        }
        return;
    }
    
    const searchText = props.highlightText.trim();
    if (!searchText) {
        editor.value.commands.setContent(textToHtml(props.content));
        return;
    }
    
    // 先设置内容
    editor.value.commands.setContent(textToHtml(props.content));
    
    // 使用 Highlight 扩展标记匹配的文本
    nextTick(() => {
        if (!editor.value) return;
        
        const { state } = editor.value;
        const { doc } = state;
        const matches: { from: number; to: number }[] = [];
        
        // 搜索所有匹配位置
        doc.descendants((node, pos) => {
            if (node.isText && node.text) {
                const text = node.text;
                let index = text.indexOf(searchText);
                while (index !== -1) {
                    matches.push({
                        from: pos + index,
                        to: pos + index + searchText.length
                    });
                    index = text.indexOf(searchText, index + 1);
                }
            }
        });
        
        // 应用高亮（从后往前，避免位置偏移问题）
        matches.reverse().forEach(match => {
            editor.value!
                .chain()
                .setTextSelection(match)
                .setHighlight({ color: props.highlightColor === 'red' ? '#fecaca' : '#bbf7d0' })
                .run();
        });
        
        if (matches.length > 0) {
            const lastMatch = matches[matches.length - 1]; // 因为已经反转，最后一个是原来的第一个
            if (lastMatch) {
                editor.value.commands.setTextSelection(lastMatch.from);
                
                // 滚动到高亮位置
                nextTick(() => {
                    const highlightEl = editorContainer.value?.querySelector('[data-highlight]') as HTMLElement;
                    if (highlightEl) {
                        highlightEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                });
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

.tiptap-viewer :deep([data-highlight]) {
    padding: 2px 4px;
    border-radius: 3px;
}
</style>
