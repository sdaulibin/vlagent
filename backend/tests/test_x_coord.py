import os
import sys
from paddleocr import PaddleOCR

def find_text_coordinate(image_path: str, target_text: str = "摘要备注"):
    """
    Use PaddleOCR to find the coordinates of specific text in an image.
    
    Args:
        image_path (str): Path to the image file.
        target_text (str): Text to search for.
        
    Returns:
        dict: Coordinate info if found, else None.
    """
    if not os.path.exists(image_path):
        print(f"Error: File not found at {image_path}")
        return None

    # Initialize OCR model
    # use_angle_cls=True enables orientation classification
    # lang='ch' supports Chinese
    try:
        # show_log is not a valid init argument for PaddleOCR class, it's usually for the ocr() method or controlled via logging levels
        # use_angle_cls is deprecated, using use_textline_orientation instead logic if needed, but keeping simple for now
        # Actually show_log might be for the ocr method. Let's remove it from init.
        ocr = PaddleOCR(use_angle_cls=True, lang='ch')
    except Exception as e:
        print(f"Failed to initialize PaddleOCR: {e}")
        return None

    print(f"Scanning image: {image_path}")
    result = ocr.ocr(image_path)

    if not result:
        print("No result from OCR.")
        return None

    first_res = result[0]
    
    # Check if result is a dictionary (new API format)
    if isinstance(first_res, dict):
        rec_texts = first_res.get('rec_texts', [])
        rec_scores = first_res.get('rec_scores', [])
        dt_polys = first_res.get('dt_polys', [])
        
        if not rec_texts:
            print("No text detected in the image.")
            return None
            
        for i, text in enumerate(rec_texts):
            score = rec_scores[i] if i < len(rec_scores) else 0.0
            box = dt_polys[i] if i < len(dt_polys) else []
            
            if target_text in text:
                if len(box) >= 2:
                    x_start = float(box[0][0])
                    x_end = float(box[1][0])
                    center_x = (x_start + x_end) / 2
                    
                    info = {
                        "text": text,
                        "confidence": score,
                        "box": box,
                        "x_start": x_start,
                        "x_end": x_end,
                        "center_x": center_x
                    }
                    
                    print(f"\n[FOUND] Target: '{target_text}' matched in '{text}'")
                    print(f"  Confidence: {score:.4f}")
                    print(f"  Left X: {x_start}")
                    print(f"  Right X: {x_end}")
                    print(f"  Center X: {center_x}")
                    return info
                    
    else:
        # Fallback to legacy list format
        if first_res is None:
            print("No text detected in the image.")
            return None

        for line in first_res:
            # line structure: [box, (text, score)]
            box = line[0]
            text_info = line[1]
            
            if isinstance(text_info, (tuple, list)):
                 text = text_info[0]
                 score = text_info[1]
            else:
                 continue

            if target_text in text:
                x_start = box[0][0]
                x_end = box[1][0]
                center_x = (x_start + x_end) / 2
                
                info = {
                    "text": text,
                    "confidence": score,
                    "box": box,
                    "x_start": x_start,
                    "x_end": x_end,
                    "center_x": center_x
                }
                
                print(f"\n[FOUND] Target: '{target_text}' matched in '{text}'")
                print(f"  Confidence: {score:.4f}")
                print(f"  Left X: {x_start}")
                print(f"  Right X: {x_end}")
                print(f"  Center X: {center_x}")
                return info

    print(f"\n[NOT FOUND] Target text '{target_text}' not found in image.")
    return None



def main():
    # Use the previously uploaded image path or a default one
    # You can pass arguments via command line as well
    default_image = "/Users/binginx/PycharmProjects/vl_qingdao/res/task_5潍坊银行/images/5潍坊银行_page_003.png"
    
    if len(sys.argv) > 1:
        image_paths = sys.argv[1:]
    else:
        image_paths = [default_image]

    for img_path in image_paths:
        print("-" * 50)
        find_text_coordinate(img_path)

if __name__ == "__main__":
    main()
