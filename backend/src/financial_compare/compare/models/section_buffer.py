"""节内活树缓冲区：content_items 原子，匹配成功即摘除。"""

from __future__ import annotations

from dataclasses import dataclass, field

from financial_compare.document.item import DocumentItem, TableBlock, TextLine, is_table_block, is_text_line


@dataclass
class SectionBuffer:
    items: list[DocumentItem] = field(default_factory=list)

    @classmethod
    def from_node(cls, node) -> SectionBuffer:
        return cls(list(node.content_items))

    def text_lines(self) -> list[TextLine]:
        return [i for i in self.items if is_text_line(i)]

    def tables(self) -> list[TableBlock]:
        return [i for i in self.items if is_table_block(i)]

    def remove(self, item: DocumentItem) -> None:
        self.items[:] = [x for x in self.items if x is not item]

    def remove_many(self, to_remove: list[DocumentItem]) -> None:
        remove_ids = {id(x) for x in to_remove}
        self.items[:] = [x for x in self.items if id(x) not in remove_ids]

    def extend(self, new_items: list[DocumentItem]) -> None:
        self.items.extend(new_items)

    def drain(self) -> list[DocumentItem]:
        out = list(self.items)
        self.items.clear()
        return out

    def replace_text_lines(self, lines: list[TextLine]) -> None:
        for line in self.text_lines():
            self.remove(line)
        self.extend(lines)

    def replace_tables(self, tables: list[TableBlock]) -> None:
        for table in self.tables():
            self.remove(table)
        self.extend(tables)
