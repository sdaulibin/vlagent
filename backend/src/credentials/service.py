"""
类凭证提取与识别服务

负责提取：电子印章、电子凭证、身份证、银行卡、网银申请书、违法犯罪告知书。
"""
import os
import json
import shutil
import tempfile
from typing import List, Dict, Any

from PIL import Image
from services.pdf.pdf_utils import split_pdf_to_images
from services.core.request_ai import request_qwen35
from src.json_repair import fix_json
from src.credentials.prompts import PROMPT_MAPPING

def _compress_images_for_ai(image_paths: List[str], max_size=1600, quality=85) -> List[str]:
    """压缩图片以减小 API payload 大小"""
    from services.pdf.pdf_utils import resize_image_high_quality
    
    compressed_dir = tempfile.mkdtemp(prefix="compressed_cred_")
    compressed_paths = []
    
    for i, path in enumerate(image_paths):
        out_path = os.path.join(compressed_dir, f"page_{i:03d}.jpg")
        success = resize_image_high_quality(
            path, out_path,
            max_width=max_size, max_height=max_size, quality=quality
        )
        if success:
            compressed_paths.append(out_path)
        else:
            compressed_paths.append(path)
            
    return compressed_paths

def _split_multi_form_image(image_path: str) -> List[str]:
    """
    检查图片比例，如果是长图或宽图（含有多联单据），切分后分别识别以提高精度。
    针对电子印章这种“上下堆叠”非常普遍的场景，只要高度不至于太小，就尝试切分。
    """
    try:
        with Image.open(image_path) as img:
            w, h = img.size
            print(f"[调试] 正在检查识别图片尺寸: H={h}, W={w}")
            
            # 无论 landscape 还是 portrait，只要高度占一定比例且是电子印章业务，
            # 为了解决 AI 识别多印章的惯性问题，我们默认尝试水平平分（假设大致为上下联）。
            if h > w * 0.4: 
                print(f"[调试] 该图比例 (H/W={h/w:.2f}) 可能含有上下双联，正在水平切分为两部分以提高精度...")
                tmp_dir = tempfile.mkdtemp(prefix="split_img_")
                
                # 水平对半切
                top_part = img.crop((0, 0, w, h // 2))
                top_path = os.path.join(tmp_dir, "part_top.jpg")
                top_part.convert("RGB").save(top_path, "JPEG", quality=95)
                
                bottom_part = img.crop((0, h // 2, w, h))
                bottom_path = os.path.join(tmp_dir, "part_bottom.jpg")
                bottom_part.convert("RGB").save(bottom_path, "JPEG", quality=95)
                
                return [top_path, bottom_path]
    except Exception as e:
        print(f"[警告] 图片切分失败: {e}")
    return [image_path]

def extract_fields_from_images(image_paths: List[str], credential_type: str) -> dict:
    """调用 Qwen3.5 进行特定凭证的字段提取"""
    # 针对电子印章的多单据/多联次场景进行特殊切分处理
    final_image_paths = []
    tmp_split_paths = [] 
    
    if credential_type == "electronic_seal" and len(image_paths) == 1:
        tmp_split_paths = _split_multi_form_image(image_paths[0])
        final_image_paths = tmp_split_paths
    else:
        final_image_paths = image_paths

    compressed_paths = _compress_images_for_ai(final_image_paths)
    prompt = PROMPT_MAPPING.get(credential_type)
    
    if not prompt:
        raise ValueError(f"不受支持的凭证类型: {credential_type}")

    try:
        # 如果切分成了多个部分，或者是多页PDF，则合并结果
        if len(compressed_paths) == 1:
            response = request_qwen35(
                question=prompt,
                file_base=compressed_paths[0],
                show_request=False
            ).strip()
            try:
                data = json.loads(fix_json(response))
                return data
            except Exception as e:
                print(f"[{credential_type}] JSON 解析失败: {e}, 原始响应: {response[:200]}")
                return {}
        else:
            # 对于多图/切分图，逐张识别并合并关键列表字段(如 seal_codes)
            merged_result = {"header": "", "seal_codes": []}
            all_fields = {} # 通用容器
            
            for path in compressed_paths:
                resp = request_qwen35(
                    question=prompt,
                    file_base=path,
                    show_request=False
                ).strip()
                try:
                    part_data = json.loads(fix_json(resp))
                    # 合并 header (取第一个非空的)
                    if not merged_result.get("header") and part_data.get("header"):
                        merged_result["header"] = part_data["header"]
                    
                    # 合并列表字段 (针对电子印章)
                    if "seal_codes" in part_data and isinstance(part_data["seal_codes"], list):
                        for code in part_data["seal_codes"]:
                            if code and code not in merged_result["seal_codes"]:
                                merged_result["seal_codes"].append(code)
                    
                    # 记录其他字段 (覆盖式合并)
                    all_fields.update(part_data)
                except:
                    continue
            
            # 如果是电子印章，优先返回合并后的结构
            if credential_type == "electronic_seal":
                return merged_result
            
            # 其他类型（如长图身份证？）也合并
            all_fields.update(merged_result)
            return all_fields
            
    finally:
        # 清理所有临时目录
        all_dirs_to_clean = set()
        for p in compressed_paths + tmp_split_paths:
            d = os.path.dirname(p)
            if d and d.startswith(tempfile.gettempdir()) and "cred_process_" not in d:
                all_dirs_to_clean.add(d)
        
        for d in all_dirs_to_clean:
            shutil.rmtree(d, ignore_errors=True)

def process_credential(file_path: str, credential_type: str) -> Dict[str, Any]:
    """
    处理凭证文件 (PDF或图片)，提取结构化字段。
    """
    tmp_dir = tempfile.mkdtemp(prefix="cred_process_")
    
    try:
        # 支持 PDF 转化为图片，若本身是图片则处理一下
        ext = os.path.splitext(file_path)[-1].lower()
        if ext == '.pdf':
            image_paths = split_pdf_to_images(file_path, tmp_dir, dpi=200)
            if not image_paths:
                raise ValueError("PDF 转换图片失败，未生成任何图片")
        else:
            # 如果是单张图片，直接使用原图路径
            image_paths = [file_path]
            
        result = extract_fields_from_images(image_paths, credential_type)
        
        # 打印识别结果以供查看
        print(f"\n[凭证识别结果 - {credential_type}] -> {json.dumps(result, ensure_ascii=False)}")
        
        return {
            "credential_type": credential_type,
            "extracted_data": result
        }
    finally:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
