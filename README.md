# Statement Normalize · 跨境流水格式转换

**到了对账那一步，还在手工改日期、金额小数点、筛手续费？** 这个离线工具把一种固定结构的通用流水转换为标准收款 CSV，并单独保留带源行号的审计记录。Python 3.10+，无第三方依赖，不联网。

```sh
git clone https://github.com/s1166921-png/statement-normalize.git
cd statement-normalize
python normalize.py examples/statement.csv demo-out --date-format "%d/%m/%Y" --decimal ","
```

示例完全虚构：4 行流水输出 2 行收款。审计记录中 EUR 净额为 215.45，USD 为 -18.00，不把两种货币相加。

- `receipts.csv`：仅输出正向收款，日期、币种和金额可直接给 [Payout Reconcile](https://github.com/s1166921-png/payout-reconcile) 使用。**服务商流水号不是 Amazon 结算编号**，不会自动填入。只有你已人工核实平台结算编号，才用 `--trust-settlement-id` 复制明确提供的 `settlement_id` 字段。
- 建议把 `receipts.csv` 原样交给对账工具，不要用 Excel 另存后再对账。若需在 Excel 查看，使用「数据 → 从文本/CSV」，导入时把结算编号及其他编号列设为「文本」，避免前导零丢失或长编号被改写。[微软说明](https://support.microsoft.com/en-gb/excel/keeping-leading-zeros-and-large-numbers)
- `audit.json`：原始字段、输入起始行号、对应收款行号、分币种净额和重复行提示。不会静默去重；只是一份格式转换记录，不能证明银行余额或款项身份。
- 输入为 UTF-8 CSV（允许 BOM），列名是 `date,currency,amount,kind,provider_id`，可有 `settlement_id` 和其他列。类型为 `credit`（正数）、`debit`、`fee`（负数）。分隔符可通过 `--delimiter` 指定逗号、分号或 `tab`。不猜日期、币种和小数点，不转换币种。
- 费用单列时保留毛收款及单列费用；源文件只提供净额时，收款输出也保持净额。**不要把同一份流水的两种导出拼一起。** 目前不内置任何银行或服务商的专有导出格式。
- 遇到无效行，退出码为 2，不输出部分收款文件。每次使用一个新输出目录。审计文件包含原始流水字段，不要提交真实数据或把输出上传到公开仓库。

## English

Normalize one documented, generic UTF-8 statement schema to payout-ready credit rows plus a separate JSON audit. Explicit date and decimal formats, exact per-currency signed totals, no implicit FX or fee netting. See the synthetic demo above. Run tests with `python -m unittest -v`. MIT.
