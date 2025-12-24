from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List
import shutil
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, desc

from src.database import get_session
from src.files.models import FileRecord
from src.transactions.models import (
    # 山东地方银行
    ShandongLocalSummary, ShandongLocalTransaction,
    # 光大银行
    EverbrightSummary, EverbrightTransaction,
    # 招商银行
    CmbSummary, CmbTransaction,
    # 济宁银行
    JiningSummary, JiningTransaction,
    # 广发银行
    CgbSummary, CgbTransaction,
)
from src.transactions.service import (
    create_shandong_transaction_records,
    create_shandong_summary_record,
    create_everbright_transaction_records,
    create_everbright_summary_record,
    create_cmb_transaction_records,
    create_cmb_summary_record,
    create_jining_transaction_records,
    create_jining_summary_record,
    create_cgb_transaction_records,
    create_cgb_summary_record,
)
from services import pdf_processor

router = APIRouter(prefix="/files", tags=["files"])

UPLOAD_DIR = "/Users/binginx/PycharmProjects/vl_flow/backend/res"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("", response_model=List[FileRecord])
async def get_files(session: AsyncSession = Depends(get_session)):
    """获取所有文件列表"""
    statement = select(FileRecord).order_by(desc(FileRecord.created_at))
    result = await session.execute(statement)
    return result.scalars().all()


@router.get("/{file_id}", response_model=FileRecord)
async def get_file(file_id: int, session: AsyncSession = Depends(get_session)):
    """获取单个文件详情"""
    statement = select(FileRecord).where(FileRecord.id == file_id)
    result = await session.execute(statement)
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return file


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    """上传文件（仅保存，不处理）"""
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)

        # 保存文件
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 创建文件记录 - 状态为 pending（待处理）
        db_file = FileRecord(filename=file.filename, file_path=file_path, status="pending")
        session.add(db_file)
        await session.commit()
        await session.refresh(db_file)

        return {
            "status": "success",
            "filename": file.filename,
            "file_id": db_file.id,
            "message": "文件上传成功，请点击开始识别"
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{file_id}/recognize")
async def start_recognition(file_id: int, session: AsyncSession = Depends(get_session)):
    """开始识别文件内容"""
    try:
        # 获取文件记录
        result = await session.execute(select(FileRecord).where(FileRecord.id == file_id))
        db_file = result.scalar_one_or_none()
        
        if not db_file:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        if db_file.status == "done":
            return {"status": "already_done", "message": "文件已识别完成"}
        
        if db_file.status == "processing":
            return {"status": "processing", "message": "文件正在识别中"}
        
        # 更新状态为处理中
        db_file.status = "processing"
        await session.commit()

        import time
        import asyncio
        from src.config import RECOGNITION_TIMEOUT
        start_time = time.time()
        
        try:
            # 提取文件内容（包含银行类型识别）
            # 使用 run_in_threadpool 避免阻塞主事件循环
            from fastapi.concurrency import run_in_threadpool
            
            # 使用 asyncio.wait_for 增加超时控制
            try:
                result = await asyncio.wait_for(
                    run_in_threadpool(pdf_processor.process_pdf_to_excel, db_file.file_path, max_workers=4),
                    timeout=RECOGNITION_TIMEOUT
                )
            except asyncio.TimeoutError:
                # 超时处理
                end_time = time.time()
                db_file.status = "error"
                db_file.error_msg = f"识别超时（超过 {RECOGNITION_TIMEOUT} 秒），任务已自动停止"
                db_file.recognition_duration = round((end_time - start_time) * 1000, 2)
                await session.commit()
                return {
                    "status": "error",
                    "message": db_file.error_msg,
                    "recognition_duration_ms": db_file.recognition_duration
                }
            
            # 获取银行类型
            bank_type = result.get("bank_type", "shandong_local")
            db_file.bank_type = bank_type
            
            # 记录原始数据量
            raw_transactions = result.get("transactions", [])
            
            # 根据银行类型创建对应的记录
            transactions = []
            summary = None
            
            if bank_type == "everbright":
                # 光大银行
                transactions = create_everbright_transaction_records(db_file.id, raw_transactions)
                summary = create_everbright_summary_record(db_file.id, result.get("summary"))
            elif bank_type == "cmb":
                # 招商银行
                transactions = create_cmb_transaction_records(db_file.id, raw_transactions)
                summary = create_cmb_summary_record(db_file.id, result.get("summary"))
            elif bank_type == "jining":
                # 济宁银行
                transactions = create_jining_transaction_records(db_file.id, raw_transactions)
                summary = create_jining_summary_record(db_file.id, result.get("summary"))
            elif bank_type == "cgb":
                # 广发银行（支持多汇总）
                summary_data = result.get("summary")
                
                if isinstance(summary_data, list) and len(summary_data) > 1:
                    # 多个汇总：按页码范围分配交易
                    summaries_info = []  # [(summary_obj, start_page)]
                    for s in summary_data:
                        summary_obj = create_cgb_summary_record(db_file.id, s)
                        if summary_obj:
                            start_page = s.get("_start_page", 0)
                            summaries_info.append((summary_obj, start_page))
                    
                    if summaries_info:
                        # 按 start_page 排序
                        summaries_info.sort(key=lambda x: x[1])
                        
                        # 批量添加汇总
                        summary_objs = [info[0] for info in summaries_info]
                        session.add_all(summary_objs)
                        await session.flush()  # 获取 summary id
                        
                        # 构建页码范围到 summary_id 的映射
                        # [(start_page, end_page, summary_id), ...]
                        page_ranges = []
                        for i, (summary_obj, start_page) in enumerate(summaries_info):
                            # end_page 是下一个汇总的 start_page - 1，最后一个汇总的 end_page 设为很大的数
                            if i + 1 < len(summaries_info):
                                end_page = summaries_info[i + 1][1] - 1
                            else:
                                end_page = 99999
                            page_ranges.append((start_page, end_page, summary_obj.id))
                        
                        # 为每个交易分配 summary_id
                        transactions = []
                        for tx_data in raw_transactions:
                            tx_page = tx_data.get("_page", 0)
                            # 找到对应的 summary
                            tx_summary_id = None
                            for start_p, end_p, s_id in page_ranges:
                                if start_p <= tx_page <= end_p:
                                    tx_summary_id = s_id
                                    break
                            # 创建交易并关联
                            tx_list = create_cgb_transaction_records(db_file.id, [tx_data], summary_id=tx_summary_id)
                            transactions.extend(tx_list)
                    else:
                        transactions = create_cgb_transaction_records(db_file.id, raw_transactions)
                    
                    summary = None  # 已批量添加
                else:
                    # 单个汇总
                    if isinstance(summary_data, list):
                        summary_data = summary_data[0] if summary_data else None
                    summary = create_cgb_summary_record(db_file.id, summary_data)
                    summary_id_for_transactions = None
                    if summary:
                        session.add(summary)
                        await session.flush()
                        summary_id_for_transactions = summary.id
                        summary = None
                    transactions = create_cgb_transaction_records(db_file.id, raw_transactions, summary_id=summary_id_for_transactions)
            else:
                # 山东地方银行（默认）
                transactions = create_shandong_transaction_records(db_file.id, raw_transactions)
                summary = create_shandong_summary_record(db_file.id, result.get("summary"))
            
            session.add_all(transactions)
            if summary:
                session.add(summary)
            
            # 计算并保存识别耗时（毫秒）
            end_time = time.time()
            db_file.recognition_duration = round((end_time - start_time) * 1000, 2)
            
            # 更新文件状态
            db_file.status = "done"
            await session.commit()
            
            return {
                "status": "success",
                "file_id": db_file.id,
                "bank_type": bank_type,
                "transactions_count": len(transactions),
                "has_summary": summary is not None,
                "recognition_duration_ms": db_file.recognition_duration
            }

        except Exception as e_process:
            db_file.status = "failed"
            db_file.error_msg = str(e_process)
            await session.commit()
            raise e_process

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{file_id}")
async def delete_file(file_id: int, session: AsyncSession = Depends(get_session)):
    """删除文件及其关联的所有数据"""
    try:
        # 查询文件记录
        statement = select(FileRecord).where(FileRecord.id == file_id)
        result = await session.execute(statement)
        file_record = result.scalar_one_or_none()
        
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")
        
        from sqlmodel import delete
        
        # 删除山东地方银行记录
        await session.execute(
            delete(ShandongLocalTransaction).where(ShandongLocalTransaction.file_id == file_id)
        )
        await session.execute(
            delete(ShandongLocalSummary).where(ShandongLocalSummary.file_id == file_id)
        )
        
        # 删除光大银行记录
        await session.execute(
            delete(EverbrightTransaction).where(EverbrightTransaction.file_id == file_id)
        )
        await session.execute(
            delete(EverbrightSummary).where(EverbrightSummary.file_id == file_id)
        )
        
        # 删除招商银行记录
        await session.execute(
            delete(CmbTransaction).where(CmbTransaction.file_id == file_id)
        )
        await session.execute(
            delete(CmbSummary).where(CmbSummary.file_id == file_id)
        )
        
        # 济宁银行
        await session.execute(
            delete(JiningTransaction).where(JiningTransaction.file_id == file_id)
        )
        await session.execute(
            delete(JiningSummary).where(JiningSummary.file_id == file_id)
        )
        
        # 广发银行（先删 transaction 因为有外键约束）
        await session.execute(
            delete(CgbTransaction).where(CgbTransaction.file_id == file_id)
        )
        await session.execute(
            delete(CgbSummary).where(CgbSummary.file_id == file_id)
        )
        
        # 删除上传的原文件
        if file_record.file_path and os.path.exists(file_record.file_path):
            os.remove(file_record.file_path)
        
        # 删除处理过程中生成的目录 (res/文件名_task_*)
        filename_base = os.path.splitext(file_record.filename)[0]
        for item in os.listdir(UPLOAD_DIR):
            item_path = os.path.join(UPLOAD_DIR, item)
            if os.path.isdir(item_path) and item.startswith(f"task_{filename_base}"):
                shutil.rmtree(item_path)
        
        # 删除文件记录
        await session.delete(file_record)
        await session.commit()
        
        return {"status": "success", "message": f"File {file_id} deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{file_id}/export")
async def export_file(file_id: int, session: AsyncSession = Depends(get_session)):
    """导出文件交易数据为 Excel（包含汇总信息）"""
    from fastapi.responses import StreamingResponse
    from io import BytesIO
    from urllib.parse import quote
    from openpyxl import Workbook
    
    # 获取文件信息
    file_stmt = select(FileRecord).where(FileRecord.id == file_id)
    file_result = await session.execute(file_stmt)
    file_record = file_result.scalar_one_or_none()
    
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    bank_type = file_record.bank_type or "shandong_local"
    
    # 创建 Excel 工作簿
    wb = Workbook()
    ws = wb.active
    ws.title = "交易明细"
    
    # 根据银行类型导出
    if bank_type == "everbright":
        # 光大银行 - 汇总信息
        summary_stmt = select(EverbrightSummary).where(EverbrightSummary.file_id == file_id)
        summary_result = await session.execute(summary_stmt)
        summary = summary_result.scalar_one_or_none()
        if summary:
            ws.append(["账户名称", summary.account_name])
            ws.append(["账号", summary.account_number])
            ws.append(["交易日期", summary.date_range])
            ws.append(["借方发生额", summary.debit_amount])
            ws.append(["贷方发生额", summary.credit_amount])
            ws.append(["借方笔数", summary.debit_count])
            ws.append(["贷方笔数", summary.credit_count])
            ws.append([])
        
        # 交易明细
        headers = ["序号", "交易日期", "时间", "借/贷", "交易金额", "账户余额", "对方账号", "对方名称", "凭证号", "摘要", "流水号"]
        ws.append(headers)
        tx_stmt = select(EverbrightTransaction).where(EverbrightTransaction.file_id == file_id)
        tx_result = await session.execute(tx_stmt)
        for tx in tx_result.scalars().all():
            ws.append([tx.sequence, tx.transaction_date, tx.transaction_time, tx.debit_credit, tx.amount, tx.balance, tx.counterparty_account, tx.counterparty_name, tx.voucher_no, tx.description, tx.serial_no])
    
    elif bank_type == "cmb":
        # 招商银行 - 汇总信息
        summary_stmt = select(CmbSummary).where(CmbSummary.file_id == file_id)
        summary_result = await session.execute(summary_stmt)
        summary = summary_result.scalar_one_or_none()
        if summary:
            ws.append(["账号", summary.account_number])
            ws.append(["账号名", summary.account_name])
            ws.append(["开始日期", summary.start_date])
            ws.append(["结束日期", summary.end_date])
            ws.append(["出账总笔数", summary.debit_count])
            ws.append(["入账总笔数", summary.credit_count])
            ws.append(["出账总金额", summary.debit_total])
            ws.append(["入账总金额", summary.credit_total])
            ws.append([])
        
        # 交易明细
        headers = ["交易流水号", "交易日期", "借方出账", "贷方入账", "余额", "收付方名称", "收付方账号", "摘要", "交易类型", "公司一卡通号", "打印实例号"]
        ws.append(headers)
        tx_stmt = select(CmbTransaction).where(CmbTransaction.file_id == file_id)
        tx_result = await session.execute(tx_stmt)
        for tx in tx_result.scalars().all():
            ws.append([tx.serial_no, tx.transaction_date, tx.debit_amount, tx.credit_amount, tx.balance, tx.counterparty_name, tx.counterparty_account, tx.description, tx.transaction_type, tx.card_no, tx.print_instance_no])
    
    elif bank_type == "jining":
        # 济宁银行 - 汇总信息
        summary_stmt = select(JiningSummary).where(JiningSummary.file_id == file_id)
        summary_result = await session.execute(summary_stmt)
        summary = summary_result.scalar_one_or_none()
        if summary:
            ws.append(["账号", summary.account_number])
            ws.append(["账户名称", summary.account_name])
            ws.append(["起止日期", summary.date_range])
            ws.append(["币种", summary.currency])
            ws.append(["收入金额合计", summary.income_total])
            ws.append(["支出金额合计", summary.expense_total])
            ws.append(["开户机构", summary.bank_name])
            ws.append([])
        
        # 交易明细
        headers = ["序号", "记账日期", "交易渠道", "收入", "支出", "账户余额", "摘要备注", "交易对手信息"]
        ws.append(headers)
        tx_stmt = select(JiningTransaction).where(JiningTransaction.file_id == file_id)
        tx_result = await session.execute(tx_stmt)
        for tx in tx_result.scalars().all():
            ws.append([tx.sequence, tx.transaction_date, tx.channel, tx.income, tx.expense, tx.balance, tx.description, tx.counterparty_info])
    
    elif bank_type == "cgb":
        # 广发银行 - 支持多汇总分 sheet 导出
        summary_stmt = select(CgbSummary).where(CgbSummary.file_id == file_id)
        summary_result = await session.execute(summary_stmt)
        summaries = summary_result.scalars().all()
        
        if summaries:
            # 删除默认 sheet，为每个汇总创建单独的 sheet
            wb.remove(ws)
            
            for idx, summary in enumerate(summaries):
                # Sheet 名称使用起止日期或序号
                sheet_name = f"明细{idx+1}" if not summary.date_range else summary.date_range[:30]
                sheet = wb.create_sheet(title=sheet_name)
                
                # 汇总信息
                sheet.append(["户名", summary.account_name])
                sheet.append(["账号", summary.account_number])
                sheet.append(["起止日期", summary.date_range])
                sheet.append(["币种", summary.currency])
                sheet.append(["单位", summary.unit])
                sheet.append(["支出总金额", summary.expense_total])
                sheet.append(["支出总笔数", summary.expense_count])
                sheet.append(["收入总金额", summary.income_total])
                sheet.append(["收入总笔数", summary.income_count])
                sheet.append(["账户当前余额", summary.current_balance])
                sheet.append(["记录数", summary.record_count])
                sheet.append([])
                
                # 交易明细标题
                headers = ["流水号", "交易时间", "收入", "支出", "余额", "币种", "对方账号", "对方户名", "交易行所", "对方开户行联行号", "对方开户行", "凭证号", "摘要", "备注", "附言"]
                sheet.append(headers)
                
                # 该汇总关联的交易明细（支持 summary_id 匹配或按 file_id 匹配的旧数据）
                from sqlalchemy import or_
                tx_stmt = select(CgbTransaction).where(
                    or_(
                        CgbTransaction.summary_id == summary.id,
                        # 向后兼容：如果只有一个汇总且交易没有 summary_id，按 file_id 匹配
                        (CgbTransaction.file_id == file_id) & (CgbTransaction.summary_id == None)
                    ) if len(summaries) == 1 else CgbTransaction.summary_id == summary.id
                )
                tx_result = await session.execute(tx_stmt)
                for tx in tx_result.scalars().all():
                    sheet.append([tx.serial_no, tx.transaction_time, tx.income, tx.expense, tx.balance, tx.currency, tx.counterparty_account, tx.counterparty_name, tx.transaction_branch, tx.counterparty_bank_code, tx.counterparty_bank, tx.voucher_no, tx.description, tx.remark, tx.postscript])
        else:
            # 无汇总时导出所有交易明细
            headers = ["流水号", "交易时间", "收入", "支出", "余额", "币种", "对方账号", "对方户名", "交易行所", "对方开户行联行号", "对方开户行", "凭证号", "摘要", "备注", "附言"]
            ws.append(headers)
            tx_stmt = select(CgbTransaction).where(CgbTransaction.file_id == file_id)
            tx_result = await session.execute(tx_stmt)
            for tx in tx_result.scalars().all():
                ws.append([tx.serial_no, tx.transaction_time, tx.income, tx.expense, tx.balance, tx.currency, tx.counterparty_account, tx.counterparty_name, tx.transaction_branch, tx.counterparty_bank_code, tx.counterparty_bank, tx.voucher_no, tx.description, tx.remark, tx.postscript])
    
    else:
        # 山东地方银行 - 汇总信息
        summary_stmt = select(ShandongLocalSummary).where(ShandongLocalSummary.file_id == file_id)
        summary_result = await session.execute(summary_stmt)
        summary = summary_result.scalar_one_or_none()
        if summary:
            ws.append(["账户名称", summary.account_name])
            ws.append(["账(卡)号", summary.account_number])
            ws.append(["开户行", summary.bank_name])
            ws.append(["起止日期", summary.date_range])
            ws.append(["收入笔数", summary.income_count])
            ws.append(["收入总额", summary.income_total])
            ws.append(["支出笔数", summary.expense_count])
            ws.append(["支出总额", summary.expense_total])
            ws.append([])
        
        # 交易明细
        headers = ["序号", "交易时间", "交易渠道", "收入", "支出", "账户余额", "币种", "对方账号", "对方户名", "摘要备注"]
        ws.append(headers)
        tx_stmt = select(ShandongLocalTransaction).where(ShandongLocalTransaction.file_id == file_id)
        tx_result = await session.execute(tx_stmt)
        for tx in tx_result.scalars().all():
            ws.append([tx.sequence, tx.transaction_time, tx.channel, tx.income, tx.expense, tx.balance, tx.currency, tx.counterparty_account, tx.counterparty_name, tx.description])
    
    # 保存到内存
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    # 生成文件名
    filename = os.path.splitext(file_record.filename)[0] + ".xlsx"
    encoded_filename = quote(filename)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
    )

