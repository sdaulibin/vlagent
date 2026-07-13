# 数据抽取与对账系统设计思路

## 项目背景

输入的是word文件夹和excel文件夹，文件夹下的文件不固定。
但需要将word文件（比如：`青岛银行2025年4季度数据变动说明3.doc`）和 Excel 文件（比如：`季报202512.XLS`）中提取金融数据并进行对比验证。

## 目标

1. 从 Word 中提取指标代码、指标名称、增减方向、金额等信息
2. 从 Excel 中定位对应指标的数值
3. 对比两者数据的一致性，生成差异报告

## 整体架构思路

文档中，每一个word提取为一张表，然后所有excel提取为一张表。

### 一、目标数据模型

将 Word 文档中的金融数据转换为此结构，一个word提取一张表：

表名：financial\_table

| 字段名               | 类型      | 说明                                                |
| ----------------- | ------- | ------------------------------------------------- |
| title             | string  | 文件标题                                              |
| sheet             | string  | 表单名称                                              |
| code              | string  | 指标代码                                              |
| name              | string  | 指标名称                                              |
| direction         | enum    | 增加/减少（+1/-1）                                      |
| amount            | decimal | 数值                                                |
| amount\_unit      | string  | 数值单位                                              |
| amount\_scale     | int     | Word 主句金额小数位数，用于对账阶段按相同精度进行四舍五入比较                   |
| paraindex         | int     | 标号                                                |
| source\_ref       | string  | 定位信息（按 Word 全文段落序号；如发生“纯序号行+下一行合并”，则为范围 `17-18`）           |
| context           | string  | 原句/段落片段                                           |
| file\_name        | string  | 文件名                                               |
| calc\_scope\_hint | string  | 当前记录生效的计算口径提示，取值建议为 `rmb`、`foreign`、`usd_total`、空 |

表名：company\_profit\_loss\_table

| 字段名                | 类型      | 说明                      |
| ------------------ | ------- | ----------------------- |
| company            | string  | 企业名称                    |
| direction          | enum    | 增加/减少（+1/-1）            |
| profit\_loss       | decimal | 数值                      |
| profit\_loss\_unit | string  | 数值单位                    |
| word\_record\_id   | int     | 关联 `financial_table.id` |
| sheet              | string  | 关联表单名称                  |
| code               | string  | 指标代码                    |
| file\_name         | string  | 文件名                     |
| exception\_id      | int     | 异常值ID                   |

Excel 数据模型：
表名：excel\_profit\_loss\_table

| 字段名                          | 类型      | 说明            |
| ---------------------------- | ------- | ------------- |
| sheet                        | string  | 表单名称          |
| code                         | string  | 指标代码          |
| name                         | string  | 指标名称          |
| cur\_rmb\_balance            | decimal | 本期人民币余额（万元）   |
| cur\_rmb\_occur              | decimal | 本期人民币发生额（万元）  |
| cur\_foreign\_balance        | decimal | 本期本外币余额（万元）   |
| cur\_foreign\_occur          | decimal | 本期本外币发生额（万元）  |
| cur\_foreign\_total\_balance | decimal | 本期美元合计余额（万元）  |
| cur\_foreign\_total\_occur   | decimal | 本期美元合计发生额（万元） |
| pre\_rmb\_balance            | decimal | 上期人民币余额 （万元）  |
| pre\_rmb\_occur              | decimal | 上期人民币发生额（万元）  |
| pre\_foreign\_balance        | decimal | 上期本外币余额（万元）   |
| pre\_foreign\_occur          | decimal | 上期本外币发生额（万元）  |
| pre\_foreign\_total\_balance | decimal | 上期美元合计余额 （万元） |
| pre\_foreign\_total\_occur   | decimal | 上期美元合计发生额（万元） |
| excel\_row\_index            | int     | Excel 原始数据行号  |
| file\_name                   | string  | 文件名           |

对比关联表：
表名：compare\_link\_table

| 字段名               | 类型     | 说明                                   |
| ----------------- | ------ | ------------------------------------ |
| id                | int    | 主键ID                                 |
| batch\_id         | string | 批次号                                  |
| word\_record\_id  | int    | 关联 `financial_table.id`              |
| excel\_record\_id | int    | 关联 `excel_profit_loss_table.id`，允许为空 |

- 说明：`excel_profit_loss_table` 不直接存“较上期增减”字段，后端在对账时先根据 Word 中已继承的口径约束信息判断使用哪组 Excel 列；若没有约束信息，再根据 Word 主句单位和 Excel 对应记录动态回退判断口径并计算差值。
- 差值计算规则：
- 若当前指标段落之前最近生效的约束行包含 `本外币`，则优先使用 `cur_foreign_balance - pre_foreign_balance` 计算差值
- 若当前指标段落之前最近生效的约束行包含 `外币` 或 `美元合计`，则优先使用 `cur_foreign_total_balance - pre_foreign_total_balance` 计算差值
- 若当前指标段落之前最近生效的约束行包含 `人民币`，则优先使用 `cur_rmb_balance - pre_rmb_balance` 计算差值
- 若当前指标段落之前没有任何生效的口径约束行，则进入默认回退逻辑：若 Word 主句单位文本中包含 `美元`，则使用 `cur_foreign_total_balance - pre_foreign_total_balance`
- 若当前指标段落之前没有任何生效的口径约束行，且 Word 主句单位文本中不包含 `美元`，则检查对应 Excel 记录是否存在人民币相关值；若存在则使用 `cur_rmb_balance - pre_rmb_balance`，若不存在则使用 `cur_foreign_balance - pre_foreign_balance`
- 若已确定的口径在 Excel 对应记录中完全不存在相关字段值，则登记 `计算要求异常`
- 上述差值先按 Excel 原始单位“万元”执行减法；若 Word 单位为 `万元` 或 `万`，则直接按“万元”口径比较；其他受支持单位则先将 Excel 差值换算后再与 `financial_table.amount + amount_unit` 比较

exception\_group\_table:

| 字段名              | 类型     | 说明                      |
| ---------------- | ------ | ----------------------- |
| id               | int    | 主键ID                    |
| exception\_id    | int    | 异常值ID                   |
| word\_record\_id | int    | 关联 `financial_table.id` |
| field\_name      | string | 异常字段名                   |
| value            | string | 错误内容，后续用于高亮             |

exception\_table:

| 字段名  | 类型     | 说明    |
| ---- | ------ | ----- |
| id   | int    | 主键ID  |
| name | string | 异常值名称 |

- 当前实际会用到并在详情页展示的异常类型为\["指标代码异常", "指标名称异常", "指标数值异常", "表单无对应异常", "关联公司数值异常", "余额缺失异常", "计算要求异常", "excel异常", "格式异常", "关联公司增减方向与当前主句不一致"]
- 当前后端异常字典由 `ExceptionType + EXCEPTION_TYPE_NAMES` 维护，不单独建 `exception_table`；除 `关联公司增减方向与当前主句不一致` 外，后端还新增独立异常 `关联公司格式异常`（建议 `id = 14`），用于标记企业明细自身格式不规范的场景；但前端现阶段仍可把它归并展示为 `格式异常`
- `指标数值单位异常`、`指标无对应异常`、`其他异常` 当前链路不再作为有效异常类型使用，也不在详情页展示
- 其中 计算要求异常包括：列根本不存在、值不是合法数字、当前记录不满足既定计算前提、无法继续完成计算
- 对于 Word 解析，如果表单内当前生效口径为 `本外币/人民币`，但具体主句金额单位使用 `美元/万美元/亿美元`，或当前生效口径为 `外币/美元合计`，但具体主句金额单位使用 `元/万/万元/亿/亿元`，应在 Word 解析阶段直接登记为 `计算要求异常`；这类记录不再继续参与后续金额计算，只保留 Word 侧异常供人工复核
- 其中 `格式异常` 只描述主句格式问题，并进一步分为两类：一类是“软异常”，即仍满足 `本期 + 增加/减少 + 修饰词 + 金额 + 单位`，例如 `本期增加约4.4亿元`、`本期减少共300万元`；这类记录仍按提取出的精确值参与对账和后续内查，但保留一条 `格式异常` 供人工复核。另一类是“阻断型异常”，即主句缺少 `增加/减少`、使用 `本期为...`、或不是 `本期`（如 `本月增加...`）；这类记录不再继续参与金额对账，且不参与依赖主句方向的后续内查
- 其中 `关联公司格式异常` 用于描述企业明细自身格式问题，也分为两类：一类是“软异常”，即仍可解析出 `增加/减少 + 金额 + 单位`，但 `增加/减少` 后含修饰词，例如 `A公司减少约2.3亿元`；这类企业明细仍写入方向、金额和单位，并继续参与后续内查。另一类是“阻断型异常”，即无法解析出 `增加/减少`，例如 `A公司2.3亿元`；这类企业明细不参与后续公司内查，但仍保留异常供人工复核
- 其中 `关联公司增减方向与当前主句不一致` 包括：主句已明确解析出 `增加/减少`，且某条关联公司明细也成功解析出 `增加/减少`，但两者方向不一致；例如主句是“本期增加6.8亿元”，而企业明细中出现“某公司减少2.3亿元”
- 内部实现中，格式异常相关的 `exception_group_table.value` 会复用一组共享格式标签常量（定义在 `core/regex_utils.py`），当前包括：
  - `FORMAT_TAG_DIRECTION_WITH_MODIFIER = 增加/减少后含修饰词`
  - `FORMAT_TAG_CANONICAL_ASSIGNMENT = 本期为`
  - `FORMAT_TAG_NON_STANDARD_INC_DEC = 非标准增减主句`
  - `FORMAT_TAG_NON_STANDARD_MAIN = 非标准主句`
  - `FORMAT_TAG_MISSING_INC_DEC = 缺少增加/减少`
  - `FORMAT_TAG_SIGNED_DIRECTION = +/-`
- 上述格式标签只作为后端内部解析标记和前端高亮判断依据，不改变用户最终看到的异常类型名称；前端仍统一展示为 `格式异常` 或 `关联公司格式异常` 的归并名称

### 二、Word 文档解析策略

使用正则表达式

- 1.按段落读取，保留原始段落文本，后续写入 `financial_table.context`
- 2.标题取第一行，写入 `financial_table.title`
- 3.文档按表单切分，遇到包含“表单”字样的段落时，视为一个新表单开始
- 4.表单名称标准格式为 `A1433表单：` 或 `A1433 表单：`，提取 `A1433` 写入 `financial_table.sheet` 和 `company_profit_loss_table.sheet`
- 5.表单名称解析完成后，到下一个表单出现之前，除了序号指标段外，可能还会出现单独一行的口径约束说明，例如 `本外币`、`外币`、`美元合计`、`人民币`
- 6.这些口径约束说明不一定紧跟在表单行后面，也可能出现在表单中间；解析时应按段落顺序维护“当前生效口径”
- 7.若识别到新的约束行，则更新当前生效口径；该口径会作用于其后的序号指标段，直到被下一条新的约束行覆盖
- 8.每条 `financial_table` 记录都应保存当前生效口径到 `calc_scope_hint`
- 9.若某条指标记录之前没有任何生效的口径约束，则该条记录的 `calc_scope_hint` 保持为空，不在 Word 解析阶段直接推断默认口径
- 10.对这类 `calc_scope_hint` 为空的记录，在后续对账阶段再做默认回退判断：若主句单位文本中包含 `美元`，则按 `美元合计` 处理；否则检查对应 Excel 记录是否存在人民币相关值，存在则按 `人民币` 处理，不存在则按 `本外币` 处理
- 11.当前表单开始后，直到遇到下一个表单名称或文档结束，期间所有段落都归属于当前 `sheet`
- 12.读取表单内每个段落，仅处理以 `（1）`、`（2）`、`(1)`、`(2)` 等序号开头的指标说明段
- 13.识别段落开头的序号，写入 `financial_table.paraindex`
- 14.识别序号后第一个中文引号内的内容，如 `12P02农林牧渔业贷款`
- 15.在引号内容中，从开头连续的英文数字部分提取指标代码，如 `12P02`，写入 `financial_table.code` 和 `company_profit_loss_table.code`
- 16.引号内容中去掉指标代码后的剩余中文文本，作为指标名称，如 `农林牧渔业贷款`，写入 `financial_table.name`
- 17.引号解析完成后，不要继续整段一起匹配，而是从引号结束位置开始，按后续文本一句一句向后解析
- 18.引号后的第一句通常是指标主句，例如 `本期减少4.4亿元` 或 `本期增加6.8亿元`
- 19.先从这句中识别 `增加` 或 `减少`，写入 `financial_table.direction`，建议标准化为 `+1 / -1`
- 20.再从同一句中识别数值部分，如 `4.4`、`6.8`，写入 `financial_table.amount`
- 21.再从同一句中识别金额单位，如 `万元`、`万`、`元`、`亿元`、`亿`、`万美元`、`美元`、`亿美元`，写入 `financial_table.amount_unit`
- 22.`financial_table.amount` 保存原始数值部分，`financial_table.amount_unit` 保存原始单位；解析阶段不再单独登记“指标数值单位异常”，后续仅按支持单位范围做换算或进入其他异常判断
- 23.若主句格式是 `本期增加/减少 + 修饰词 + 金额 + 单位`（例如 `本期增加约4.4亿元`、`本期减少共300万元`），仍落库该条指标记录，并按提取出的方向、金额、单位精确参与后续对账和内查；同时登记一条 `格式异常`
- 24.若主句格式不是 `本期增加/减少 + 金额 + 单位`，且也不属于上述“可解析软异常”（例如 `本月增加/减少...`、`本期为...`、`本期4.4亿元`），仍然落库该条指标记录；对于无法按既定规则解析出的 `direction/amount/amount_unit`，分别置为 `0/空/空`，并登记一条 `格式异常`。这类记录不再参与金额对账，也不参与依赖主句方向的后续内查
- 25.生成指标主记录时，将当前段落继承到的口径约束写入 `financial_table.calc_scope_hint`
- 26.主句示例：`（1）“12P02农林牧渔业贷款”本期减少4.4亿元`，这一句只生成一条 `financial_table` 记录
- 27.每条指标记录生成 `financial_table.source_ref`，保存按 Word 全文段落序号的定位信息（如发生合并则为范围）
- 28.整段原文保留在 `financial_table.context`，用于后续人工复核
- 29.主句解析完成后，再继续向后读取下一句或下一个分句
- 30.若后续文本出现 `主要是`、`主要为`、`主要由`、`主要原因是`，则从这些提示词之后开始解析企业明细
- 31.企业明细要逐个企业解析，不能把多个企业合并成一条记录
- 32.每个企业明细的基本格式是 `企业名称 + 增加/减少 + 金额`，例如 `青州市财通农业发展有限公司减少2.3亿元`
- 33.先识别企业名称，写入 `company_profit_loss_table.company`
- 34.再识别该企业后的 `增加` 或 `减少`，写入 `company_profit_loss_table.direction`
- 35.再识别该企业后的金额数值和单位，数值写入 `company_profit_loss_table.profit_loss`，单位写入 `company_profit_loss_table.profit_loss_unit`；解析阶段不再单独登记“指标数值单位异常”，后续如涉及对账再根据单位换算
- 36.若企业明细格式是 `企业名称 + 增加/减少 + 修饰词 + 金额 + 单位`（例如 `A公司减少约2.3亿元`），仍写入该企业明细的方向、金额、单位，并额外登记一条 `关联公司格式异常`
- 37.若企业明细无法解析出 `增加/减少`，但仍能识别“企业名称 + 金额 + 单位”（例如 `A公司2.3亿元`），则仍可登记一条 `关联公司格式异常` 用于提示；这条企业明细不参与后续公司内查
- 38.每条企业明细都要写入 `company_profit_loss_table.word_record_id = financial_table.id`
- 39.`company_profit_loss_table.company` 存关联主体机构，通常取当前文档所属机构名称
- 40.企业明细仍保留 `sheet + code` 等冗余字段，便于独立查询与排查
- 41.同一段落中的多个企业明细，一般使用 `，` 或 `、` 分隔，需要拆分后逐个处理
- 42.例如 `主要是青州市财通农业发展有限公司减少2.3亿元，乳山市德欣农业开发有限公司减少1.5亿元。` 应拆成两条 `company_profit_loss_table` 记录
- 43.若段落只有指标总额，没有企业分解，则只写 `financial_table`，不写 `company_profit_loss_table`
- 44.若主句属于“阻断型格式异常”，则该 `word_record_id` 不参与依赖主句方向的“关联公司增减方向与当前主句不一致”判断；但企业明细自身仍可继续参与“关联公司增减金额不一致”内查，前提是参与比较的那条企业明细本身格式有效
- 45.若主句 `financial_table.direction` 已成功解析为 `增加/减少`，且主句不属于“阻断型格式异常”，则当前段落下每条格式有效的企业明细 `company_profit_loss_table.direction` 也必须与主句保持一致；若任一企业明细方向相反，则登记一条新的 `关联公司增减方向与当前主句不一致`
- 46.`关联公司增减方向与当前主句不一致` 建议按“每个冲突企业一条异常明细”落库：`word_record_id = financial_table.id`、`exception_id = 13`、`field_name = company_direction`、`value = 企业名称`
- 47.执行“关联公司增减金额不一致”内查时，只比较格式有效的企业明细记录；若某一公司的某条明细自身格式异常，则只忽略那一条明细，不影响同公司其他格式有效记录继续参与内查
- 48.异常信息不再回写 `financial_table` 的聚合字段，而是统一写入 `exception_group_table`
- 49.解析顺序必须固定为：先维护当前口径约束，再解析引号内指标信息，再解析主句方向、金额、金额单位，最后逐个企业明细并执行“主句-企业明细方向一致性校验”

### 三、Excel 数据对齐策略

#### 1. 建立索引

- 按 Sheet 逐个读取 Excel，识别每个工作表的表头、指标区和数值区
- Excel 表单名称标准化规则：若当前 Sheet 名称只有数字，则使用第一张 Sheet 名称中的字母前缀与当前数字拼接；若当前 Sheet 名称本身已包含字母，则保持原样
- 在每个 Sheet 中定位指标代码列、指标名称列、本期人民币余额列、本期本外币余额列、本期美元合计余额列、上期人民币余额列、上期本外币余额列、上期美元合计余额列
- 每识别到一行有效指标数据，就生成一条 `excel_profit_loss_table` 记录
- 将 `sheet`、`code`、`name`、`cur_rmb_balance`、`cur_rmb_occur`、`cur_foreign_balance`、`cur_foreign_occur`、`cur_foreign_total_balance`、`cur_foreign_total_occur`、`pre_rmb_balance`、`pre_rmb_occur`、`pre_foreign_balance`、`pre_foreign_occur`、`pre_foreign_total_balance`、`pre_foreign_total_occur`、`file_name`、`batch_id` 分别写入对应字段

#### 2. 数值列识别

- 通过表头关键词识别 `本期人民币余额`、`本期本外币余额`、`本期美元合计余额`、`上期人民币余额`、`上期本外币余额`、`上期美元合计余额` 及其对应发生额列
- Excel 各金额字段按原值写入，单位保持为“万元”
- 对账阶段不直接读取差值字段，而是先读取 Word 主句中的金额单位，再动态选择差值列：
- 若 `financial_table.calc_scope_hint = usd_total`，则使用 `cur_foreign_total_balance - pre_foreign_total_balance`
- 若 `financial_table.calc_scope_hint = foreign`，则使用 `cur_foreign_balance - pre_foreign_balance`
- 若 `financial_table.calc_scope_hint = rmb`，则使用 `cur_rmb_balance - pre_rmb_balance`
- 若 `financial_table.calc_scope_hint` 为空，则进入默认回退逻辑：若 Word 主句单位文本中包含 `美元`，则按 `usd_total` 使用 `cur_foreign_total_balance - pre_foreign_total_balance`；否则检查对应 Excel 记录是否存在人民币相关值，存在则按 `rmb` 使用 `cur_rmb_balance - pre_rmb_balance`，不存在则按 `foreign` 使用 `cur_foreign_balance - pre_foreign_balance`
- 口径约束行优先级高于金额单位；只有在没有约束行时，才使用金额单位判断
- 若选中的“本期余额”或“上期余额”字段为空，则先记录一条 `余额缺失异常`，并将该空值按 `0` 参与后续减法计算
- 计算出的差值先按 Excel 原始单位“万元”执行减法；若 Word 单位为 `万元`、`万` 或 `万美元`，则直接按“万”口径参与对账；其他受支持单位则将 Excel 差值按规则换算后参与对账
- 若某个 Sheet 表头存在合并单元格，需要先做表头归并后再识别字段位置

#### 3. 数据匹配

- 我们的目标是核对 Word 文档信息，所以要以 `financial_table` 为核心，找到对应的 `excel_profit_loss_table` 记录，查证 `financial_table` 中的数值是否与 Excel 动态计算结果一致
- （1）以 `financial_table.sheet = excel_profit_loss_table.sheet` 作为第一层匹配条件，先把比对范围限定在同一表单内；若匹配不到对应表单，则新增一条 `compare_link_table` 记录，`excel_record_id = 空`，并新增一条 `exception_group_table` 记录：`word_record_id = financial_table.id`、`exception_id = 5`、`field_name = sheet`、`value = financial_table.sheet`
- （2）同一表单下，以 `financial_table.code = excel_profit_loss_table.code` 作为第二层精确匹配条件；若同一 `sheet + code` 命中多条 Excel 记录，则记录一条 `exception_id = 10` 的异常，`word_record_id = financial_table.id`、`field_name = code`、`value = financial_table.code`，返回
- （3）若 `sheet + code` 未命中，则直接创建 `compare_link_table`（`excel_record_id = 空`），并记录一条 `exception_id = 1` 的异常，`field_name = code`；不再继续使用标准化后的 `name` 做兜底匹配，同时该条记录直接停留在 Word 表单自查，不再继续进入后续 Excel 对账判断
- （4）若匹配到唯一 Excel 记录，则创建一条 `compare_link_table`；若标准化后的 `financial_table.name` 与标准化后的 `excel_profit_loss_table.name` 仍不一致，则记录一条 `exception_id = 2` 的异常，`field_name = name`
- （5）Excel 中原始 `name` 字段必须保留，不直接覆盖；“去序号、去空格”只用于解析阶段辅助识别和对账阶段严格匹配，便于后续人工复核时看到原始指标名称
- （6）若主句在 Word 解析阶段被识别为“软异常”（如 `本期增加约...`、`本期减少共...`），则该条记录仍可继续完成 Excel 匹配、金额计算与金额对账；若主句被识别为“阻断型格式异常”（如 `本期为...`、`本月增加...`、缺少 `增加/减少`），则该条记录仍可完成 Excel 匹配并保存关联，但不再继续进入金额计算与金额对账判断
- （7）Word 金额比较时，先将 `financial_table.direction * financial_table.amount` 作为 Word 侧参与比较的最终值；若 `direction` 不是“增加/减少”对应的合法值，直接记录一条 `exception_id = 3` 的异常，`field_name = direction`
- （8）Excel 金额比较时，不使用现成差值字段，而是按当前记录动态计算：
- 若 `financial_table.calc_scope_hint = usd_total`，则使用 `excel_profit_loss_table.cur_foreign_total_balance - excel_profit_loss_table.pre_foreign_total_balance`
- 若 `financial_table.calc_scope_hint = foreign`，则使用 `excel_profit_loss_table.cur_foreign_balance - excel_profit_loss_table.pre_foreign_balance`
- 若 `financial_table.calc_scope_hint = rmb`，则使用 `excel_profit_loss_table.cur_rmb_balance - excel_profit_loss_table.pre_rmb_balance`
- 若 `financial_table.calc_scope_hint` 为空，则进入默认回退逻辑：若 Word 主句单位文本中包含 `美元`，则按 `usd_total` 使用 `excel_profit_loss_table.cur_foreign_total_balance - excel_profit_loss_table.pre_foreign_total_balance`；否则检查对应 Excel 记录是否存在人民币相关值，存在则按 `rmb` 使用 `excel_profit_loss_table.cur_rmb_balance - excel_profit_loss_table.pre_rmb_balance`，不存在则按 `foreign` 使用 `excel_profit_loss_table.cur_foreign_balance - excel_profit_loss_table.pre_foreign_balance`
- `发生额` 字段只保留，不参与当前对账
- （9）若第（8）步要求使用的 Excel 余额列存在，但其中某个“本期余额”或“上期余额”值为空，则记录一条 `exception_id = 8` 的异常，`field_name` 填对应余额字段名，`value` 填空值原文；随后将缺失余额按 `0` 继续参与减法计算
- （10）若第（8）步要求使用的 Excel 列不存在、列值不是合法数字、无法完成计算，或当前记录不满足既定计算前提，则记录一条 `exception_id = 9` 的异常，`field_name` 填对应字段名，`value` 填错误内容，返回
- （11）将 Excel 差值按“万元”先执行减法；若 `financial_table.amount_unit` 为 `万元`、`万` 或 `万美元`，则直接按“万”口径参与比较；否则将 Excel 差值从“万”换算到“亿”口径（除以 `10000`）。对账比较时按 `financial_table.amount_scale` 做四舍五入，保证 Excel 侧与 Word 侧使用相同小数精度参与比较。若最终值不一致，或者 Word 方向导致的正负号与 Excel 计算结果相反，则记录一条 `exception_id = 3` 的异常，`field_name` 取 `amount / direction / amount_unit` 中对应的异常字段
- （12）Word 内部先执行“主句-企业明细方向一致性校验”：仅当主句不属于“阻断型格式异常”，且 `financial_table.direction` 已被成功解析为 `增加/减少` 时，才检查当前 `word_record_id` 下每条格式有效的 `company_profit_loss_table.direction` 是否与主句一致；若某条企业明细方向相反，则对当前 `word_record_id` 新增一条 `exception_id = 13` 的异常，建议 `field_name = company_direction`、`value = 企业名称`
- （13）最后执行 Word 内部企业明细一致性校验：加载表 `company_profit_loss_table`，按 `batch_id + file_name + company` 分组，对比每个分组下格式有效记录的 `direction`、`profit_loss` 和 `profit_loss_unit` 是否一致；若不一致，则对该分组内所有关联的 Word 主记录分别记录一条 `exception_id = 7` 的异常。若同一公司存在格式异常记录，则只忽略该条异常记录，不影响同公司其他格式有效记录参与比较

### 四、实现策略选择

#### 1. 架构选择

当前阶段只实现纯后端离线批处理程序，不实现 API 和前端。

- 使用 Python 编程，当前入口为命令行方式运行
- 数据库存储使用 SQLite
- 运行环境按本地和 Docker 兼容方式设计
- Word 转换链路只保留 `LibreOffice/soffice + python-docx`
- Excel 解析链路使用 `xlrd==1.2.0`

#### 2. 实现策略

- 实施优先级以“抽取准确性优先、处理效率次之”为原则，不以高并发作为首要目标。
- 当前任务执行采用“文件级有限并发”策略：可并发处理多个 Word/Excel 文件，但单个文件内部按顺序解析，避免复杂并发导致结果不稳定。
- 数据库写入采用“单文件内存聚合 + 单文件批量写库”的方式，不在逐条解析时立即写库。
- 对账和校验统一从数据库读取，不直接依赖解析时的临时内存结果。
- Word 文档处理采用两段式主链路：`.doc -> .docx -> 结构化解析`。
- `.doc` 文件只使用 `soffice --headless` 转换为 `.docx`，不依赖 Word COM、不依赖 Microsoft Office。
- Word 解析后保留原始段落文本到 `financial_table.context`，用于后续人工复核。
- Excel 提取阶段使用 `xlrd==1.2.0` 读取 `.xls` 文件内容，当前按“前 4 行固定表头 + 合并单元格展开 + 表头语义识别”实现。
- Excel 原始金额字段统一按“万元”口径落库，不单独保存 `profit_loss_change` 字段。
- Excel 差值只在对账阶段动态计算，不在解析阶段预先写回结果字段。
- 对比过程不采用暴力比对，而是按 `sheet -> code -> name` 的顺序逐条匹配对应的 `excel_profit_loss_table` 记录。
- Word 内部一致性校验和 Word/Excel 对账分两个阶段执行：先完成 Word 自校验，再执行跨源对账。
- 若后期数据量持续增大，优先通过增加 `batch_id`、`file_name`、`sheet + code` 等索引和批次管理方式提升性能；只有当 SQLite 无法满足容量和并发要求时，再考虑迁移到 PostgreSQL。

#### 3. 数据库设计

表名：financial\_table

| 字段名               | 类型      | 说明                                                |
| ----------------- | ------- | ------------------------------------------------- |
| title             | string  | 文件标题                                              |
| sheet             | string  | 表单名称                                              |
| code              | string  | 指标代码                                              |
| name              | string  | 指标名称                                              |
| direction         | enum    | 增加/减少（+1/-1）                                      |
| amount            | decimal | 数值                                                |
| amount\_unit      | string  | 数值单位                                              |
| paraindex         | int     | 标号                                                |
| source\_ref       | string  | 定位信息（段落序号）                                        |
| context           | string  | 原句/段落片段                                           |
| file\_name        | string  | 文件名                                               |
| batch\_id         | string  | 批次号                                               |
| calc\_scope\_hint | string  | 当前记录生效的计算口径提示，取值建议为 `rmb`、`foreign`、`usd_total`、空 |

表名：company\_profit\_loss\_table

| 字段名                | 类型      | 说明                      |
| ------------------ | ------- | ----------------------- |
| company            | string  | 企业名称                    |
| direction          | enum    | 增加/减少（+1/-1）            |
| profit\_loss       | decimal | 数值                      |
| profit\_loss\_unit | string  | 数值单位                    |
| word\_record\_id   | int     | 关联 `financial_table.id` |
| sheet              | string  | 关联表单名称                  |
| code               | string  | 指标代码                    |
| file\_name         | string  | 文件名                     |
| batch\_id          | string  | 批次号                     |

Excel 数据模型：
表名：excel\_profit\_loss\_table

| 字段名                          | 类型      | 说明            |
| ---------------------------- | ------- | ------------- |
| sheet                        | string  | 表单名称          |
| code                         | string  | 指标代码          |
| name                         | string  | 指标名称          |
| cur\_rmb\_balance            | decimal | 本期人民币余额（万元）   |
| cur\_rmb\_occur              | decimal | 本期人民币发生额（万元）  |
| cur\_foreign\_balance        | decimal | 本期本外币余额（万元）   |
| cur\_foreign\_occur          | decimal | 本期本外币发生额（万元）  |
| cur\_foreign\_total\_balance | decimal | 本期美元合计余额（万元）  |
| cur\_foreign\_total\_occur   | decimal | 本期美元合计发生额（万元） |
| pre\_rmb\_balance            | decimal | 上期人民币余额（万元）   |
| pre\_rmb\_occur              | decimal | 上期人民币发生额（万元）  |
| pre\_foreign\_balance        | decimal | 上期本外币余额（万元）   |
| pre\_foreign\_occur          | decimal | 上期本外币发生额（万元）  |
| pre\_foreign\_total\_balance | decimal | 上期美元合计余额（万元）  |
| pre\_foreign\_total\_occur   | decimal | 上期美元合计发生额（万元） |
| excel\_row\_index            | int     | Excel 原始数据行号  |
| file\_name                   | string  | 文件名           |
| batch\_id                    | string  | 批次号           |

表名：compare\_link\_table

| 字段名               | 类型     | 说明                                   |
| ----------------- | ------ | ------------------------------------ |
| id                | int    | 主键ID                                 |
| batch\_id         | string | 批次号                                  |
| word\_record\_id  | int    | 关联 `financial_table.id`              |
| excel\_record\_id | int    | 关联 `excel_profit_loss_table.id`，允许为空 |

exception\_group\_table:

| 字段名              | 类型     | 说明                      |
| ---------------- | ------ | ----------------------- |
| id               | int    | 主键ID                    |
| exception\_id    | int    | 异常值ID                   |
| word\_record\_id | int    | 关联 `financial_table.id` |
| field\_name      | string | 异常字段名                   |
| value            | string | 错误内容，后续用于高亮             |
| batch\_id        | string | 批次号                     |

exception\_table:

| 字段名  | 类型     | 说明    |
| ---- | ------ | ----- |
| id   | int    | 主键ID  |
| name | string | 异常值名称 |

#### 4. 代码结构设计，包括主要函数、接口、数据库操作、文件操作等

当前项目按“入口层 -> 服务层 -> 解析层 -> 存储层 -> 工具层”分层组织代码，不包含 API 层。

建议目录结构如下：

```text
project/
├─ run_batch.py
├─ app/
│  ├─ __init__.py
│  ├─ __main__.py
│  ├─ main.py
│  ├─ services/
│  │  ├─ task_service.py
│  │  ├─ word_service.py
│  │  ├─ excel_service.py
│  │  ├─ compare_service.py
│  │  └─ exception_service.py
│  ├─ parsers/
│  │  ├─ word_converter.py
│  │  ├─ word_parser.py
│  │  ├─ excel_parser.py
│  ├─ repositories/
│  │  ├─ base_repository.py
│  │  ├─ financial_repository.py
│  │  ├─ company_profit_loss_repository.py
│  │  ├─ excel_profit_loss_repository.py
│  │  └─ exception_repository.py
│  ├─ models/
│  │  ├─ db_models.py
│  │  ├─ dto.py
│  │  └─ enums.py
│  ├─ utils/
│  │  ├─ file_utils.py
│  │  ├─ unit_utils.py
│  │  ├─ regex_utils.py
│  │  ├─ text_utils.py
│  │  ├─ system_utils.py
│  │  └─ log_utils.py
│  └─ config.py
├─ data/
│  ├─ input/
│  ├─ converted/
│  ├─ export/
│  └─ temp/
└─ tests/
```

##### 4.1 主流程设计

当前主流程拆成以下阶段：

1. 扫描输入目录，识别 Word 文件和 Excel 文件
2. 校验运行环境依赖
3. Word 文件执行 `.doc -> .docx` 转换
4. 对转换后的 `.docx` 执行段落级解析，生成 `financial_table` 和 `company_profit_loss_table`
5. 对 Excel 文件执行表格解析，生成 `excel_profit_loss_table`
6. 对 Word 结果先做内部一致性校验
7. 再执行 Word 与 Excel 的跨源对账
8. 生成批次摘要

当前主控函数实际为：

```python
def run_batch_task(word_dir: str, excel_dir: str, batch_id: str) -> dict[str, int | str]:
    initialize()
    word_files = scan_word_files(word_dir)
    excel_files = scan_excel_files(excel_dir)
    validate_runtime_requirements(word_files, excel_files)
    parse_word_files(word_files, batch_id)
    parse_excel_files(excel_files, batch_id)
    run_word_internal_checks(batch_id)
    run_cross_source_compare(batch_id)
    return build_batch_summary(batch_id)
```

入口方式当前有两种：

- `python -m app.main --word-dir <目录> --excel-dir <目录> --batch-id <批次号>`
- `python run_batch.py --word-dir <目录> --excel-dir <目录> --batch-id <批次号>`

##### 4.1.1 本地运行与接口验证说明

当前项目仍以“先批处理入库，再通过接口查询结果”为主，推荐按以下顺序在本地验证：

1. 安装 Python 依赖
2. 确认系统已安装 `LibreOffice/soffice`
3. 执行批处理，将 Word/Excel 解析结果写入 SQLite
4. 启动 FastAPI
5. 访问接口验证批次、关联列表、关联详情、异常详情

本地安装依赖命令：

```bash
python -m pip install -r requirements.txt
```

运行前环境要求：

- 若输入目录中包含 `.doc` 文件，系统必须能直接调用 `soffice`
- 若输入目录中包含 Word 文件，Python 环境必须安装 `python-docx`
- 若输入目录中包含 Excel 文件，Python 环境必须安装 `xlrd==1.2.0`
- 当前实现面向测试阶段，`app.main` 在每次执行前会先删除库中所有表，再按最新结构重建

推荐的批处理命令示例：

```bash
python -m app.main --word-dir "d:\code\comapreParse\compareData" --excel-dir "d:\code\comapreParse\compareData" --batch-id verify_20260616
```

如果希望使用脚本入口，也可以执行：

```bash
python run_batch.py --word-dir "d:\code\comapreParse\compareData" --excel-dir "d:\code\comapreParse\compareData" --batch-id verify_20260616
```

批处理成功后，数据库中会写入：

- `financial_table`
- `company_profit_loss_table`
- `excel_profit_loss_table`
- `compare_link_table`
- `exception_group_table`

同时可通过以下视图为前端查询提供平铺数据源：

- `vw_compare_link_detail`
- `vw_word_company_detail`
- `vw_word_exception_detail`

启动本地接口命令：

```bash
uvicorn app.api.main:app --reload
```

默认启动后可打开：

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`

当前最小接口验证顺序建议如下：

1. `GET /api/batches`
2. `GET /api/compare-links?batch_id=<批次号>`
3. 从关联列表中取一条 `compare_link.id`，再请求 `GET /api/compare-links/{link_id}`
4. 从详情中取 `word_record.id`，再请求 `GET /api/word-records/{word_record_id}/exceptions`

接口含义说明：

- `/api/batches`：返回当前数据库中可查询的批次列表
- `/api/compare-links`：返回某个批次下的关联列表，供前端左右画线列表页使用
- `/api/compare-links/{link_id}`：返回单条关联详情，包含 Word 主记录、Excel 记录、企业明细列表、异常列表
- `/api/word-records/{word_record_id}/exceptions`：返回某条 Word 主记录对应的异常详情，可用于详情页或后续高亮

若接口返回空列表，优先检查以下几点：

- 批处理是否执行成功
- 传入的 `batch_id` 是否与跑批时一致
- 当前 Python 环境是否已安装 `fastapi`、`uvicorn`、`python-docx`、`xlrd==1.2.0`
- `soffice` 是否可在命令行直接执行
- SQLite 文件 `data_extraction.db` 是否为当前项目目录下最新生成的数据库

##### 4.2 Word 处理模块

`word_converter.py` 负责文档转换，当前保留以下核心函数：

```python
def convert_doc_to_docx(doc_path: str, output_dir: str) -> str:
    """将 .doc 转换为 .docx，当前只使用 soffice headless"""
```

`word_parser.py` 负责按段落解析 Word 文本，核心职责如下：

- 按表单切分段落块
- 解析指标主记录
- 解析企业明细记录
- 生成 `financial_table` 和 `company_profit_loss_table` 两类记录

Word 服务层 `word_service.py` 负责把转换、解析、异常登记、批量落库串起来：

- 单文件内存聚合
- 单文件批量写入 `financial_table`
- 单文件批量写入 `company_profit_loss_table`
- `万元`、`万`、`元`、`亿美元`、`亿元`、`亿`、`万美元`、`美元` 不在解析阶段单独登记异常类型；当前链路不再使用“指标数值单位异常”

##### 4.3 Excel 处理模块

`excel_parser.py` 负责解析 `.xls` 内容，当前实现特点如下：

- 固定前 4 行作为表头区域
- 先展开合并单元格，再识别表头语义
- 识别 `本期/上期 + 人民币/本外币/美元合计 + 余额/发生额`
- 只保留有效指标行，过滤无代码或无有效名称的行
- 指标名称保留原始值，对账时再做“去序号、去空格”的标准化匹配

Excel 服务层 `excel_service.py` 负责：

- 逐文件解析 Excel
- 单文件内存聚合
- 单文件批量写入 `excel_profit_loss_table`

##### 4.4 对账与校验模块

`compare_service.py` 负责两个阶段：

1. Word 内部一致性校验
2. Word 与 Excel 的跨源对账

当前关键函数如下：

```python
def run_word_internal_checks(batch_id: str) -> None:
    """按 file_name + sheet + code + company 分组检查企业明细是否一致"""

def match_excel_record(batch_id: str, financial_record: dict[str, Any]) -> tuple[dict[str, Any] | None, int | None]:
    """先按 sheet，再按 code，再按标准化 name 查找 Excel 记录"""

def calculate_excel_delta(financial_record: dict[str, Any], excel_record: dict[str, Any]) -> tuple[float | None, int | None]:
    """按单位和表单口径动态计算 Excel 差值"""

def compare_amount(financial_record: dict[str, Any], excel_record: dict[str, Any]) -> list[int]:
    """比较 Word 与 Excel 的金额结果"""

def run_cross_source_compare(batch_id: str) -> None:
    """执行完整跨源对账"""
```

当前对账实现要点如下：

- 匹配顺序固定为 `sheet -> code -> name`
- `sheet + code` 命中多条时记 `excel异常`
- `name` 对账使用标准化名称，只做“去前导序号、去空格”后严格相等
- Word 金额按 `direction * amount` 形成带符号结果
- Excel 差值不存库，在对账阶段动态计算
- `发生额` 字段只保留，不参与本次对账
- Excel 差值计算先按“万元”做减法，再根据 Word 单位决定是否除以 `10000`；对需要换算到“亿元/亿美元”口径的结果，严格四舍五入保留 1 位小数
- 选中的余额字段为空时，先记 `余额缺失异常`，再按 `0` 参与计算
- 缺列、列值非法或无法完成计算时记 `计算要求异常`

##### 4.5 数据库操作层

数据库访问统一通过 repository 层封装，不在业务代码中直接拼接业务 SQL。

当前主要仓储职责如下：

- `financial_repository.py`：主记录批量写入、按批次查询、更新异常列表
- `company_profit_loss_repository.py`：企业明细批量写入、按批次查询、更新企业异常
- `excel_profit_loss_repository.py`：Excel 记录批量写入、按批次查询、按 `sheet + code` 查询、按 `sheet` 查询
- `exception_repository.py`：初始化异常字典、写入异常关联表、按批次统计异常数量
- `base_repository.py`：初始化数据库、自动补列、提供通用连接能力

##### 4.6 文件操作与工具函数

当前主要工具模块如下：

- `file_utils.py`：扫描 Word/Excel 文件、创建运行目录
- `unit_utils.py`：金额换算，支持 `convert_to_yi()`、`convert_wan_to_yi()`
- `regex_utils.py`：Word 指标主句和企业明细的正则规则
- `text_utils.py`：指标名称标准化，当前仅做去前导序号、去空格
- `system_utils.py`：校验 `soffice`、`python-docx`、`xlrd==1.2.0` 等运行依赖
- `log_utils.py`：统一日志输出

##### 4.7 日志与验证建议

- 所有文件处理过程都应记录日志，至少包括：文件开始处理、转换成功或失败、解析成功或失败、对账完成、异常数量。
- 对 Word 转换、Word 解析、Excel 解析、金额换算、异常判定分别保留最小可回归测试样例。
- 对典型样例文档做链路验证，确保从“文件输入 -> 数据库结果 -> 异常输出”整条链路可复核。
- 修改解析逻辑后，至少执行一次语法检查和最小编译校验，确保主流程可运行。

##### 4.8 前端展示

- 前端使用js就行
- 关联记录展示。首先左侧展示word，右侧展示对应的excel，利用那个关联表，再word和excel文档之间拉一条线，展示关联记录。
- 详情展示。点击关联记录，弹窗一个页面，可以展示 word 这段的提取结果、excel 这行的提取结果、有异常值，展示他们之间异常值。弹窗应该是可以移动的。

##### 4.9 后端配合前端工作

- 后端展示层建议围绕当前物理表构建 3 个视图或等价的接口查询结果，不额外增加展示专用物理表。
- <br />
  1. 关联列表视图：用于前端左右两侧画连接线。数据来源为 `compare_link_table + financial_table + excel_profit_loss_table`，建议至少输出：`compare_link_table.id`、`batch_id`、`word_record_id`、`excel_record_id`、`financial_table.sheet`、`financial_table.code`、`financial_table.name`、`financial_table.source_ref`、`excel_profit_loss_table.sheet`、`excel_profit_loss_table.code`、`excel_profit_loss_table.name`、`excel_profit_loss_table.excel_row_index`
-  1. 关联详情视图：用于点击连接线后的弹窗详情页。以 `financial_table` 为核心，联合 `compare_link_table`、`excel_profit_loss_table`、`company_profit_loss_table`、`exception_group_table` 以及异常类型映射（`ExceptionType + EXCEPTION_TYPE_NAMES`）进行查询，建议输出 4 个区域：`word_record`、`excel_record`、`company_detail_list`、`exception_list`
-  1. 异常详情视图：用于异常列表展示和后续字段高亮。数据来源为 `exception_group_table + 异常类型映射`，建议至少输出：`word_record_id`、`exception_id`、`exception_name`、`field_name`、`value`、`batch_id`
- 关联详情视图中的 `word_record` 建议直接返回 `financial_table` 当前记录的完整字段；`excel_record` 建议直接返回关联到的 `excel_profit_loss_table` 当前记录完整字段；`company_detail_list` 建议按 `company_profit_loss_table.word_record_id = financial_table.id` 查询
- `exception_list` 建议按 `exception_group_table.word_record_id = financial_table.id` 查询，并通过 `ExceptionType + EXCEPTION_TYPE_NAMES` 映射得到异常名称；其中 `field_name` 和 `value` 直接提供给前端，用于后续字段级高亮
- 当 `compare_link_table.excel_record_id` 为空时，关联详情视图中的 `excel_record` 返回空对象，但仍返回 `word_record` 与 `exception_list`，用于展示“表单无对应异常”或“指标代码异常”等场景
- 后端接口层建议直接按前端页面需求返回聚合后的 JSON 结构，不要求前端自行拼接多张表
- 使用 FastAPI 构建 RESTful 接口，前端通过接口获取数据
