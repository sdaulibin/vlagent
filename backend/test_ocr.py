from src.confirmation_letter.service import extract_fields_from_images

def run():
    res = extract_fields_from_images(["/Users/binginx/.gemini/antigravity/brain/8272da08-42b4-4c67-8d74-184628a60cac/media__1773379553423.png"])
    raw = res.get("raw_text", "")
    import re
    print("ALL DATES IN RAW TEXT:")
    print(re.findall(r"2025.*?日", raw))
    print("seal_date:", res.get("seal_date"))

if __name__ == '__main__':
    run()
