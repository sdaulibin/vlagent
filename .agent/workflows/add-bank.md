---
description: 添加新银行流水识别模板
---

# 添加新银行模板

本工作流用于向 vl_flow 项目添加新的银行流水识别模板。

## 所需信息

请提供以下信息：
1. **银行名称**（如：工商银行）
2. **模板ID**（如：icbc，用于文件命名）
3. **银行关键词**（用于自动识别，如：工商银行、中国工商银行、ICBC）
4. **汇总信息字段**（如：户名、账号、收支汇总等）
5. **交易明细字段**（如：交易时间、收入、支出、余额等）

## 步骤 1：创建银行 Schema 文件

在 `backend/config/bank_schemas/` 目录下创建新的 JSON 文件，格式如下：

```json
{
    "template_id": "模板ID",
    "bank_names": ["银行名称1", "银行名称2"],
    "vertical_line_config": {
        "enabled": false,
        "lines": []
    },
    "summary_schema": {
        "户名": "",
        "账号": "",
        "起止日期": "",
        "收入总金额": "",
        "支出总金额": ""
    },
    "transaction_schema": {
        "流水号": "",
        "交易时间": "",
        "收入": "",
        "支出": "",
        "余额": "",
        "对方账号": "",
        "对方户名": "",
        "摘要": ""
    }
}
```

文件路径: `backend/config/bank_schemas/{template_id}.json`

## 步骤 2：更新银行注册表

编辑 `backend/config/bank_schemas/bank_registry.json`，添加关键词映射：

```json
{
  "keywords": {
    "新银行名称": "template_id",
    "银行别名": "template_id"
  }
}
```

## 步骤 3：创建数据库模型（可选）

如果需要自定义字段，在 `backend/src/transactions/models.py` 中添加：
- Summary 模型（汇总信息）
- Transaction 模型（交易明细）

## 步骤 4：验证配置

1. 重启后端服务
2. 上传该银行的 PDF 流水
3. 确认自动识别银行类型
4. 验证提取的汇总和明细信息

## 现有模板参考

| 银行 | 模板ID | Schema 文件 |
|-----|--------|------------|
| 广发银行 | cgb | cgb.json |
| 招商银行 | cmb | cmb.json |
| 光大银行 | everbright | everbright.json |
| 济宁银行 | jining | jining.json |
| 山东地方银行 | shandong_local | shandong_local.json |
| 邮储银行 | psbc | psbc.json |

