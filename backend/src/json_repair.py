import re
import json

def fix_json(json_str):
    """
    更稳健的 JSON 修复函数，处理被截断的 JSON (处理未闭合的括号、引号等)
    """
    if not json_str:
        return "{}"
    
    json_str = json_str.strip()
    
    # 移除 Markdown 代码块标记包围
    if json_str.startswith("```json"):
        json_str = json_str[7:]
    elif json_str.startswith("```"):
        json_str = json_str[3:]
    if json_str.endswith("```"):
        json_str = json_str[:-3]
    
    json_str = json_str.strip()
    
    # 处理可能的循环输出导致的截断问题 (Stack-based repair)
    stack = []
    is_in_string = False
    is_escaped = False
    
    # 找到第一个出现的 { 或 [
    start_pos = -1
    for i, char in enumerate(json_str):
        if char in '{[':
            start_pos = i
            break
    
    if start_pos == -1:
        return json_str
    
    fixed_chars = []
    i = start_pos
    while i < len(json_str):
        char = json_str[i]
        
        if is_in_string:
            if is_escaped:
                fixed_chars.append(char)
                is_escaped = False
            elif char == '\\':
                fixed_chars.append(char)
                is_escaped = True
            elif char == '"':
                fixed_chars.append(char)
                is_in_string = False
            else:
                # 转义字符串内的控制字符（如 raw_text 中的换行符）
                if char == '\n':
                    fixed_chars.append('\\n')
                elif char == '\r':
                    fixed_chars.append('\\r')
                elif char == '\t':
                    fixed_chars.append('\\t')
                else:
                    fixed_chars.append(char)
        else:
            if char == '"':
                fixed_chars.append(char)
                is_in_string = True
            elif char == '{':
                fixed_chars.append(char)
                stack.append('}')
            elif char == '[':
                fixed_chars.append(char)
                stack.append(']')
            elif char == '}':
                if stack and stack[-1] == '}':
                    fixed_chars.append(char)
                    stack.pop()
                else:
                    # 意外的闭括号，跳过
                    pass
            elif char == ']':
                if stack and stack[-1] == ']':
                    fixed_chars.append(char)
                    stack.pop()
                else:
                    pass
            # 允许的字符列表，不包含可能会干扰结构的字符
            elif char in ' \n\r\t:,0123456789.truefalsenull-':
                fixed_chars.append(char)
            elif char == ',':
                # 如果逗号后面紧跟的是闭括号，或者到了字符串末尾，则移除该逗号（防止尾部逗号）
                next_content = json_str[i+1:].strip()
                if not next_content or next_content[0] in '}]':
                    pass
                else:
                    fixed_chars.append(char)
            else:
                # 其他字符可能是截断处的垃圾，或者是属性名内容（如果没在双引号内，其实应该出错，但这里为了鲁棒性先保留）
                fixed_chars.append(char)
        
        i += 1
    
    # 构建修复后的字符串
    fixed_str = "".join(fixed_chars)
    
    # 1. 修复未闭合的字符串
    if is_in_string:
        # 如果是因为转义符号结束的，补一个字符再闭合
        if fixed_str.endswith('\\'):
            fixed_str += '"'
        else:
            fixed_str += '"'
            
    # 2. 移除尾部的逗号
    fixed_str = fixed_str.strip()
    if fixed_str.endswith(','):
        fixed_str = fixed_str[:-1].strip()
        
    # 3. 闭合所有的栈
    while stack:
        fixed_str += stack.pop()
        
    return fixed_str