import sys
import os
import json

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.json_repir import fix_json

def test_truncation():
    test_cases = [
        # Case 1: Truncated string
        ('{"key": "value', '{"key": "value"}'),
        # Case 2: Truncated object
        ('{"key": {"inner": "val"', '{"key": {"inner": "val"}}'),
        # Case 3: Truncated array
        ('[{"a": 1}, {"a": 2', '[{"a": 1}, {"a": 2}]'),
        # Case 4: Truncated with tailing comma
        ('{"a": 1, "b": 2,', '{"a": 1, "b": 2}'),
        # Case 5: Markdown wrapper
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        # Case 6: Complex nested truncation
        ('{"list": [{"id": 1, "data": "someth', '{"list": [{"id": 1, "data": "someth"}]}'),
        # Case 7: Truncated mid-value
        ('{"key1": "val1", "key2": "trunc', '{"key1": "val1", "key2": "trunc"}'), 
        # Case 8: Escaped quotes truncation
        ('{"text": "He said \\"hello', '{"text": "He said \\"hello"}')
    ]

    for i, (input_str, expected) in enumerate(test_cases):
        result = fix_json(input_str)
        try:
            parsed = json.loads(result)
            print(f"Test case {i+1} PASSED: {result}")
        except Exception as e:
            print(f"Test case {i+1} FAILED: {result}")
            print(f"Error: {e}")

if __name__ == "__main__":
    test_truncation()
