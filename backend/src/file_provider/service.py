"""
影像平台 (SunECM) SDK 封装

通过 JPype 调用 Java SDK (fileUpload.jar)，提供文件上传/下载/查询/删除功能。
"""
import logging
import os
import threading
from pathlib import Path
from typing import Optional

from src.config import settings

logger = logging.getLogger(__name__)

# 模块级状态
_jvm_lock = threading.Lock()
_jvm_started = False

BACKEND_DIR = Path(__file__).parent.parent.parent
LIB_DIR = BACKEND_DIR / "lib"
JAR_PATH = LIB_DIR / "fileUpload.jar"


def init_jvm() -> bool:
    """初始化 JVM（线程安全，单例）"""
    global _jvm_started

    if _jvm_started:
        return True

    with _jvm_lock:
        if _jvm_started:
            return True

        try:
            import jpype

            if jpype.isJVMStarted():
                _jvm_started = True
                return True

            if not JAR_PATH.exists():
                logger.error(f"JAR 文件不存在: {JAR_PATH}")
                return False

            classpath = str(JAR_PATH)
            user_dir = str(LIB_DIR)

            jpype.startJVM(
                f"-Duser.dir={user_dir}",
                classpath=[classpath],
                convertStrings=True,
                jvmpath=None,
            )

            # 验证 Client 类可加载
            jpype.JClass("com.bqd.cms.Client")

            _jvm_started = True
            logger.info("JVM 启动成功，影像平台 SDK 已就绪")
            return True

        except Exception as e:
            logger.error(f"JVM 启动失败: {e}")
            return False


def shutdown_jvm():
    """关闭 JVM"""
    global _jvm_started

    if not _jvm_started:
        return

    with _jvm_lock:
        try:
            import jpype

            if jpype.isJVMStarted():
                jpype.shutdownJVM()
                _jvm_started = False
                logger.info("JVM 已关闭")
        except Exception as e:
            logger.error(f"JVM 关闭失败: {e}")


def is_jvm_ready() -> bool:
    """检查 JVM 是否就绪"""
    try:
        import jpype
        return jpype.isJVMStarted() and _jvm_started
    except ImportError:
        return False


def _get_client(is_tfs: bool = False):
    """获取 Java Client 实例"""
    from jpype import JClass

    Client = JClass("com.bqd.cms.Client")
    return Client(is_tfs)


def _build_java_map(params: Optional[dict] = None):
    """将 Python dict 转为 Java HashMap"""
    from jpype import JClass

    if not params:
        return None

    HashMap = JClass("java.util.HashMap")
    java_map = HashMap()
    for key, value in params.items():
        java_map.put(str(key), str(value))
    return java_map


def download(
    save_path: str,
    busi_serial_no: str,
    system_code: str = "OL_PT",
    params: Optional[dict] = None,
    is_tfs: bool = False,
) -> str:
    """
    从影像平台下载文件

    Args:
        save_path: 本地保存目录
        busi_serial_no: 业务流水号
        system_code: 系统代码
        params: 可选过滤参数
        is_tfs: 是否贸金系统

    Returns:
        下载结果字符串
    """
    if not is_jvm_ready():
        raise RuntimeError("JVM 未启动，无法调用影像平台 SDK")

    os.makedirs(save_path, exist_ok=True)
    client = _get_client(is_tfs)
    java_map = _build_java_map(params)

    if is_tfs:
        result = client.downloadByBusiSerialNo(
            save_path, busi_serial_no, system_code, java_map, True
        )
    else:
        result = client.downloadByBusiSerialNo(
            save_path, busi_serial_no, system_code, java_map
        )

    return str(result)


def query(
    busi_serial_no: str,
    system_code: str = "OL_PT",
    params: Optional[dict] = None,
    is_tfs: bool = False,
) -> str:
    """
    查询影像平台文件信息

    Returns:
        查询结果 XML 字符串
    """
    if not is_jvm_ready():
        raise RuntimeError("JVM 未启动，无法调用影像平台 SDK")

    client = _get_client()
    java_map = _build_java_map(params)

    result = client.queryByBusiSerialNo(busi_serial_no, system_code, java_map)
    return str(result)


def upload(
    file_path: str,
    busi_serial_no: str,
    system_code: str = "OL_PT",
) -> str:
    """
    上传文件到影像平台

    Args:
        file_path: 文件或目录路径
        busi_serial_no: 业务流水号
        system_code: 系统代码

    Returns:
        上传结果字符串
    """
    if not is_jvm_ready():
        raise RuntimeError("JVM 未启动，无法调用影像平台 SDK")

    client = _get_client()
    result = client.uploadByPathAndSerialNo(file_path, busi_serial_no, system_code)
    return str(result)


def delete(
    busi_serial_no: str,
    system_code: str = "OL_PT",
    is_tfs: bool = False,
) -> str:
    """
    删除影像平台文件（逻辑删除）

    Returns:
        删除结果字符串
    """
    if not is_jvm_ready():
        raise RuntimeError("JVM 未启动，无法调用影像平台 SDK")

    client = _get_client()

    if is_tfs:
        result = client.deleteByBusiSerialNo(busi_serial_no, system_code, True)
    else:
        result = client.deleteByBusiSerialNo(busi_serial_no, system_code)

    return str(result)
