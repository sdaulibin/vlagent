import os
import json
import concurrent.futures
from src.config import MODEL_LOCAL
from services.core.request_ai import request_stream
from src.json_repir import fix_json

# Schema 配置文件路径
SCHEMA_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "schemas.json")

def load_schema(schema_name: str):
    """
    从配置文件加载指定的 schema
    
    Args:
        schema_name: schema 名称，如 "bank_transaction", "bank_summary"
        
    Returns:
        str: JSON schema 字符串
    """
    if os.path.exists(SCHEMA_CONFIG_PATH):
        with open(SCHEMA_CONFIG_PATH, 'r', encoding='utf-8') as f:
            schemas = json.load(f)
            return json.dumps(schemas.get(schema_name, {}), ensure_ascii=False)
    return "{}"

def get_summary_column_x(file_path):
    """
    获取图片中"摘要备注"表头所在的x坐标
    """
    prompt = """
    请识别下图中交易明细表格中“摘要”或者“备注”这一列列头文字中心点的x坐标。
    如果你看到了“摘要”或者“备注”字样，请返回它的横向中心坐标值（0-1000之间）。
    只需返回 JSON 格式：{"x": "坐标值"}。严禁输出其他文字。
    """
    response = request_stream(question=prompt, file_base=file_path, model=MODEL_LOCAL).strip()
    try:
        data = json.loads(fix_json(response))
        return data
    except:
        return {"x": "700"} # 默认兜底

def get_real_x_coordinate(file_path, image_path):
    """
    获取"摘要备注"列的真实x坐标位置
    """
    from PIL import Image
    ai_res = get_summary_column_x(file_path)
    try:
        x_percent = int(ai_res.get("x", 700))
        with Image.open(image_path) as img:
            width, _ = img.size
            real_x = int((x_percent / 1000) * width)
            return real_x
    except:
        return 700

def read_data_with_schema(file_path, schema: list, bank_type: str = "shandong_local"):
    """
    使用指定的 schema 从图片中提取交易明细数据
    """
    result_schema = json.dumps(schema, ensure_ascii=False)
    
    if bank_type == "everbright":
        prompt = f"""
        你是银行流水OCR专家，请从光大银行对公账户对账单中提取交易明细数据。
        
        【列顺序 - 从左到右，共11列】
        序号 | 交易日期 | 时间 | 借/贷 | 交易金额 | 账户余额 | 对方账号 | 对方名称 | 凭证号 | 摘要 | 流水号
        
        【关键！各列内容特征】
        1. **凭证号**（第9列）：
           - 这一列**大部分情况下为空**
           - 只有银行系统填写的凭证编号才属于此列
           - 如果该区域没有内容，必须填空字符串 ""
        
        2. **摘要**（第10列）：
           - 这一列包含**交易描述信息**
           - 典型内容例如："转账"、"一般贷款21002 xxxxxxx"、"转账一备注: xxx"、"货款"等
           - **任何描述性文字都应归入摘要列，而非凭证号列**
        
        3. **流水号**（第11列，最右侧）：
           - 纯数字编号，如 "901008003834"
        
        【重要！利用图中的黑色辅助线判定列边界】
        图中有多条垂直辅助线，请严格按照辅助线位置进行列归位：
        - 从左到右第1条线后：对方账号
        - 第2条线后：对方名称
        - 第3条线后：凭证号（通常为空！）
        - 第4条线后：摘要（包含"转账"、"贷款"等描述文字）
        - 第5条线后：流水号

        【常见错误 - 必须避免】
        ❌ 错误：把"转账"、"一般贷款xxx"等内容放入凭证号
        ✓ 正确：凭证号为空 ""，摘要填"转账"或"一般贷款xxx"
        
        【多行合并规则】
        - 对方账号、对方名称、摘要、流水号 等字段若跨多行，必须纵向合并
        - 合并时去除换行产生的多余空格
        
        【输出要求】
        只输出合法的 JSON 列表。严禁任何解释性文字。
        
        请根据以下 schema 提取数据：
        {result_schema}
        """
    elif bank_type == "cmb":
        prompt = f"""
        你是银行流水OCR专家，请从招商银行交易明细表中提取数据。
        
        【列顺序 - 从左到右】
        交易流水号 | 交易日期 | 借方(出账) | 贷方(入账) | 余额 | 收(付)方名称 | 收(付)方账号 | 摘要 | 交易类型 | 公司一卡通号 | 打印实例号
        
        【重要！提取规范】
        1. **判定合法交易行（核心规则）**：
           - **必须包含日期**：每一行合法记录的“交易日期”必须包含有效的日期格式（如 yyyy-MM-dd）。
           - **严禁提取噪声**：如果某一行看似文本（如 URL 链接 `http://...` 或 `www.cmbchina.com`），即使它位于第一列区域，也**必须忽略**，严禁将其作为“交易流水号”提取。
           - **黑名单字符**：如果内容包含 ".com"、"http"、"Enquiry"、"aspx" 等关键字，直接丢弃该行。
        2. **利用黑色辅助线判定（图中有 10 条垂直线 L1-L10，各列严禁错位）**：
           请严格按照辅助线定义的“车道”进行 11 个列的内容归位：
           - **L1 左侧**：交易流水号。
           - **L1 与 L2 之间**：交易日期（yyyy-MM-dd HH:mm:ss，需多行合并）。
           - **L2 与 L3 之间**：借方(出账)。
           - **L3 与 L4 之间**：贷方(入账)。**若此区间无字则必须为空 ""**，严禁抓取右侧余额。
           - **L4 与 L5 之间**：余额。
           - **L5 与 L6 之间**：收(付)方名称（需合并多行）。
           - **L6 与 L7 之间**：收(付)方账号。
           - **L7 与 L8 之间**：摘要。
           - **L8 与 L9 之间**：交易类型。
           - **L9 与 L10 之间**：公司一卡通号。**若此区间无字则必须为空 ""**，严禁抓取右侧打印号。
           - **L10 以右区域**：打印实例号（跨 3-4 行，须多行合并）。
        3. **过滤背景噪声**：
           - **URL 噪声**：强制忽略页面顶部和底部的 URL 字符串。
           - **页脚噪声**：严禁提取页码、温馨提示等。
        4. **多行合并**：收付方名称、流水号、打印实例号等多行文本必须纵向合并为一个字符串。
        5. **停止机制**：根据表格结束线或识别到非法行内容立即停止。
        
        【输出要求】
        只输出合法的 JSON 列表。严禁任何解释性文字。所见即所得，确保数据完整性。
        
        请根据以下 schema 提取数据：
        {result_schema}
        """
    elif bank_type == "jining":
        prompt = f"""
        你是银行流水OCR专家，请从济宁银行单位活期存款账户交易明细中提取数据。
        
        【特殊格式说明 - 济宁银行独有】
        济宁银行的每笔交易分为**两行**：
        - **第1行**：序号 | 记账日期 | 交易渠道 | 收入 | 支出 | 账户余额 | 摘要/备注
        - **第2行**：交易对手信息（以"交易对手信息:"开头，包含对方账号和对方名称）
        
        【重要！两行合并为一条记录】
        1. 第1行包含主要交易字段
        2. 第2行以"交易对手信息:"开头，内容格式如：
           "交易对手信息: 160805011920042856 梁山骏马机械制造有限公司 中国工商银行总行清算中心"
        3. **必须将两行合并为一条完整的交易记录**
        
        【列字段说明】
        - 序号：交易序号，如 1, 2, 3...
        - 记账日期：格式如 2024-06-30
        - 交易渠道：如"网银互联"、"人民银行"、"网上银行"等
        - 收入：金额，无数据时为空或0.00
        - 支出：金额，无数据时为空或0.00
        - 账户余额：当前账户余额
        - 摘要备注：如"汇兑汇款"、"网银转账|贷款"、"汇款|贷款"等
        - 交易对手信息：第2行的完整内容（去掉"交易对手信息:"前缀）
        
        【提取规则】
        1. **识别表头行**：包含"序号"、"记账日期"、"交易渠道"等文字的行是表头，跳过不提取
        2. **判定合法记录**：必须同时包含日期格式（如2024-06-30）和金额数据
        3. **合并规则**：每条记录占两行，第2行的交易对手信息必须合并到对应的第1行记录中
        4. **过滤噪声**：忽略页码、页眉页脚、URL等非交易数据
        
        【输出要求】
        只输出合法的 JSON 列表。严禁任何解释性文字。
        
        请根据以下 schema 提取数据：
        {result_schema}
        """
    elif bank_type == "cgb":
        prompt = f"""
        你是银行流水OCR专家，请从广发银行账户交易明细表中提取交易数据。
        
        【列顺序 - 从左到右，共15列】
        流水号 | 交易时间 | 收入 | 支出 | 余额 | 币种 | 对方账号 | 对方户名 | 交易行所 | 对方开户行联行号 | 对方开户行 | 凭证号 | 摘要 | 备注 | 附言
        
        【字段说明】
        - 流水号：交易流水号，如 76054955 7635（8位+4位格式）
        - 交易时间：交易日期时间，如 2024-01-21 00:56:45
        - 收入：收入金额，无数据时为空或"-"
        - 支出：支出金额，无数据时为空或"-"
        - 余额：交易后余额
        - 币种：如"人民币"
        - 对方账号：对方账户号码（可能跨多行）
        - 对方户名：对方户名（可能跨多行），如"山东莱威新材料有限公司"
        - 交易行所：交易行所代码
        - 对方开户行联行号：对方开户行联行号
        - 对方开户行：对方开户行名称（可能跨多行）
        - 凭证号：凭证号（可能为空）
        - 摘要：交易摘要，如"贷款还款"、"网银支付"、"普通汇兑"等
        - 备注：备注信息（可能为空）
        - 附言：附言信息，如"往来款"等
        
        【跨页记录处理 - 非常重要！】
        广发银行流水存在跨页现象，一条交易记录可能被分割到两页：
        1. **页面底部不完整记录**：如果页面底部的行没有完整的流水号（8位数字+4位数字格式如"80335487 2412"），
           或者缺少日期时间（如"2024-05-31 17:39:42"格式），该记录是不完整的，标记为 "_incomplete": "tail"
        2. **页面顶部延续记录**：如果页面顶部第一行没有流水号或日期，只有时间（如"17:39:42"）或其他部分字段，
           该记录是上页的延续，标记为 "_incomplete": "head"
        3. 完整记录无需标记 "_incomplete" 字段
        
        【多行合并规则】
        - 流水号、对方账号、对方户名、对方开户行等字段可能跨多行，必须纵向合并
        - 合并时去除换行产生的多余空格
        
        【提取规则】
        1. 识别表头行并跳过（包含"流水号"、"交易时间"等文字的行）
        2. 忽略页脚信息（如"第X页,共X页"）
        3. 每条交易记录可能占多行（因为字段内容跨行）
        4. 保留原始金额格式
        5. **重要**：忽略电子印章/专用章内容，不要将印章中的文字（如"广发银行电子回单专用章"）识别到任何字段中
        
        【输出要求】
        只输出合法的 JSON 列表。严禁任何解释性文字。
        
        请根据以下 schema 提取数据：
        {result_schema}
        """
    else:
        # 山东地方银行默认提示
        prompt = f"""
        Suppose you are an information extraction expert. Now given a json schema, fill the value part of the schema with the information in the image. Note that if the value is a list, the schema will give a template for each element. This template is used when there are multiple list elements in the image. Finally, only legal json is required as the output. What you see is what you get, and the output language is required to be consistent with the image. No explanation is required. The input json schema content is as follows: {result_schema}。
        """
    
    rest = request_stream(question=prompt,
                          show_request=False,
                          file_base=file_path,
                          model=MODEL_LOCAL)
    return rest

def read_data(file_path, schema_name: str = "bank_transaction"):
    """
    使用AI模型从图片中提取数据
    
    Args:
        file_path (str): 图片文件路径
        schema_name (str): schema 配置名称，默认为 "bank_transaction"
        
    Returns:
        str: 提取的JSON数据
    """
    result_schema = load_schema(schema_name)
    
    prompt = f"""
    Suppose you are an information extraction expert. Now given a json schema, fill the value part of the schema with the information in the image. Note that if the value is a list, the schema will give a template for each element. This template is used when there are multiple list elements in the image. Finally, only legal json is required as the output. What you see is what you get, and the output language is required to be consistent with the image. No explanation is required. The input json schema content is as follows: {result_schema}。
    """
    rest = request_stream(question=prompt,
                          show_request=False,
                          file_base=file_path,
                          model=MODEL_LOCAL)

    return rest

def process_single_image(args):
    """
    处理单个图片的函数，用于多线程处理
    """
    image_path, results_dir = args
    try:
        filename = os.path.basename(image_path)
        output_path = os.path.join(results_dir, f"{os.path.splitext(filename)[0]}.txt")
        
        # 提取数据
        rest = read_data(image_path)
        
        # 保存结果
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(rest)
        return True
    except Exception as e:
        print(f"处理图片 {os.path.basename(image_path)} 时出错: {e}")
        return False

def process_single_image_with_schema(args):
    """
    处理单个图片的函数（使用指定 schema），用于多线程处理
    """
    image_path, results_dir, schema, bank_type = args
    try:
        filename = os.path.basename(image_path)
        output_path = os.path.join(results_dir, f"{os.path.splitext(filename)[0]}.txt")
        
        # 提取数据
        rest = read_data_with_schema(image_path, schema, bank_type)
        
        # 保存结果
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(rest)
        
        print(f"  ✓ 页面 {filename} 识别完成")
        return True
    except Exception as e:
        print(f"  ✗ 处理图片 {os.path.basename(image_path)} 时出错: {e}")
        return False

def batch_process_images_multithread_with_schema(input_folder, output_folder, schema, bank_type="shandong_local", max_workers=4):
    """
    使用多线程处理文件夹中的所有图片（使用指定 schema）
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    image_files = sorted([f for f in os.listdir(input_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        args_list = [(os.path.join(input_folder, f), output_folder, schema, bank_type) for f in image_files]
        futures = [executor.submit(process_single_image_with_schema, args) for args in args_list]
        concurrent.futures.wait(futures)

def batch_process_images_multithread(input_folder, output_folder, max_workers=4):
    """
    使用多线程处理文件夹中的所有图片
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    image_files = sorted([f for f in os.listdir(input_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        args_list = [(os.path.join(input_folder, f), output_folder) for f in image_files]
        futures = [executor.submit(process_single_image, args) for args in args_list]
        concurrent.futures.wait(futures)

def read_summary_data_with_schema(file_path, schema: dict, bank_type: str):
    """
    使用指定的 schema 从图片中提取汇总数据
    """
    result_schema = json.dumps(schema, ensure_ascii=False)
    
    if bank_type == "cmb":
        prompt = f"""
        作为银行单据分析专家，请从招商银行流水单首页的上方区域提取汇总信息。
        需要提取的信息包括但不限于：账号、户名、币种、开始日期、结束日期、出账总笔数、入账总笔数、出账总金额、入账总金额等。
        
        【提取规范】
        1. 只从首页顶部的文字描述区域提取，不要提取下方的表格明细。
        2. 确保日期格式统一（如 yyyyMMdd 或 yyyy-MM-dd）。
        3. 金额请保留原始数值字符串。
        
        请直接输出 JSON，严禁任何解释。Schema 如下：
        {result_schema}
        """
    elif bank_type == "jining":
        prompt = f"""
        作为银行单据分析专家，请从济宁银行单位活期存款账户交易明细首页提取汇总信息。
        
        【济宁银行汇总信息位置】
        汇总信息位于页面左上角区域，包括：
        - 账号：如 81501220142103084
        - 账户名称：如 山东太岳弹簧有限公司
        - 起止日期：如 2024/01/01-2024/06/30
        - 币种：如 人民币
        - 收入金额合计：如 142,161,044.41
        - 支出金额合计：如 138,088,971.61
        - 开户机构：如 济宁银行股份有限公司梁山支行（位于"开户机构:"后面）
        
        【提取规范】
        1. 只从首页顶部区域提取，不要提取下方的交易明细表格
        2. 金额请保留原始字符串格式（含逗号分隔符）
        3. 日期格式保持原样
        
        请直接输出 JSON，严禁任何解释。Schema 如下：
        {result_schema}
        """
    elif bank_type == "cgb":
        prompt = f"""
        作为银行单据分析专家，请从广发银行账户交易明细表首页提取汇总信息。
        
        【广发银行汇总信息位置】
        汇总信息位于页面顶部区域，包括：
        - 户名：如 山东莱威新材料有限公司
        - 账号：如 955088023736990012
        - 起止日期：如 20240120-20240630
        - 币种：如 人民币
        - 单位：如 元
        - 支出总金额：如 6,545,010.42
        - 支出总笔数：如 5
        - 收入总金额：如 6,512,058.90
        - 收入总笔数：如 8
        - 账户当前余额：如 2,342.22
        - 记录数：如 13
        
        【提取规范】
        1. 只从首页顶部区域提取，不要提取下方的交易明细表格
        2. 金额请保留原始字符串格式（含逗号分隔符）
        3. 日期格式保持原样（如 yyyyMMdd-yyyyMMdd）
        
        请直接输出 JSON，严禁任何解释。Schema 如下：
        {result_schema}
        """
    else:
        # 通用汇总提取提示
        prompt = f"""
        Suppose you are an information extraction expert. Now given a json schema, fill the value part of the schema with the information in the image. Finally, only legal json is required as the output. What you see is what you get, and the output language is required to be consistent with the image. No explanation is required. The input json schema content is as follows: {result_schema}。
        """
        
    response = request_stream(question=prompt, file_base=file_path, model=MODEL_LOCAL).strip()
    return response

def read_summary_data(file_path, schema_name: str = "bank_summary"):
    """
    从图片中提取汇总数据（仅用于第1页）
    """
    schema_str = load_schema(schema_name)
    prompt = f"Suppose you are an information extraction expert. Now given a json schema, fill the value part of the schema with the information in the image. Finally, only legal json is required as the output. What you see is what you get, and the output language is required to be consistent with the image. No explanation is required. The input json schema content is as follows: {schema_str}。"
    response = request_stream(question=prompt, file_base=file_path, model=MODEL_LOCAL).strip()
    return response
