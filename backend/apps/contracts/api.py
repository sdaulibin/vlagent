from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List
import shutil
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, desc

from core.database import get_session
from apps.contracts.models import CompareTask, DiffRecord
from services import contract_processor

router = APIRouter(prefix="/contracts", tags=["contracts"])

UPLOAD_DIR = "/Users/binginx/PycharmProjects/vl_flow/backend/res/contracts"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("", response_model=List[CompareTask])
async def get_compare_tasks(session: AsyncSession = Depends(get_session)):
    """获取所有比对任务列表"""
    statement = select(CompareTask).order_by(desc(CompareTask.created_at))
    result = await session.execute(statement)
    return result.scalars().all()


@router.get("/{task_id}", response_model=CompareTask)
async def get_compare_task(task_id: int, session: AsyncSession = Depends(get_session)):
    """获取单个比对任务详情"""
    statement = select(CompareTask).where(CompareTask.id == task_id)
    result = await session.execute(statement)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/{task_id}/diffs", response_model=List[DiffRecord])
async def get_task_diffs(task_id: int, session: AsyncSession = Depends(get_session)):
    """获取比对任务的差异列表"""
    statement = select(DiffRecord).where(DiffRecord.task_id == task_id)
    result = await session.execute(statement)
    return result.scalars().all()


@router.post("/compare")
async def compare_contracts(
    file_a: UploadFile = File(...),
    file_b: UploadFile = File(...),
    session: AsyncSession = Depends(get_session)
):
    """上传两份文档并进行比对"""
    try:
        # 保存文件
        file_a_path = os.path.join(UPLOAD_DIR, f"a_{file_a.filename}")
        file_b_path = os.path.join(UPLOAD_DIR, f"b_{file_b.filename}")
        
        with open(file_a_path, "wb") as buffer:
            shutil.copyfileobj(file_a.file, buffer)
        
        with open(file_b_path, "wb") as buffer:
            shutil.copyfileobj(file_b.file, buffer)
        
        # 创建比对任务
        task = CompareTask(
            file_a_name=file_a.filename,
            file_a_path=file_a_path,
            file_b_name=file_b.filename,
            file_b_path=file_b_path,
            status="processing"
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        
        try:
            # 执行比对并获取内容
            result_data = contract_processor.compare_documents_with_content(file_a_path, file_b_path)
            
            content_a = result_data.get("content_a", "")
            content_b = result_data.get("content_b", "")
            diffs = result_data.get("diffs", [])
            
            # 更新任务内容
            task.content_a = content_a
            task.content_b = content_b
            
            # 保存差异记录
            for diff_data in diffs:
                diff = DiffRecord(
                    task_id=task.id,
                    diff_type=diff_data.get("type", "modified"),
                    original_text=diff_data.get("original", ""),
                    comparison_text=diff_data.get("comparison", ""),
                    location=diff_data.get("location", "")
                )
                session.add(diff)
            
            task.status = "done"
            await session.commit()
            
            return {
                "status": "success",
                "task_id": task.id,
                "diff_count": len(diffs),
                "content_a": content_a,
                "content_b": content_b
            }
            
        except Exception as e_compare:
            task.status = "failed"
            task.error_msg = str(e_compare)
            await session.commit()
            raise e_compare
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{task_id}")
async def delete_compare_task(task_id: int, session: AsyncSession = Depends(get_session)):
    """删除比对任务及其差异记录"""
    # 查询任务
    statement = select(CompareTask).where(CompareTask.id == task_id)
    result = await session.execute(statement)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 删除差异记录
    diff_stmt = select(DiffRecord).where(DiffRecord.task_id == task_id)
    diff_result = await session.execute(diff_stmt)
    diffs = diff_result.scalars().all()
    for diff in diffs:
        await session.delete(diff)
    
    # 删除文件
    for path in [task.file_a_path, task.file_b_path]:
        if os.path.exists(path):
            os.remove(path)
    
    # 删除任务记录
    await session.delete(task)
    await session.commit()
    
    return {"status": "success", "message": "Task deleted"}
