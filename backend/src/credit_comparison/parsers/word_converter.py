from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4


def _convert_with_soffice(source_path: Path, output_path: Path, target_path: Path) -> bool:
    """使用 LibreOffice 执行 doc 转 docx。

    这里故意只保留容器友好的实现，不依赖 Word COM。
    """

    profile_dir = output_path / ".lo_profiles" / uuid4().hex
    profile_dir.mkdir(parents=True, exist_ok=True)
    user_installation = profile_dir.resolve().as_uri()
    soffice_command = [
        "soffice",
        "--headless",
        f"-env:UserInstallation={user_installation}",
        "--convert-to",
        "docx",
        str(source_path),
        "--outdir",
        str(output_path),
    ]
    try:
        result = subprocess.run(soffice_command, capture_output=True, text=True, check=False)
        return result.returncode == 0 and target_path.exists()
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)


def build_converted_batch_dir(output_dir: str, batch_id: str) -> Path:
    """为转换结果构建批次目录。"""

    base_dir = Path(output_dir)
    normalized_batch_id = re.sub(r'[<>:"/\\|?*]+', "_", str(batch_id or "").strip()).strip(" .")
    batch_dir_name = normalized_batch_id or "_default"
    return base_dir / batch_dir_name


def convert_doc_to_docx(doc_path: str, output_dir: str, batch_id: str = "") -> str:
    """将 .doc 转换为 .docx。

    当前实现面向 Docker 运行环境，只使用 LibreOffice headless 转换。
    """

    source_path = Path(doc_path)
    output_path = build_converted_batch_dir(output_dir, batch_id)
    output_path.mkdir(parents=True, exist_ok=True)

    if source_path.suffix.lower() == ".docx":
        return str(source_path)

    target_path = output_path / f"{source_path.stem}.docx"
    if target_path.exists():
        target_path.unlink()

    if not _convert_with_soffice(source_path, output_path, target_path):
        raise RuntimeError("doc 转 docx 失败: LibreOffice 不可用或转换失败")
    return str(target_path)
