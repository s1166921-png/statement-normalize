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

## 串起来试用 / Try it with Payout Reconcile

跑完上面的转换命令后，留在 `statement-normalize` 目录，执行：

```sh
git clone https://github.com/s1166921-png/payout-reconcile.git
python payout-reconcile/payout.py payout-reconcile/examples/amazon.tsv demo-out/receipts.csv --amazon-v2 --settlement-decimal "," --coverage 2026-11-01 2026-11-30
```

预期结果：DEMO-A 和 DEMO-B 是待复核候选，DEMO-C 在覆盖流水中没找到。这个虚构流水只有服务商编号、没有可信结算编号，所以没有任何已确认到账。对账命令返回 1 代表有待复核项，不是运行失败。

Expected: A and B are review candidates; C is not found in the statement. Exit code 1 means review items, not a runtime error.

## English

Normalize one documented, generic UTF-8 statement schema to payout-ready credit rows plus a separate JSON audit. Explicit date and decimal formats, exact per-currency signed totals, no implicit FX or fee netting. See the synthetic demo above. Run tests with `python -m unittest -v`. MIT.
