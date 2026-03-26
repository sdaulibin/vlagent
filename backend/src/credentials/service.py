"""
Credential extraction and recognition service.
Supports: Electronic Seal, Electronic Credential, ID Card, Bank Card, Online Banking Application, Notice of Illegal Activity.
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
    
    # Strategy 1: Grid split for dense A4 forms (Account Opening, Power of Attorney)
    DENSE_TYPES = ["account_opening_app", "power_of_attorney"]
    if credential_type in DENSE_TYPES and len(image_paths) == 1:
        tmp_split_paths = _grid_split_image(image_paths[0], rows=2, cols=2)
        final_image_paths = tmp_split_paths
        max_size = 2048 # resolution boost
    # Strategy 2: Simple horizontal split for Electronic Seal
    elif credential_type == "electronic_seal" and len(image_paths) == 1:
        tmp_split_paths = _split_multi_form_image(image_paths[0])
        final_image_paths = tmp_split_paths
        max_size = 1600
    else:
        final_image_paths = image_paths
        max_size = 1600

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
            
            return _merge_json_results(part_results)
            
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
