import sys
import os
import json

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.pdf_processor import deduplicate_records

def test_deduplication():
    records = [
        {"交易流水号": "ID1", "amount": 100},
        {"交易流水号": "ID1", "amount": 100}, # Duplicate by ID
        {"交易流水号": "ID2", "amount": 200},
        {"交易流水号": "", "amount": 300},
        {"交易流水号": None, "amount": 300}, # Duplicate by content hash
        {"交易流水号": "ID3", "amount": 400},
    ]
    
    result = deduplicate_records(records)
    print(f"Original: {len(records)}, Deduplicated: {len(result)}")
    for r in result:
        print(r)
    
    if len(result) == 4:
        print("Test PASSED")
    else:
        print("Test FAILED")

if __name__ == "__main__":
    test_deduplication()
