"""
文件验证服务单元测试
"""
import pytest
from services.pdf.file_validator import validate_pdf_format


class TestValidatePdfFormat:
    """PDF 格式验证测试"""
    
    def test_valid_pdf_file(self):
        """测试有效的 PDF 文件"""
        filename = "test.pdf"
        # PDF 魔数
        content = b'%PDF-1.4 fake content'
        
        is_valid, error_msg = validate_pdf_format(filename, content)
        
        assert is_valid is True
        assert error_msg == ""
    
    def test_wrong_extension_docx(self):
        """测试 .docx 扩展名"""
        filename = "test.docx"
        content = b'%PDF-1.4 fake content'
        
        is_valid, error_msg = validate_pdf_format(filename, content)
        
        assert is_valid is False
        assert "仅支持 PDF" in error_msg
    
    def test_wrong_extension_txt(self):
        """测试 .txt 扩展名"""
        filename = "test.txt"
        content = b'Some text content'
        
        is_valid, error_msg = validate_pdf_format(filename, content)
        
        assert is_valid is False
        assert "仅支持 PDF" in error_msg
    
    def test_wrong_extension_uppercase(self):
        """测试大写扩展名 .PDF"""
        filename = "test.PDF"
        content = b'%PDF-1.4 fake content'
        
        is_valid, error_msg = validate_pdf_format(filename, content)
        
        assert is_valid is True
        assert error_msg == ""
    
    def test_fake_pdf_wrong_magic(self):
        """测试假 PDF 文件（扩展名正确但内容不是 PDF）"""
        filename = "fake.pdf"
        # 不是 PDF 魔数
        content = b'PK\x03\x04 this is actually a zip'
        
        is_valid, error_msg = validate_pdf_format(filename, content)
        
        assert is_valid is False
        assert "不是有效的 PDF" in error_msg
    
    def test_empty_content(self):
        """测试空内容"""
        filename = "empty.pdf"
        content = b''
        
        is_valid, error_msg = validate_pdf_format(filename, content)
        
        assert is_valid is False
        assert "不是有效的 PDF" in error_msg
    
    def test_image_renamed_to_pdf(self):
        """测试图片改名为 PDF"""
        filename = "image.pdf"
        # PNG 魔数
        content = b'\x89PNG\r\n\x1a\n'
        
        is_valid, error_msg = validate_pdf_format(filename, content)
        
        assert is_valid is False
        assert "不是有效的 PDF" in error_msg


# 银行流水验证测试需要 AI 服务，暂时跳过
class TestValidateBankStatement:
    """银行流水验证测试（需要 AI 服务）"""
    
    @pytest.mark.skip(reason="需要 AI 服务支持")
    def test_valid_bank_statement(self):
        """测试有效的银行流水文件"""
        pass
    
    @pytest.mark.skip(reason="需要 AI 服务支持")
    def test_invoice_document(self):
        """测试发票文件（应返回 False）"""
        pass
    
    @pytest.mark.skip(reason="需要 AI 服务支持")
    def test_contract_document(self):
        """测试合同文件（应返回 False）"""
        pass
