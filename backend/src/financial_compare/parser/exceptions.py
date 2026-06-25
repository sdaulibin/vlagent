"""解析器异常定义。"""


class LanguageGateError(Exception):
    """语言门禁未通过：当前流水线仅处理以中文为主的文档。"""

    def __init__(self, message: str = "文档主体语言非中文，当前 StructuredParser 仅支持简体中文/繁体中文。"):
        super().__init__(message)
        self.message = message
