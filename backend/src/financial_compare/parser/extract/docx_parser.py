"""DOCX 文本解析器，使用 python-docx 提取 Word 文档中的文本内容。"""

from pathlib import Path
from typing import Literal

from financial_compare.parser.extract.docx_table import DocxTableExtractor

from docx import Document
from docx.table import Table, _Row
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn

from financial_compare.document.item import DocumentItem, Row, TableBlock, TableLoc, TextLine, TextLoc

# OOXML ``w:numFmt``：在 Word 中常显示为「一、二、」类序号，可用 ``_to_chinese_number`` 近似渲染。
# ``japaneseCounting`` 在中文年报等文档中常见；``ideographTraditional`` / ``taiwaneseCounting`` 同理。
_NUMFMT_IDEOGRAPH_SIMPLE = frozenset({
    "chineseCounting",
    "japaneseCounting",
    "ideographTraditional",
    "taiwaneseCounting",
})


def _find_el_by_attr(parent, tag_qn: str, attr_qn: str, attr_val: str):
    """在子树中查找首个 ``tag_qn`` 且 ``attr_qn == attr_val`` 的元素。

    说明：不可使用 ``element.find(tag, {attr: val})``，ElementTree 的第二个参数是
    *命名空间前缀表*，不是按属性筛选；错误用法会匹配到错误的 ``w:num``，导致
    编号样式错乱（例如把 ``1.`` 误判为项目符号 ````）。
    """
    if parent is None:
        return None
    want = str(attr_val)
    for el in parent.iter(tag_qn):
        if el.get(attr_qn) == want:
            return el
    return None


class DOCXParser:
    """DOCX 文本解析器。

    使用 python-docx 读取 DOCX 文件中的所有文本和表格，
    按文档中的原始顺序返回 ``DocumentItem`` 混合流。
    表格输出 ``TableBlock``（含 HTML 与表头行推断）。
    支持提取段落的自动编号。
    """

    def __init__(self) -> None:
        self._numbering_cache = {}
        self._level_counters = {}

    def _get_numbering_part(self, doc: Document):
        """获取文档的 numbering part。

        Args:
            doc: Document 对象

        Returns:
            numbering part 或 None
        """
        try:
            return doc.part.numbering_part._element
        except Exception:
            return None

    def _get_list_number(self, doc: Document, paragraph: Paragraph) -> str:
        """获取段落的自动编号文本。

        Args:
            doc: Document 对象
            paragraph: 段落对象

        Returns:
            编号文本（如 "1.", "(1)", "a."），如果没有编号则返回空字符串
        """
        try:
            # 获取段落的 pPr 元素
            p = paragraph._p
            pPr = p.find(qn('w:pPr'))
            if pPr is None:
                return ""

            # 查找 numPr (numbering properties)
            numPr = pPr.find(qn('w:numPr'))
            if numPr is None:
                return ""

            # 获取 numId (编号 ID)
            numId_elem = numPr.find(qn('w:numId'))
            if numId_elem is None:
                return ""
            num_id = numId_elem.get(qn('w:val'))

            # 获取 ilvl (级别)
            ilvl_elem = numPr.find(qn('w:ilvl'))
            ilvl = int(ilvl_elem.get(qn('w:val'))) if ilvl_elem is not None else 0

            # Word：w:numId=0 表示已清除列表编号（numbering.xml 中无对应 w:num）；
            # w:ilvl=255 为「无有效列表层级」占位，均不得合成可见序号。
            if num_id == "0" or ilvl == 255:
                return ""

            # 先解析编号定义，成功后再递增计数器，避免无效 numPr 污染序号。
            numbering_part = self._get_numbering_part(doc)
            if numbering_part is None:
                return ""

            num = _find_el_by_attr(numbering_part, qn('w:num'), qn('w:numId'), num_id)
            if num is None:
                return ""

            abstract_num_id_elem = num.find(qn('w:abstractNumId'))
            if abstract_num_id_elem is None:
                return ""
            abstract_num_id = abstract_num_id_elem.get(qn('w:val'))

            abstract_num = _find_el_by_attr(
                numbering_part,
                qn('w:abstractNum'),
                qn('w:abstractNumId'),
                abstract_num_id,
            )
            if abstract_num is None:
                return ""

            lvl = _find_el_by_attr(
                abstract_num, qn('w:lvl'), qn('w:ilvl'), str(ilvl)
            )
            if lvl is None:
                return ""

            if num_id not in self._level_counters:
                self._level_counters[num_id] = {}
            if ilvl not in self._level_counters[num_id]:
                self._level_counters[num_id][ilvl] = 0

            self._level_counters[num_id][ilvl] += 1
            current_num = self._level_counters[num_id][ilvl]

            # 获取 numFmt (编号格式类型)
            num_fmt_elem = lvl.find(qn('w:numFmt'))
            num_fmt = num_fmt_elem.get(qn('w:val')) if num_fmt_elem is not None else "decimal"

            # 获取 lvlText (编号文本模板)
            lvl_text_elem = lvl.find(qn('w:lvlText'))
            lvl_text = lvl_text_elem.get(qn('w:val')) if lvl_text_elem is not None else "%1."

            # 获取 lvlJc (对齐方式)
            lvl_jc_elem = lvl.find(qn('w:lvlJc'))
            lvl_jc = lvl_jc_elem.get(qn('w:val')) if lvl_jc_elem is not None else "left"

            # 处理项目符号 (bullet)
            if num_fmt == "bullet":
                return self._get_bullet_symbol(lvl_text, lvl)

            # 格式化编号数字
            if num_fmt == "decimal":
                formatted_num = str(current_num)
            elif num_fmt == "lowerLetter":
                formatted_num = chr(ord('a') + current_num - 1)
            elif num_fmt == "upperLetter":
                formatted_num = chr(ord('A') + current_num - 1)
            elif num_fmt == "lowerRoman":
                formatted_num = self._to_roman(current_num, upper=False)
            elif num_fmt == "upperRoman":
                formatted_num = self._to_roman(current_num, upper=True)
            elif num_fmt in _NUMFMT_IDEOGRAPH_SIMPLE:
                formatted_num = self._to_chinese_number(current_num)
            elif num_fmt == "chineseCountingThousand":
                formatted_num = self._to_chinese_number(current_num) + "、"
            else:
                formatted_num = str(current_num)

            # 替换 lvlText 中的 %1 为实际数字
            result = lvl_text.replace("%1", formatted_num)

            # 处理其他占位符（简化处理，只处理连续的编号）
            for i in range(2, 10):
                if f"%{i}" in result:
                    parent_level = ilvl - (i - 1)
                    if parent_level >= 0 and parent_level in self._level_counters.get(num_id, {}):
                        parent_num = self._level_counters[num_id][parent_level]
                        result = result.replace(f"%{i}", str(parent_num))
                    else:
                        result = result.replace(f"%{i}", "")

            return result

        except Exception:
            return ""

    def _get_bullet_symbol(self, lvl_text: str, lvl) -> str:
        """获取项目符号的标准化表示。

        Args:
            lvl_text: 原始 lvlText 内容
            lvl: 级别元素

        Returns:
            标准化的项目符号字符串
        """
        # 如果 lvlText 包含非标准符号（Wingdings等特殊字体），转换为标准符号
        # 常见的 Wingdings 符号映射
        wingdings_map = {
            '\uf06e': '•',  # 圆点
            '\uf076': '•',
            '\uf0a7': '•',
            '\uf0b7': '•',
            '\uf0d8': '•',
            '': '•',  # 方块 (U+F06E in private use area)
            '': '•',  # 圆点 (U+F0B7)
            '': '▸',  # 箭头 (U+F0D8)
            '': '•',
            '': '•',
            '': '•',
        }

        # 首先尝试从 lvlText 直接获取
        if lvl_text and lvl_text != '%1':
            # 检查是否是 Wingdings 等特殊字体符号
            for special_char, standard_char in wingdings_map.items():
                if special_char in lvl_text:
                    return standard_char

            # 如果 lvlText 不是占位符形式，直接返回
            if '%' not in lvl_text:
                return lvl_text

        # 尝试从 lvl 获取 rPr (run properties) 中的字体信息
        try:
            rPr = lvl.find(qn('w:rPr'))
            if rPr is not None:
                rFonts = rPr.find(qn('w:rFonts'))
                if rFonts is not None:
                    ascii_font = rFonts.get(qn('w:ascii'))
                    hAnsi_font = rFonts.get(qn('w:hAnsi'))

                    # 如果是 Wingdings 或 Symbol 字体，返回标准项目符号
                    if ascii_font in ['Wingdings', 'Wingdings 2', 'Wingdings 3', 'Symbol', 'Webdings']:
                        return '•'
        except Exception:
            pass

        # 默认返回标准项目符号
        return '•'

    def _to_roman(self, num: int, upper: bool = True) -> str:
        """将数字转换为罗马数字。

        Args:
            num: 数字
            upper: 是否使用大写

        Returns:
            罗马数字字符串
        """
        val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
        syb = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]

        roman_num = ""
        for i in range(len(val)):
            count = num // val[i]
            roman_num += syb[i] * count
            num %= val[i]

        return roman_num if upper else roman_num.lower()

    def _to_chinese_number(self, num: int) -> str:
        """将数字转换为中文数字。

        Args:
            num: 数字

        Returns:
            中文数字字符串
        """
        chinese_nums = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
        chinese_units = ["", "十", "百", "千"]

        if num == 0:
            return chinese_nums[0]

        if num <= 10:
            return chinese_nums[num]

        if num < 20:
            return "十" + (chinese_nums[num - 10] if num > 10 else "")

        result = ""
        num_str = str(num)
        length = len(num_str)

        for i, digit in enumerate(num_str):
            d = int(digit)
            if d != 0:
                result += chinese_nums[d] + chinese_units[length - i - 1]
            elif result and result[-1] != chinese_nums[0]:
                result += chinese_nums[0]

        # 去除末尾的零
        if result.endswith(chinese_nums[0]):
            result = result[:-1]

        return result

    @staticmethod
    def _row_type_from_tr(row: _Row) -> Literal["header", "body"]:
        """行样式含 w:tblHeader 时标为 header，否则 body。"""
        tr_pr = row._tr.find(qn("w:trPr"))
        if tr_pr is not None and tr_pr.find(qn("w:tblHeader")) is not None:
            return "header"
        return "body"

    @staticmethod
    def _extract_row_cells(row: _Row) -> list[str]:
        cell_texts: list[str] = []
        seen_cells: set[int] = set()
        for cell in row.cells:
            tc_id = id(cell._tc)
            if tc_id in seen_cells:
                continue
            seen_cells.add(tc_id)
            cell_texts.append(cell.text.strip())
        return cell_texts

    def parse(self, docx_path: str | Path) -> list[DocumentItem]:
        """解析 DOCX 文件，按文档顺序返回 ``DocumentItem`` 混合流。

        处理逻辑：
        1. 按文档顺序遍历段落和表格
        2. 普通段落：``TextLine``，保留自动编号
        3. 表格：单个 ``TableBlock``，每行一个 ``Row``
        4. 全局递增 ``stream_index``、``element_index``、``table_index``

        Args:
            docx_path: DOCX 文件路径

        Returns:
            ``DocumentItem`` 列表。空段落保留为 ``TextLine(text="")``。

        Raises:
            FileNotFoundError: 当文件不存在时
            RuntimeError: 当解析失败时
        """
        docx_path = Path(docx_path)
        if not docx_path.exists():
            raise FileNotFoundError(f"DOCX 文件不存在: {docx_path}")

        items: list[DocumentItem] = []
        self._numbering_cache = {}
        self._level_counters = {}
        stream_index = 0
        element_index = 0
        table_index = 0

        try:
            doc = Document(docx_path)

            for element in doc.element.body:
                tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

                if tag == "p":
                    paragraph = Paragraph(element, doc)
                    stripped = paragraph.text.strip()
                    if not stripped:
                        text = ""
                    else:
                        text = stripped
                        numbering = self._get_list_number(doc, paragraph)
                        if numbering:
                            text = f"{numbering} {text}"

                    items.append(
                        TextLine(
                            text=text,
                            loc=TextLoc(
                                stream_index=stream_index,
                                element_index=element_index,
                            ),
                        )
                    )
                    stream_index += 1
                    element_index += 1

                elif tag == "tbl":
                    table = Table(element, doc)
                    rows: list[Row] = []
                    for row_index, row in enumerate(table.rows):
                        cell_texts = self._extract_row_cells(row)
                        if not cell_texts:
                            continue
                        rows.append(
                            Row(
                                content="|".join(cell_texts),
                                row_type=self._row_type_from_tr(row),
                                row_index=row_index,
                            )
                        )

                    if rows:
                        block = TableBlock(
                            html=None,
                            rows=rows,
                            loc=TableLoc(
                                stream_index=stream_index,
                                table_index=table_index,
                                element_index=element_index,
                            ),
                        )
                        block = DocxTableExtractor.extract(block)
                        items.append(block)
                        stream_index += 1
                        table_index += 1
                    element_index += 1

        except Exception as e:
            raise RuntimeError(f"解析 DOCX 失败: {e}") from e

        return items
