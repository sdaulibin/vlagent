"""
影像平台文件服务 API 路由

提供影像平台 (SunECM) 文件的上传、下载、查询、删除接口。
"""
import logging
import os
import shutil
import tempfile
import zipfile
from io import BytesIO

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from src.file_provider.schemas import DownloadRequest, QueryRequest, FileProviderResponse
from src.file_provider import service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/file-provider", tags=["file-provider"])


@router.get("/status")
async def get_status():
    """检查 JVM 和影像平台 SDK 状态"""
    ready = service.is_jvm_ready()
    return {
        "jvm_ready": ready,
        "jar_exists": service.JAR_PATH.exists(),
        "config_exists": (service.LIB_DIR / "ServerConfig.xml").exists(),
    }


@router.post("/download")
async def download_file(req: DownloadRequest):
    """
    从影像平台下载文件

    按业务流水号下载文件到临时目录，打包为 ZIP 返回。
    """
    tmp_dir = tempfile.mkdtemp(prefix="ecm_download_")

    try:
        result = service.download(
            save_path=tmp_dir,
            busi_serial_no=req.busi_serial_no,
            system_code=req.system_code,
            params=req.params,
            is_tfs=req.is_tfs,
        )

        # 检查下载目录中的文件
        files = [
            f for f in os.listdir(tmp_dir)
            if os.path.isfile(os.path.join(tmp_dir, f))
        ]

        if not files:
            return FileProviderResponse(
                success=False,
                message=f"下载完成但目录为空，SDK 返回: {result}",
            )

        # 单文件直接返回，多文件打包 ZIP
        if len(files) == 1:
            file_path = os.path.join(tmp_dir, files[0])
            from fastapi.responses import FileResponse

            return FileResponse(
                file_path,
                filename=files[0],
                background=lambda: _cleanup(tmp_dir),
            )

        # 多文件打包 ZIP
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in files:
                zf.write(os.path.join(tmp_dir, fname), fname)
        zip_buffer.seek(0)

        from fastapi.responses import StreamingResponse

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={req.busi_serial_no}.zip"
            },
            background=lambda: _cleanup(tmp_dir),
        )

    except RuntimeError as e:
        _cleanup(tmp_dir)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        _cleanup(tmp_dir)
        logger.error(f"下载失败: {e}")
        raise HTTPException(status_code=500, detail=f"下载失败: {e}")


@router.post("/query")
async def query_file(req: QueryRequest) -> FileProviderResponse:
    """
    查询影像平台文件信息

    按业务流水号查询文件列表和元数据。
    """
    try:
        result = service.query(
            busi_serial_no=req.busi_serial_no,
            system_code=req.system_code,
            params=req.params,
        )
        return FileProviderResponse(success=True, message="查询完成", data=result)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"查询失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {e}")


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    busi_serial_no: str = Form(...),
    system_code: str = Form("OL_PT"),
) -> FileProviderResponse:
    """
    上传文件到影像平台

    上传单个文件到指定业务流水号下。
    """
    tmp_dir = tempfile.mkdtemp(prefix="ecm_upload_")

    try:
        # 保存上传文件到临时目录
        tmp_path = os.path.join(tmp_dir, os.path.basename(file.filename))
        with open(tmp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        result = service.upload(
            file_path=tmp_dir,
            busi_serial_no=busi_serial_no,
            system_code=system_code,
        )
        return FileProviderResponse(success=True, message="上传完成", data=result)

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"上传失败: {e}")
    finally:
        _cleanup(tmp_dir)


@router.delete("/{busi_serial_no}")
async def delete_file(
    busi_serial_no: str,
    system_code: str = "OL_PT",
    is_tfs: bool = False,
) -> FileProviderResponse:
    """
    删除影像平台文件（逻辑删除）

    按业务流水号删除指定系统代码下的文件。
    """
    try:
        result = service.delete(
            busi_serial_no=busi_serial_no,
            system_code=system_code,
            is_tfs=is_tfs,
        )
        return FileProviderResponse(success=True, message="删除完成", data=result)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"删除失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")


def _cleanup(tmp_dir: str):
    """清理临时目录"""
    try:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
    except Exception as e:
        logger.warning(f"清理临时目录失败 {tmp_dir}: {e}")
