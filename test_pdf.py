import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from src.native_statement.parser import parse_native_pdf

print("Testing parse_native_pdf against 3莱商银行.pdf")
result = parse_native_pdf("backend/res/3莱商银行.pdf")
if "error" in result:
    print(f"Error: {result['error']}")
else:
    headers = result.get("headers", [])
    for idx, tx in enumerate(result.get("transactions", [])[:5]):
        print(f"--- Transaction {idx} ---")
        for field in headers:
            val = tx.get(field, "")
            if val:
                print(f"{field}: {repr(val)}")
