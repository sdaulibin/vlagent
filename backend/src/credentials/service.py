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

from PIL import Image, ImageEnhance, ImageFilter
from services.pdf.pdf_utils import split_pdf_to_images
from services.core.request_ai import request_qwen35, ai_semaphore
from src.json_repair import fix_json
from src.credentials.prompts import PROMPT_MAPPING, SEAL_CODE_VERIFY_PROMPT, ELECTRONIC_SEAL_PROMPT


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

    # 【调试】打印AI返回的原始数据
    print(f"[DEBUG] AI返回的原始 authorized_items_by_category: {data.get('authorized_items_by_category', {})}")

    # 获取四类分组的原始数据
    raw_categories = data.get("authorized_items_by_category", {})
    if not isinstance(raw_categories, dict):
        raw_categories = {}

    # 【统计】记录模型返回的勾选情况
    total_items = 0
    checked_items = 0
    for category in ["opening", "change", "cancellation"]:
        raw_items = raw_categories.get(category, [])
        if isinstance(raw_items, list):
            for item in raw_items:
                if isinstance(item, dict):
                    total_items += 1
                    if item.get("checked", False):
                        checked_items += 1

    print(f"[DEBUG] 授权事项统计: 总计 {total_items} 项, 已勾选 {checked_items} 项")

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

    # 【类别边界一致性检查】
    # 模型在类别边界处易将最后一项的方框与下一类首项方框混淆，导致结果反转。
    # 特征：某类别仅最后一项被勾选，其余全部未勾选——这几乎不可能是真实填写模式。
    for category in ["opening", "change", "cancellation"]:
        items = result[category]
        if len(items) < 2:
            continue
        checked_count = sum(1 for it in items if it.get("checked", False))
        if checked_count == 1 and items[-1].get("checked", False):
            items[-1]["checked"] = False
            print(f"[DEBUG] 边界一致性修正: {category} 最后一项 '{items[-1]['name']}' 由 checked→unchecked (类别内仅末项被勾选，疑似边界错配)")

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


def _enhance_for_handwriting(image_path: str, output_path: str) -> bool:
    """增强手写文字图像：提高对比度、锐化边缘、灰度化。
    用于违法犯罪告知书等包含手写数字/日期的凭证类型，帮助 OCR 更准确识别。"""
    try:
        img = Image.open(image_path)
        img = img.convert("L")
        img = ImageEnhance.Contrast(img).enhance(1.5)
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Brightness(img).enhance(1.1)
        img.convert("RGB").save(output_path, "JPEG", quality=95)
        return True
    except Exception as e:
        print(f"  [图像增强] 失败: {e}")
        return False


def _luhn_check(number: str) -> bool:
    """Luhn 校验算法，用于验证银行卡号是否有效。"""
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 2:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _fix_bank_account(bank_account: str) -> str:
    """用 Luhn 校验修正手写银行卡号中常见的 OCR 错误。"""
    digits = re.sub(r'\D', '', bank_account)
    if not digits:
        return bank_account
    if _luhn_check(digits):
        return digits
    for i in range(len(digits)):
        if digits[i] == '7':
            candidate = digits[:i] + '1' + digits[i:]
            if _luhn_check(candidate):
                print(f"  [银行卡号修正] {bank_account} -> {candidate} (在位置{i}的7前插入1, Luhn通过)")
                return candidate
    for i in range(len(digits)):
        candidate = digits[:i+1] + '1' + digits[i+1:]
        if _luhn_check(candidate):
            print(f"  [银行卡号修正] {bank_account} -> {candidate} (在位置{i}后插入1, Luhn通过)")
            return candidate
    print(f"  [银行卡号修正] 无法通过Luhn修正: {bank_account}")
    return bank_account


def _compress_images_for_ai(image_paths: List[str], output_dir: str, max_size=1600, quality=85) -> List[str]:
    """Compress images to reduce API payload size."""
    from services.pdf.pdf_utils import resize_image_high_quality

    compressed_paths = []

    for i, path in enumerate(image_paths):
        out_path = os.path.join(output_dir, f"page_{i:03d}.jpg")
        success = resize_image_high_quality(
            path, out_path,
            max_width=max_size, max_height=max_size, quality=quality
        )
        if success:
            compressed_paths.append(out_path)
        else:
            compressed_paths.append(path)

    return compressed_paths

def _grid_split_image(image_path: str, output_dir: str, rows=2, cols=2) -> List[str]:
    """Split an A4 form into a grid (e.g., 2x2) for higher precision recognition."""
    try:
        with Image.open(image_path) as img:
            w, h = img.size
            print(f"[DEBUG] Grid splitting dense form ({rows}x{cols}), original size: {w}x{h}")
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
                    part_path = os.path.join(output_dir, f"part_{r}_{c}.jpg")
                    part.convert("RGB").save(part_path, "JPEG", quality=95)
                    split_paths.append(part_path)
            return split_paths
    except Exception as e:
        print(f"[WARNING] Grid split failed: {e}")
    return [image_path]

def _auto_rotate_if_needed(img: Image.Image) -> Image.Image:
    """检测印章编码是否倒立，如果是则旋转180度。
    通过检测印章周围的关键文字方向来判断：如果"业务受理章"等文字是倒立的，说明印章是倒的。
    简化方案：对每个切片生成一个正向和180度旋转版本，都用一次快速AI调用判断哪个方向正确。
    """
    import numpy as np
    try:
        # 简单启发式：印章编码通常在图片下半部分
        # 如果下半部分有大量深色像素（印章本身是红色/深色），
        # 说明印章可能是正的；如果上半部分有，可能需要旋转
        w, h = img.size
        arr = np.array(img.convert('L'))
        
        # 计算上半和下半的深色像素密度
        mid = h // 2
        top_density = np.mean(arr[:mid, :] < 128)
        bottom_density = np.mean(arr[mid:, :] < 128)
        
        # 如果顶部深色密度远大于底部，图片可能需要旋转
        if top_density > bottom_density * 1.5:
            print(f"  [自动旋转] 检测到印章可能倒立 (top={top_density:.3f}, bot={bottom_density:.3f})，旋转180度")
            return img.rotate(180, expand=True)
    except Exception as e:
        print(f"  [自动旋转] 检测失败: {e}")
    return img


def _split_multi_form_image(image_path: str, output_dir: str) -> List[str]:
    """Split electronic seal documents (multi-part forms) for higher precision."""
    try:
        with Image.open(image_path) as img:
            w, h = img.size
            if h > w * 0.4:
                print(f"[DEBUG] Image ratio (H/W={h/w:.2f}) suggests multi-part form, spliting horizontally...")

                # Split in half horizontally
                top_part = _auto_rotate_if_needed(img.crop((0, 0, w, h // 2)))
                top_path = os.path.join(output_dir, "part_top.jpg")
                top_part.convert("RGB").save(top_path, "JPEG", quality=95)

                bottom_part = _auto_rotate_if_needed(img.crop((0, h // 2, w, h)))
                bottom_path = os.path.join(output_dir, "part_bottom.jpg")
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


def _verify_seal_codes(data: dict, credential_type: str, image_paths: list[str] | str | None) -> dict:
    """对电子印章编码进行核验：清理分隔符，并对每个tile旋转180度重新提取以改善识别。"""
    if credential_type != "electronic_seal":
        return data
    
    # Normalize to list
    if image_paths is None:
        return data
    if isinstance(image_paths, str):
        image_paths = [image_paths]
    
    seal_codes = data.get("seal_codes", [])
    if not seal_codes:
        return data

    # Step 1: Clean dashes/spaces
    seal_codes = [c.replace("-", "").replace(" ", "") for c in seal_codes]
    print(f"  [印章核验] 原始编码(清理后): {seal_codes}")

    # Step 2: 对每个tile旋转180度重新提取
    from PIL import Image
    rotated_results = []
    for tile_path in image_paths:
        try:
            img = Image.open(tile_path)
            rotated_img = img.rotate(180, expand=True)
            rotated_path = tile_path.rsplit(".", 1)[0] + "_rotated.jpg"
            rotated_img.save(rotated_path, "JPEG", quality=95)

            resp = request_qwen35(
                question=ELECTRONIC_SEAL_PROMPT,
                file_base=rotated_path,
                show_request=False,
            ).strip()
            rotated_data = json.loads(fix_json(resp))
            codes = rotated_data.get("seal_codes", [])
            codes = [c.replace("-", "").replace(" ", "") for c in codes]
            print(f"  [印章核验] tile {tile_path} 旋转提取: {codes}")
            rotated_results.extend(codes)

            try:
                os.unlink(rotated_path)
            except:
                pass
        except Exception as e:
            print(f"  [印章核验] tile旋转提取失败: {e}")

    # Step 3: 合并 - 对每个位置取原始和旋转中最长的
    if not rotated_results:
        data["seal_codes"] = seal_codes
        return data

    n = len(seal_codes)
    # 如果旋转结果数量匹配，一一对应取最长
    if len(rotated_results) >= n:
        final = []
        for i in range(n):
            orig = seal_codes[i] if i < len(seal_codes) else ""
            rot = rotated_results[i] if i < len(rotated_results) else ""
            best = rot if len(rot) >= len(orig) else orig  # 优先旋转结果（旋转提取通常更准确）
            print(f"  [印章核验] 位置{i}: 原始={orig}({len(orig)}字符) vs 旋转={rot}({len(rot)}字符) -> {best}")
            final.append(best)
        data["seal_codes"] = final
    else:
        # 旋转结果不够，用全局策略：收集所有候选，按长度排序取前N
        all_codes = list(seal_codes) + rotated_results
        unique = list(dict.fromkeys(all_codes))
        by_length = sorted(unique, key=lambda c: len(c), reverse=True)
        final = by_length[:n]
        print(f"  [印章核验] 全局候选: {all_codes}, 选取: {final}")
        data["seal_codes"] = final

    print(f"  [印章核验] 最终结果: {data['seal_codes']}")
    return data


def extract_fields_from_images(image_paths: List[str], credential_type: str) -> dict:
    """Call AI to extract fields from document images."""
    with tempfile.TemporaryDirectory(prefix="cred_work_") as work_dir:
        final_image_paths = []

        # Strategy 1: Account Opening - full image at high resolution (grid splitting caused field mixing/truncation)
        if credential_type == "account_opening_app" and len(image_paths) == 1:
            final_image_paths = image_paths
            max_size = 3072
        # Strategy 2: Electronic Seal - split + high resolution for small seal code text
        elif credential_type == "electronic_seal" and len(image_paths) == 1:
            final_image_paths = _split_multi_form_image(image_paths[0], work_dir)
            max_size = 3072
        # Strategy 3: Power of Attorney - higher resolution to preserve small checkbox symbols
        elif credential_type == "power_of_attorney" and len(image_paths) == 1:
            final_image_paths = image_paths
            max_size = 3072
        # Strategy 4: Illegal activity notice - high resolution + handwriting enhancement
        elif credential_type == "notice_illegal_activity":
            final_image_paths = image_paths
            max_size = 3072
            enhanced_dir = os.path.join(work_dir, "enhanced")
            os.makedirs(enhanced_dir, exist_ok=True)
            enhanced_paths = []
            for idx, p in enumerate(final_image_paths):
                ep = os.path.join(enhanced_dir, f"enhanced_{idx:03d}.jpg")
                if _enhance_for_handwriting(p, ep):
                    enhanced_paths.append(ep)
                else:
                    enhanced_paths.append(p)
            final_image_paths = enhanced_paths
        else:
            final_image_paths = image_paths
            max_size = 1600

        # 根据凭证类型调整压缩质量
        compress_dir = os.path.join(work_dir, "compressed")
        os.makedirs(compress_dir, exist_ok=True)
        if credential_type in ("power_of_attorney", "account_opening_app", "electronic_seal", "notice_illegal_activity"):
            compressed_paths = _compress_images_for_ai(final_image_paths, compress_dir, max_size=max_size, quality=95)
        else:
            compressed_paths = _compress_images_for_ai(final_image_paths, compress_dir, max_size=max_size)
        prompt = PROMPT_MAPPING.get(credential_type)

        if not prompt:
            raise ValueError(f"Unsupported credential type: {credential_type}")

        # Single image case
        if len(compressed_paths) == 1:
            response = request_qwen35(
                question=prompt,
                file_base=compressed_paths[0],
                show_request=False
            ).strip()
            try:
                data = json.loads(fix_json(response))
                data = _post_process_boolean_fields(data, credential_type)
                data = _post_process_authorized_items(data, credential_type)
                # 银行卡号 Luhn 校验修正（手写"17"→"7"等常见OCR错误）
                if credential_type == "notice_illegal_activity" and data.get("bank_account"):
                    data["bank_account"] = _fix_bank_account(data["bank_account"])
                data = _verify_seal_codes(data, credential_type, compressed_paths)
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
            merged = _post_process_boolean_fields(merged, credential_type)
            merged = _post_process_authorized_items(merged, credential_type)
            if credential_type == "notice_illegal_activity" and merged.get("bank_account"):
                merged["bank_account"] = _fix_bank_account(merged["bank_account"])
            merged = _verify_seal_codes(merged, credential_type, compressed_paths)
            return merged

def process_credential(file_path: str, credential_type: str) -> Dict[str, Any]:
    """Process PDF or image to extract structured fields."""
    with tempfile.TemporaryDirectory(prefix="cred_process_") as tmp_dir:
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


async def process_credential_async(record_id: int):
    """
    后台任务处理凭证提取。

    三段式：在调用 AI 期间不持有 DB 连接，避免压测时连接池耗尽。
    """
    import asyncio
    import time
    from src.database import SessionLocal
    from src.credentials.models import CredentialRecord, CredentialResult

    # 阶段 1：标记 processing，立刻释放连接
    async with SessionLocal() as db:
        record = await db.get(CredentialRecord, record_id)
        if not record:
            return
        file_path = record.file_path
        credential_type = record.credential_type
        record.status = "processing"
        record.error_msg = None
        await db.commit()

    start_time = time.time()

    # 阶段 2：纯外部 IO，不持有任何 DB 连接
    try:
        async with ai_semaphore():
            result = await asyncio.to_thread(process_credential, file_path, credential_type)
    except Exception as e:
        duration = time.time() - start_time
        async with SessionLocal() as db:
            record = await db.get(CredentialRecord, record_id)
            if record:
                record.status = "failed"
                record.error_msg = str(e)
                record.processing_duration = round(duration, 2)
                await db.commit()
        return

    # 阶段 3：回写结果
    duration = time.time() - start_time
    async with SessionLocal() as db:
        record = await db.get(CredentialRecord, record_id)
        if not record:
            return

        cred_result = CredentialResult(
            record_id=record.id,
            user_id=record.user_id,
            credential_type=result["credential_type"],
            extracted_data=json.dumps(result["extracted_data"], ensure_ascii=False),
        )
        db.add(cred_result)

        record.status = "done"
        record.processing_duration = round(duration, 2)
        await db.commit()
