from fastapi import APIRouter, UploadFile, File, HTTPException
from services import pdf_processor
from typing import List
import shutil
import os
import uuid

router = APIRouter()

UPLOAD_DIR = "/Users/binginx/workspace/vl_flow/res"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Use original filename
        file_path = os.path.join(UPLOAD_DIR, file.filename)

        # Save the file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Process the file with PDF Processor
        # Note: This is a synchronous function, might block the event loop. 
        # For production, should run in a separate thread/process. 
        # For now, we run it directly as per request.
        raw_transactions = pdf_processor.process_pdf_to_excel(file_path, max_workers=4)

        # Map to frontend format
        transactions = []
        for idx, item in enumerate(raw_transactions):
            # Try to use "序号" as ID, otherwise generate one
            try:
                t_id = int(item.get("序号", idx)) 
            except:
                t_id = idx

            # Format amount
            income = item.get("收入", "0.00")
            expense = item.get("支出", "0.00")
            if income and income != "0.00" and income != "0":
                amount = f"+{income}"
            else:
                amount = f"-{expense}"

            transactions.append({
                "id": t_id,
                "date": item.get("交易时间", ""),
                "type": item.get("交易渠道", ""),
                "amount": amount,
                "balance": item.get("账户余额", ""),
                "desc": item.get("摘要备注", "")
            })

        return {
            "status": "success",
            "filename": file.filename,
            "transactions": transactions
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
