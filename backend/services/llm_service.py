import asyncio
from typing import List, Dict, Any
from pydantic import BaseModel

class Transaction(BaseModel):
    id: int
    date: str
    type: str
    amount: str
    balance: str
    desc: str

class LLMService:
    def __init__(self):
        # TODO: Initialize Qwen3 VL model or API client here
        pass

    async def identify_transactions(self, file_path: str) -> List[Transaction]:
        """
        Analyzes the uploaded file (image/pdf) and extractions transaction details.
        Currently returns mock data.
        """
        # Simulate processing delay
        await asyncio.sleep(1.5)

        # Mock Data (matching the prototype)
        # TODO: Replace with actual model inference
        # If using local Qwen3 VL, you would load the image from file_path
        # and pass it to the model with a prompt like:
        # "Identify all bank transactions in this statement. Return JSON format."
        
        return [
            Transaction(id=1, date="2023-10-24", type="转账汇款", amount="-5,000.00", balance="24,500.00", desc="支付宝转账-张三"),
            Transaction(id=2, date="2023-10-25", type="工资入账", amount="+12,000.00", balance="36,500.00", desc="XX科技有限公司-10月工资"),
            Transaction(id=3, date="2023-10-26", type="消费支出", amount="-328.50", balance="36,171.50", desc="沃尔玛超市购物"),
            Transaction(id=4, date="2023-10-27", type="理财赎回", amount="+50,000.00", balance="86,171.50", desc="招商银行理财赎回"),
            Transaction(id=5, date="2023-10-28", type="其他支出", amount="-100.00", balance="86,071.50", desc="手机话费充值"),
        ]

llm_service = LLMService()
