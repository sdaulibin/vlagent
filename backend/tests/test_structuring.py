"""structuring.py 单元测试"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.documents.structuring import (
    InputLine, SectionBlock, StructuredDocument,
    classify_line, build_structured_document, flatten_section, flatten_document,
)


def _line(text, style_hint="", outline_level=None, is_table=False, table_rows=None):
    return InputLine(
        text=text, style_hint=style_hint, outline_level=outline_level,
        is_table=is_table, table_rows=table_rows,
    )


# ---- 分类器测试 ----

class TestClassifyLine:
    def test_blank(self):
        assert classify_line("") == "BLANK"
        assert classify_line("   ") == "BLANK"
        assert classify_line("\t\n") == "BLANK"

    def test_h1_style(self):
        assert classify_line("foo", style_hint="Heading 1") == "H1"
        assert classify_line("foo", style_hint="heading 1") == "H1"

    def test_h2_style(self):
        assert classify_line("bar", style_hint="Heading 2") == "H2"

    def test_h3_style(self):
        assert classify_line("baz", style_hint="Heading 3") == "H3"

    def test_h4_style(self):
        assert classify_line("qux", style_hint="Heading 4") == "H4"

    def test_outline_level(self):
        assert classify_line("x", outline_level=0) == "H1"
        assert classify_line("x", outline_level=1) == "H2"
        assert classify_line("x", outline_level=2) == "H3"
        assert classify_line("x", outline_level=3) == "H4"

    def test_style_overrides_outline(self):
        assert classify_line("x", style_hint="Heading 2", outline_level=0) == "H2"

    def test_h1_regex(self):
        assert classify_line("第一节 总则") == "H1"
        assert classify_line("第三节　股权转让") == "H1"  # 全角空格
        assert classify_line("第十二节 附则") == "H1"

    def test_h2_regex(self):
        assert classify_line("一、总则") == "H2"
        assert classify_line("十二、其他") == "H2"

    def test_h4_regex(self):
        assert classify_line("1. 基本原则") == "H4"
        assert classify_line("12. 注意事项") == "H4"

    def test_h3_regex(self):
        assert classify_line("3.2 标题文本") == "H3"
        assert classify_line("1.1 总则") == "H3"

    def test_h3_unit_prevention(self):
        assert classify_line("3.2 亿元") == "NORMAL"
        assert classify_line("2.1 万美元") == "NORMAL"
        assert classify_line("1.5%") == "NORMAL"

    def test_h3_not_h4(self):
        # "1.1" should be H3 not H4
        assert classify_line("1.1 概述") == "H3"

    def test_toc_title(self):
        assert classify_line("目录") == "TOCTitle"
        assert classify_line("目 录") == "TOCTitle"
        assert classify_line("表 目 录") == "TOCTitle"

    def test_glossary_title(self):
        assert classify_line("附录") == "GlossaryTitle"
        assert classify_line("附 录") == "GlossaryTitle"
        assert classify_line("术语") == "GlossaryTitle"
        assert classify_line("定义") == "GlossaryTitle"

    def test_normal(self):
        assert classify_line("这是一段普通文本") == "NORMAL"
        assert classify_line("增长率3.5%") == "NORMAL"

    def test_table(self):
        assert classify_line("", style_hint="Table") == "Table"


# ---- 状态机测试 ----

class TestStateMachine:
    def test_simple_hierarchy(self):
        lines = [
            _line("第一节 总则"),
            _line("本合同由双方签订。"),
            _line("一、基本条款"),
            _line("条款内容。"),
            _line("1.1 细则"),
            _line("细则内容。"),
            _line("第二节 转让"),
            _line("转让内容。"),
        ]
        doc = build_structured_document(lines)
        flatten_document(doc)

        assert len(doc.main) == 2
        assert doc.main[0].role == "h1"
        assert doc.main[0].title == "第一节 总则"
        assert len(doc.main[0].children) == 1
        assert doc.main[0].children[0].role == "h2"
        assert doc.main[0].children[0].title == "一、基本条款"
        assert len(doc.main[0].children[0].children) == 1
        assert doc.main[0].children[0].children[0].role == "h3"
        assert doc.main[0].children[0].children[0].title == "1.1 细则"
        assert doc.main[1].role == "h1"
        assert doc.main[1].title == "第二节 转让"

    def test_body_without_heading(self):
        lines = [
            _line("没有标题的文本。"),
            _line("更多文本。"),
        ]
        doc = build_structured_document(lines)
        assert len(doc.main) == 1
        assert doc.main[0].role == "body"
        assert len(doc.main[0].content) == 2

    def test_stack_pop_on_lower_level(self):
        lines = [
            _line("第一节"),
            _line("1.1 子节"),
            _line("第二节"),
            _line("内容"),
        ]
        doc = build_structured_document(lines)
        assert len(doc.main) == 2
        assert len(doc.main[0].children) == 1
        # "内容" 应属于第二节
        assert len(doc.main[1].content) == 1

    def test_blank_lines_ignored_in_body(self):
        lines = [
            _line("第一节"),
            _line(""),
            _line("内容"),
        ]
        doc = build_structured_document(lines)
        assert len(doc.main[0].content) == 1
        assert doc.main[0].content[0].text == "内容"


# ---- TOC 测试 ----

class TestTOC:
    def test_toc_basic(self):
        lines = [
            _line("目录"),
            _line("第一节 总则 ............. 1"),
            _line("第二节 转让 ............. 5"),
            _line(""),
            _line(""),
            _line("第一节 总则"),
            _line("正文内容"),
        ]
        doc = build_structured_document(lines)
        assert len(doc.toc) >= 2
        assert any("总则" in t.title for t in doc.toc)
        assert any("转让" in t.title for t in doc.toc)
        # 正文第一节应在 main 中
        assert len(doc.main) >= 1
        assert doc.main[0].title == "第一节 总则"

    def test_toc_duplicate_ordinal_ends(self):
        lines = [
            _line("目录"),
            _line("第一节 总则"),
            _line("第二节 转让"),
            _line("第一节 总则"),  # 重复 → TOC 结束
            _line("正文内容"),
        ]
        doc = build_structured_document(lines)
        assert len(doc.toc) >= 2
        # 第一个 "第一节 总则" 应在 main（reprocess 后）
        assert any(m.title == "第一节 总则" for m in doc.main)

    def test_toc_glossary_ends(self):
        lines = [
            _line("目录"),
            _line("第一节 总则"),
            _line("附录"),
            _line("附录内容"),
        ]
        doc = build_structured_document(lines)
        assert len(doc.toc) >= 1
        # "附录" 应作为 GLOSSARY 中的 H1 写入 main
        assert any("附录" in m.title for m in doc.main)


# ---- GLOSSARY 测试 ----

class TestGlossary:
    def test_glossary_basic(self):
        lines = [
            _line("定义"),
            _line("甲方：指某公司。"),
            _line("乙方：指另一公司。"),
            _line("第一节 正式内容"),
            _line("正文"),
        ]
        doc = build_structured_document(lines)
        # "定义" 作为 H1
        assert doc.main[0].role == "h1"
        assert "定义" in doc.main[0].title
        # 第一节 也在 main
        assert any(m.title == "第一节 正式内容" for m in doc.main)

    def test_glossary_duplicate_title_discarded(self):
        lines = [
            _line("定义"),
            _line("甲方：指某公司。"),
            _line("定义"),  # 重复，应被丢弃
            _line("乙方：指另一公司。"),
        ]
        doc = build_structured_document(lines)
        # "定义" H1 + body 内容
        assert doc.main[0].role == "h1"
        body_lines = [l for b in doc.main for l in b.content]
        texts = [l.text for l in body_lines]
        assert "定义" not in texts  # 重复的标题被丢弃


# ---- 表格测试 ----

class TestTable:
    def test_table_under_heading(self):
        lines = [
            _line("第一节"),
            _line("", is_table=True, table_rows=[["A", "B"], ["1", "2"]]),
        ]
        doc = build_structured_document(lines)
        assert len(doc.main) == 1
        assert doc.main[0].role == "h1"
        assert len(doc.main[0].children) == 1
        assert doc.main[0].children[0].role == "table"

    def test_table_toplevel(self):
        lines = [
            _line("", is_table=True, table_rows=[["X"]]),
        ]
        doc = build_structured_document(lines)
        assert len(doc.main) == 1
        assert doc.main[0].role == "table"


# ---- 后处理测试 ----

class TestFlatten:
    def test_flatten_section(self):
        block = SectionBlock(
            role="h1", title="第一节",
            content=[InputLine(text="正文行1"), InputLine(text="正文行2")],
            children=[
                SectionBlock(role="h2", title="一、子节", content=[InputLine(text="子内容")])
            ],
        )
        text = flatten_section(block)
        assert "第一节" in text
        assert "正文行1" in text
        assert "一、子节" in text
        assert "子内容" in text

    def test_flatten_table(self):
        block = SectionBlock(
            role="table",
            content=[InputLine(text="", is_table=True, table_rows=[["A", "B"], ["1", "2"]])],
        )
        text = flatten_section(block)
        assert "A B" in text
        assert "1 2" in text

    def test_flatten_document(self):
        doc = StructuredDocument(main=[
            SectionBlock(role="h1", title="第一节", content=[InputLine(text="内容")]),
        ])
        flatten_document(doc)
        assert doc.main[0].text_content != ""
        assert "第一节" in doc.main[0].text_content
        assert "内容" in doc.main[0].text_content


# ---- 运行 ----

if __name__ == "__main__":
    import traceback
    failed = 0
    total = 0

    test_classes = [TestClassifyLine, TestStateMachine, TestTOC, TestGlossary, TestTable, TestFlatten]

    for cls in test_classes:
        instance = cls()
        for attr in dir(instance):
            if not attr.startswith("test_"):
                continue
            total += 1
            try:
                getattr(instance, attr)()
                print(f"  PASS  {cls.__name__}.{attr}")
            except Exception as e:
                failed += 1
                print(f"  FAIL  {cls.__name__}.{attr}")
                traceback.print_exc()

    print(f"\n{total - failed}/{total} passed, {failed} failed")
    sys.exit(1 if failed else 0)
