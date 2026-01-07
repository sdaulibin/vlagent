"""
Java SDK 文件下载测试类

使用 JPype 调用 Java SDK (fileUpload.jar) 下载外部系统的流水资料文件。

使用方法：
    1. 安装 JPype: uv add jpype1
    2. 确保 lib/fileUpload.jar 和 lib/ServerConfig.xml 存在
    3. 运行: uv run python tests/test_java_sdk_download.py
"""

import os
import sys
from pathlib import Path

# 获取项目根目录
BACKEND_DIR = Path(__file__).parent.parent
LIB_DIR = BACKEND_DIR / "lib"
JAR_PATH = LIB_DIR / "fileUpload.jar"
CONFIG_PATH = LIB_DIR / "ServerConfig.xml"


def check_dependencies():
    """检查依赖是否满足"""
    try:
        import jpype
        print(f"✓ JPype 版本: {jpype.__version__}")
    except ImportError:
        print("✗ JPype 未安装，请运行: uv add jpype1")
        return False
    
    if not JAR_PATH.exists():
        print(f"✗ JAR 文件不存在: {JAR_PATH}")
        return False
    print(f"✓ JAR 文件: {JAR_PATH}")
    
    if not CONFIG_PATH.exists():
        print(f"✗ 配置文件不存在: {CONFIG_PATH}")
        return False
    print(f"✓ 配置文件: {CONFIG_PATH}")
    
    return True


def init_jvm():
    """初始化 JVM"""
    import jpype
    
    if jpype.isJVMStarted():
        return True
    
    classpath = str(JAR_PATH)
    os.chdir(str(LIB_DIR))
    
    try:
        jpype.startJVM(classpath=[classpath], convertStrings=True)
        print(f"✓ JVM 已启动")
        return True
    except Exception as e:
        print(f"✗ JVM 启动失败: {e}")
        return False


def download_file(
    save_path: str,
    busi_serial_no: str,
    system_code: str = "OL_PT",
    params: dict = None,
    is_tfs: bool = False
):
    """
    下载文件
    
    Args:
        save_path: 保存目录路径
        busi_serial_no: 业务流水号
        system_code: 系统代码 (如 "OL_PT", "TFS_YW", "GX_KHZL" 等)
        params: 可选参数字典 (如 {"FILETITLE": "支票复印"})
        is_tfs: 是否为贸金系统
    
    Returns:
        str: 下载结果
    """
    import jpype
    from jpype import JClass
    
    Client = JClass("com.bqd.cms.Client")
    HashMap = JClass("java.util.HashMap")
    
    client = Client(is_tfs)
    
    java_map = None
    if params:
        java_map = HashMap()
        for key, value in params.items():
            java_map.put(key, value)
    
    os.makedirs(save_path, exist_ok=True)
    
    if is_tfs:
        result = client.downloadByBusiSerialNo(save_path, busi_serial_no, system_code, java_map, True)
    else:
        result = client.downloadByBusiSerialNo(save_path, busi_serial_no, system_code, java_map)
    
    return str(result)


def shutdown_jvm():
    """关闭 JVM"""
    import jpype
    if jpype.isJVMStarted():
        jpype.shutdownJVM()
        print("✓ JVM 已关闭")


def main():
    """测试主函数"""
    print("=" * 50)
    print("Java SDK 文件下载测试")
    print("=" * 50)
    
    if not check_dependencies():
        sys.exit(1)
    
    if not init_jvm():
        sys.exit(1)
    
    try:
        # ===== 测试参数（请根据实际情况修改）=====
        save_path = str(BACKEND_DIR / "downloads" / "test")
        busi_serial_no = "20150908_0019"  # 业务流水号
        system_code = "OL_PT"              # 系统代码
        params = {}                        # 可选参数
        is_tfs = False                     # 是否为贸金系统
        
        print(f"\n正在下载文件...")
        print(f"  保存路径: {save_path}")
        print(f"  业务流水号: {busi_serial_no}")
        print(f"  系统代码: {system_code}")
        
        result = download_file(save_path, busi_serial_no, system_code, params, is_tfs)
        print(f"  下载结果: {result}")
        
        if os.path.exists(save_path):
            files = os.listdir(save_path)
            print(f"  下载的文件: {files}" if files else "  下载目录为空")
    
    except Exception as e:
        print(f"  下载失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        shutdown_jvm()
    
    print("\n" + "=" * 50)


if __name__ == "__main__":
    main()
