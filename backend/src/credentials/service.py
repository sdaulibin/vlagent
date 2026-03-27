"""
Credential extraction and recognition service.
Supports: Electronic Seal, Electronic Credential, ID Card, Bank Card, Online Banking Application, Notice of Illegal Activity.
"""
import os
import json
import re
import shutil
import tempfile
from typing import List, Dict, Any

from PIL import Image
from services.pdf.pdf_utils import split_pdf_to_images
from services.core.request_ai import request_qwen35
from src.json_repair import fix_json
from src.credentials.prompts import PROMPT_MAPPING


def _post_process_boolean_fields(data: dict, credential_type: str) -> dict:
    """
    后处理 Boolean 字段，针对开户申请书和授权委托书中的勾选字段进行二次校验和修正

    规则：
    1. 如果字符串值看起来像 "X" 或 "×" 标记，转换为 false
    2. 清理可能的误识别
    """
    if credential_type not in ["account_opening_app", "power_of_attorney"]:
        return data

    boolean_field_patterns = {
        "account_opening_app": [
            "open_online_banking", "open_mobile_banking", "open_sms_notice",
            "open_phone_reconciliation", "open_official_web_reconciliation"
        ],
        "power_of_attorney": ["is_employee"]
    }

    fields_to_check = boolean_field_patterns.get(credential_type, [])

    for field in fields_to_check:
        if field in data:
            value = data[field]
            # 如果是字符串，检查是否包含 X/× 标记
            if isinstance(value, str):
                # 检查是否是叉号标记
                if re.search(r'^[×xX]$', value.strip()):
                    data[field] = False
                elif value.lower() in ["false", "no", "否", "未勾选", "×", "x"]:
                    data[field] = False
                elif value.lower() in ["true", "yes", "是", "√", "勾选"]:
                    data[field] = True
                else:
                    # 无法确定，保持原值或默认 false
                    data[field] = bool(value) if isinstance(value, bool) else False

    return data


def _post_process_authorized_items(data: dict, credential_type: str) -> dict:
    """
    后处理授权委托书的授权事项（四类分组结构）

    处理逻辑：
    1. opening（开户类）、change（变更类）、cancellation（注销类）：
       - 确保返回所有已知项目及其勾选状态
       - 使用白名单过滤非标准项目名称
    2. other（其他业务）：按逗号/顿号/空格分隔，识别手写或机打的任意内容
    """
    if credential_type != "power_of_attorney":
        return data

    # 获取四类分组的原始数据
    raw_categories = data.get("authorized_items_by_category", {})
    if not isinstance(raw_categories, dict):
        raw_categories = {}

    # 【标准项目定义】每类业务的所有已知项目（按顺序，与prompts.py完全一致）
    STANDARD_ITEMS = {
        "opening": [
            "账户开户",
            "企业网上银行注册",
            "企业手机银行注册",
            "企业短信通知注册",
            "签署税收居民身份声明文件",
        ],
        "change": [
            "账户信息变更",
            "预留印鉴变更",
            "公章变更",
            "企业网上银行变更",
            "企业短信通知变更",
            "企业手机银行变更",
        ],
        "cancellation": [
            "账户销户",
            "企业网上银行注销",
            "企业手机银行注销",
            "企业短信通知注销",
        ],
    }

    # 【名称标准化】处理各种变体（包含更多变体形式）
    NAME_MAPPING = {
        # 开户类
        "账户开户": "账户开户",
        "企业网上银行注册": "企业网上银行注册",
        "企业网上银行": "企业网上银行注册",
        "网银注册": "企业网上银行注册",
        "企业手机银行注册": "企业手机银行注册",
        "企业手机银行": "企业手机银行注册",
        "手机银行注册": "企业手机银行注册",
        "企业短信通知注册": "企业短信通知注册",
        "企业短信通知": "企业短信通知注册",
        "短信通知注册": "企业短信通知注册",
        "签署税收居民身份声明文件": "签署税收居民身份声明文件",
        "税收居民身份声明文件": "签署税收居民身份声明文件",
        "税收居民身份声明": "签署税收居民身份声明文件",
        "签署税收居民身份声明": "签署税收居民身份声明文件",
        # 变更类
        "账户信息变更": "账户信息变更",
        "预留印鉴变更": "预留印鉴变更",
        "印鉴变更": "预留印鉴变更",
        "公章变更": "公章变更",
        "企业网上银行变更": "企业网上银行变更",
        "网银变更": "企业网上银行变更",
        "企业短信通知变更": "企业短信通知变更",
        "短信通知变更": "企业短信通知变更",
        "企业手机银行变更": "企业手机银行变更",
        "手机银行变更": "企业手机银行变更",
        # 注销类
        "账户销户": "账户销户",
        "销户": "账户销户",
        "企业网上银行注销": "企业网上银行注销",
        "网银注销": "企业网上银行注销",
        "企业手机银行注销": "企业手机银行注销",
        "手机银行注销": "企业手机银行注销",
        "企业短信通知注销": "企业短信通知注销",
        "短信通知注销": "企业短信通知注销",
    }

    result = {
        "opening": [],
        "change": [],
        "cancellation": [],
        "other": [],
    }

    # 处理三类已知业务
    for category in ["opening", "change", "cancellation"]:
        raw_items = raw_categories.get(category, [])
        if not isinstance(raw_items, list):
            raw_items = []

        standard_names = set(STANDARD_ITEMS[category])
        # 从模型结果中提取已勾选的项目
        checked_names = set()

        for item in raw_items:
            if isinstance(item, dict):
                # 新格式：{"name": "xxx", "checked": true/false}
                name = item.get("name", "")
                checked = item.get("checked", False)
                if name and isinstance(name, str):
                    normalized = NAME_MAPPING.get(name.strip(), name.strip())
                    if normalized in standard_names and checked:
                        checked_names.add(normalized)
            elif isinstance(item, str):
                # 旧格式兼容：纯字符串表示已勾选
                normalized = NAME_MAPPING.get(item.strip(), item.strip())
                if normalized in standard_names:
                    checked_names.add(normalized)

        # 生成完整的标准列表（包含所有项目及其勾选状态）
        for name in STANDARD_ITEMS[category]:
            result[category].append({
                "name": name,
                "checked": name in checked_names
            })

    # 处理"其他业务"（按分隔符拆分，包括空格）
    raw_other = raw_categories.get("other", [])
    if not isinstance(raw_other, list):
        raw_other = []

    other_items = []
    for item in raw_other:
        if isinstance(item, dict):
            # 如果是对象格式，提取内容
            content = item.get("name", "") or item.get("content", "")
            if content:
                # 按多种分隔符分隔（包括中文和英文标点）
                parts = re.split(r'[,，、;；\s\n\r]+', str(content))
                for part in parts:
                    part = part.strip()
                    if part and len(part) > 1 and part not in other_items:
                        other_items.append(part)
        elif isinstance(item, str) and item.strip():
            # 按多种分隔符分隔（包括中文和英文标点）
            parts = re.split(r'[,，、;；\s\n\r]+', item)
            for part in parts:
                part = part.strip()
                if part and len(part) > 1 and part not in other_items:
                    other_items.append(part)

    # 【新增】如果 other_items 为空，尝试从原始数据中查找可能遗漏的内容
    # 检查是否有类似"其他"的键
    if not other_items:
        for key in raw_categories:
            if "其他" in str(key) or "other" in str(key).lower():
                extra_content = raw_categories.get(key, "")
                if isinstance(extra_content, str) and extra_content.strip():
                    parts = re.split(r'[,，、;；\s\n\r]+', extra_content)
                    for part in parts:
                        part = part.strip()
                        if part and len(part) > 1 and part not in other_items:
                            other_items.append(part)

    result["other"] = other_items

    # 更新数据
    data["authorized_items_by_category"] = result
    print(f"[DEBUG] Post-processed authorized_items_by_category: {result}")

    return data

def _compress_images_for_ai(image_paths: List[str], max_size=1600, quality=85) -> List[str]:
    """Compress images to reduce API payload size."""
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

def _grid_split_image(image_path: str, rows=2, cols=2) -> List[str]:
    """Split an A4 form into a grid (e.g., 2x2) for higher precision recognition."""
    try:
        with Image.open(image_path) as img:
            w, h = img.size
            print(f"[DEBUG] Grid splitting dense form ({rows}x{cols}), original size: {w}x{h}")
            tmp_dir = tempfile.mkdtemp(prefix="grid_split_")
            split_paths = []
            
            dw = w // cols
            dh = h // rows
            
            for r in range(rows):
                for c in range(cols):
                    left = c * dw
                    top = r * dh
                    right = (c + 1) * dw if c < cols - 1 else w
                    bottom = (r + 1) * dh if r < rows - 1 else h
                    
                    part = img.crop((left, top, right, bottom))
                    part_path = os.path.join(tmp_dir, f"part_{r}_{c}.jpg")
                    part.convert("RGB").save(part_path, "JPEG", quality=95)
                    split_paths.append(part_path)
            return split_paths
    except Exception as e:
        print(f"[WARNING] Grid split failed: {e}")
    return [image_path]

def _split_multi_form_image(image_path: str) -> List[str]:
    """Split electronic seal documents (multi-part forms) for higher precision."""
    try:
        with Image.open(image_path) as img:
            w, h = img.size
            if h > w * 0.4: 
                print(f"[DEBUG] Image ratio (H/W={h/w:.2f}) suggests multi-part form, spliting horizontally...")
                tmp_dir = tempfile.mkdtemp(prefix="split_img_")
                
                # Split in half horizontally
                top_part = img.crop((0, 0, w, h // 2))
                top_path = os.path.join(tmp_dir, "part_top.jpg")
                top_part.convert("RGB").save(top_path, "JPEG", quality=95)
                
                bottom_part = img.crop((0, h // 2, w, h))
                bottom_path = os.path.join(tmp_dir, "part_bottom.jpg")
                bottom_part.convert("RGB").save(bottom_path, "JPEG", quality=95)
                
                return [top_path, bottom_path]
    except Exception as e:
        print(f"[WARNING] Image split failed: {e}")
    return [image_path]

def _merge_json_results(results: List[dict]) -> dict:
    """Merge recognition results from multiple tiles with conflict handling."""
    if not results: return {}
    final_data = {}
    for res in results:
        if not isinstance(res, dict): continue
        for k, v in res.items():
            if k not in final_data or not final_data[k]:
                final_data[k] = v
            else:
                # Conflict: if boolean, True wins
                if isinstance(v, bool):
                    if v is True: final_data[k] = True
                # Conflict: if list, unique list items
                elif isinstance(v, list) and isinstance(final_data[k], list):
                    for item in v:
                        if item and item not in final_data[k]:
                            final_data[k].append(item)
                # Conflict: if string, take the longer one
                elif isinstance(v, str) and isinstance(final_data[k], str):
                    if len(v) > len(final_data[k]):
                        final_data[k] = v
    return final_data

def extract_fields_from_images(image_paths: List[str], credential_type: str) -> dict:
    """Call AI to extract fields from document images."""
    final_image_paths = []
    tmp_split_paths = []

    # Strategy 1: Grid split for dense A4 forms (Account Opening only - NOT Power of Attorney)
    DENSE_TYPES = ["account_opening_app"]  # 移除 power_of_attorney
    if credential_type in DENSE_TYPES and len(image_paths) == 1:
        tmp_split_paths = _grid_split_image(image_paths[0], rows=2, cols=2)
        final_image_paths = tmp_split_paths
        max_size = 2048 # resolution boost
    # Strategy 2: Simple horizontal split for Electronic Seal
    elif credential_type == "electronic_seal" and len(image_paths) == 1:
        tmp_split_paths = _split_multi_form_image(image_paths[0])
        final_image_paths = tmp_split_paths
        max_size = 1600
    # Strategy 3: Power of Attorney - high resolution, no split
    elif credential_type == "power_of_attorney" and len(image_paths) == 1:
        final_image_paths = image_paths
        max_size = 2048  # 提升分辨率
        quality = 95     # 提升质量
    else:
        final_image_paths = image_paths
        max_size = 1600

    # 根据凭证类型调整压缩质量
    if credential_type == "power_of_attorney":
        compressed_paths = _compress_images_for_ai(final_image_paths, max_size=max_size, quality=95)
    else:
        compressed_paths = _compress_images_for_ai(final_image_paths, max_size=max_size)
    prompt = PROMPT_MAPPING.get(credential_type)

    if not prompt:
        raise ValueError(f"Unsupported credential type: {credential_type}")

    try:
        # Single image case
        if len(compressed_paths) == 1:
            response = request_qwen35(
                question=prompt,
                file_base=compressed_paths[0],
                show_request=False
            ).strip()
            try:
                data = json.loads(fix_json(response))
                # 后处理 Boolean 字段
                data = _post_process_boolean_fields(data, credential_type)
                # 后处理授权事项列表
                data = _post_process_authorized_items(data, credential_type)
                return data
            except Exception as e:
                print(f"[{credential_type}] JSON parse failed: {e}")
                return {}
        else:
            # Multi-tile case, merge results
            part_results = []
            for path in compressed_paths:
                resp = request_qwen35(
                    question=prompt,
                    file_base=path,
                    show_request=False
                ).strip()
                try:
                    part_results.append(json.loads(fix_json(resp)))
                except:
                    continue

            merged = _merge_json_results(part_results)
            # 后处理 Boolean 字段
            merged = _post_process_boolean_fields(merged, credential_type)
            # 后处理授权事项列表
            merged = _post_process_authorized_items(merged, credential_type)
            return merged

    finally:
        # Clean temporary directories
        all_dirs_to_clean = set()
        for p in compressed_paths + tmp_split_paths:
            d = os.path.dirname(p)
            if d and d.startswith(tempfile.gettempdir()) and ("grid_split_" in d or "compressed_cred_" in d or "split_img_" in d):
                all_dirs_to_clean.add(d)

        for d in all_dirs_to_clean:
            shutil.rmtree(d, ignore_errors=True)

def process_credential(file_path: str, credential_type: str) -> Dict[str, Any]:
    """Process PDF or image to extract structured fields."""
    tmp_dir = tempfile.mkdtemp(prefix="cred_process_")
    
    try:
        ext = os.path.splitext(file_path)[-1].lower()
        if ext == '.pdf':
            image_paths = split_pdf_to_images(file_path, tmp_dir, dpi=200)
            if not image_paths:
                raise ValueError("PDF conversion failed")
        else:
            image_paths = [file_path]
            
        result = extract_fields_from_images(image_paths, credential_type)
        
        print(f"\n[Recognition Result - {credential_type}] -> {json.dumps(result, ensure_ascii=False)}")
        
        return {
            "credential_type": credential_type,
            "extracted_data": result
        }
    finally:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
