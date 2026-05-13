# Budget Viz 使用与解读指南

这是给 **使用者** 看的说明文档，目的是让你打开 dashboard 时能看懂每一栏数字、每一个面板背后到底做了什么变换，以及为什么有些行被丢掉了。

---

## 1. 整体数据流

```
Card Statements/<bank>/*.csv
        │
        ▼
[Step 2] 各银行 parser          一文件一 parser，列名/符号统一
        │   → 统一 schema: date, description, amount, source, raw_type, raw_status
        ▼
[Step 3] 合并 + 排序             所有源拼成一张表
        │
        ▼
[Step 5] PayPal dedup           丢 PayPal 内部噪音 + 卡账单重复
        │   → 输出 cleaned_df 和 dropped_df（dashboard 的「PayPal dropped rows」面板）
        ▼
[Step 4] Transfer detection     两层规则识别"账户内部转账"
        │   → 给每行打 is_transfer / category="transfer"
        ▼
[Step 6] OpenAI 分类（待做）     给非 transfer 行打 10 个消费类别之一
        │
        ▼
[Step 7] Dashboard 渲染          KPI、图表、可筛选表格
```

---

## 2. 金额符号约定（最重要的一条）

整个项目只有一个不变量：

> **正数 = 消费支出（钱出去）；负数 = 退款 / 收入 / 转入（钱进来）**

不同银行的原始 CSV 符号习惯不一样，所有 parser 内部都做了翻转，保证下游看到的金额统一。例如：

| 来源 | 原始 CSV 里购物是 | parser 处理 |
|---|---|---|
| Chase Sapphire / Freedom Flex / Chase 借记 | 负数 | **翻转**（× −1） |
| Discover 信用卡 / Amex | 正数 | 不翻 |
| Discover 借记 | 拆 Debit / Credit 两列 | 合并 → 支出为正 |
| PayPal | 负数 | **翻转** |
| SoFi 支票 / 储蓄 | 负数 | **翻转** |

---

## 3. 来源识别（source 列怎么来的）

按文件名匹配：

| 文件名规律 | source 取值 |
|---|---|
| `Chase3209_*.CSV` | `chase_sapphire` |
| `Chase5878_*.CSV` | `chase_freedom_flex` |
| `Chase8290_*.CSV` | `chase_debit` |
| `Discover-Last12Months*.csv` | `discover_credit` |
| `Debt-*.csv`（在 Discover 文件夹下） | `discover_debit` |
| `Amx/activity.csv` | `amex` |
| `Paypal/Download.CSV` | `paypal` |
| `SOFI-JointChecking*.csv` | `sofi_checking` |
| `SOFI-JointSavings*.csv` | `sofi_savings` |

最后 4 位数到友好名字的映射在 `config/card_aliases.json`。

---

## 4. Transfer detection（转账识别，category = transfer）

"转账"指你自己账户之间的资金移动（信用卡还款、储蓄/支票互转、券商转账等），**不是消费**，所以从消费总额里排除。识别分两层：

### Layer 1：按规则打标（`config/transfer_rules.json`）

对每一行检查：source + raw_type + description 是否命中规则。命中即为转账。常见规则：
- Chase 借记 `Type=ACCT_XFER / LOAN_PMT / CHASE_TO_PARTNERFI` 等
- Chase 借记 `Type=ACH_DEBIT` **且** 描述含 `CHASE CREDIT CRD AUTOPAY`（其它 ACH_DEBIT 是真账单）
- Chase / Discover 信用卡里类型为 `Payment` 或描述含 `INTERNET PAYMENT - THANK YOU` 等
- SoFi `Type=DIRECT_DEPOSIT / INTEREST_EARNED` 或描述含 `To Savings / From Checking / JPMORGAN CHASE` 等
- 任何账户里描述含 `ROBINHOOD / Moomoo / Discover / American Express / SoFi` 的资金调度

### Layer 2：跨账户配对

剩下没被 Layer 1 命中的行，再做配对：

- 两行来自**不同 source**
- 日期相差 ≤ 3 天
- 金额绝对值相等、一正一负（`amount_a + amount_b ≈ 0`）
- 至少一边描述里有"对家"账户的关键词（CHASE / SOFI / DISCOVER / AMEX / ROBINHOOD / MOOMOO / PAYPAL / TRANSFER / PAYMENT THANK YOU）

两边都打成 transfer。

---

## 5. PayPal dedup（PayPal 去重）

PayPal 是最吵的源——它会把一笔真实消费拆成 3~4 行内部记账。模块 `src/paypal_dedup.py` 处理两件事：

### 5.1 内部过滤（drop_reason = `paypal_internal`）

丢掉这些不是真实消费的行：
1. `Status = Pending`（每个 Pending 都会有 Completed 孪生行）
2. `Type = General Card Deposit`（卡支付的内部对冲）
3. `Type = General Card Withdrawal` **且** 同日同金额有 `Payment Refund` 配对（退款内部对冲）
4. `Type = Bank Deposit to PP Account`（从银行调钱到 PayPal 余额——内部资金调度）
5. 不在保留 type 白名单里的所有 type（`Account Hold for Open Authorization`、`Reversal of General Account Hold`、`ReAuthorization`、`Void of Authorization`、`Other` 等）

**保留 type 白名单**：
- `PreApproved Payment Bill User Payment`（订阅自动扣款）
- `Express Checkout Payment`（一次性结账）
- `General Payment`（一般支付）
- `General PayPal Debit Card Transaction`（PayPal 借记卡刷卡）
- `Payment Refund`（退款）
- `General Authorization`（仅 Completed）
- `General GI/Open wallet Transaction`

### 5.2 跨卡去重（drop_reason = `paypal_cross_card`）

对每条 PayPal 支出（amount > 0），在 Chase Sapphire / Freedom Flex / Chase 借记 / Discover 信用卡 / Discover 借记 / Amex 里找：
- 日期相差 ≤ 3 天
- `abs(amount)` 完全相等
- 描述含 `PAYPAL`（不区分大小写）

找到就把 **PayPal 那行丢掉**（卡那行才是真正的资金来源）。

---

## 6. Dashboard 面板与列含义

### 顶部 KPI 行

| 指标 | 含义 |
|---|---|
| Total rows | 经过 PayPal dedup 之后的全部行数（含 transfer） |
| Spending rows | 非 transfer 的行数（真实消费 + 退款） |
| Transfer rows | 被识别为转账的行数 |
| Sources | 当前数据涉及多少个 source |

### "Rows per source" 表

每个 source 下分别有多少 transfer 行和 spending 行——用来快速发现"这个银行的转账数是不是少得反常"。

### "PayPal dropped rows" 面板

展示 `paypal_dedup` 丢掉的 PayPal 行。每列含义：

| 列 | 含义 |
|---|---|
| `date` | PayPal CSV 的 `Date` 列解析后的日期 |
| `description` | PayPal CSV 的 `Name` 列（商家/对手方姓名，空值表示 PayPal 没填商家——多见于内部行） |
| `amount` | **已经翻转过符号**的金额。正 = 支出，负 = 退款 / 资金调入 |
| `raw_type` | PayPal `Type` 列原值，**未改动**。常见类型见下面对照表 |
| `raw_status` | PayPal `Status` 列原值（`Completed` 或 `Pending`） |
| `drop_reason` | 我们加的列，告诉你这行**为什么被删**。只有两个取值：<br>• `paypal_internal` — 命中"内部过滤"规则（PayPal 自己的记账噪音）<br>• `paypal_cross_card` — 命中"跨卡去重"（卡账单里已经有这一笔） |

**`raw_type` 取值速查**：

| raw_type | 含义 |
|---|---|
| PreApproved Payment Bill User Payment | 订阅自动扣款（Spotify / Patreon / Google 等）|
| Express Checkout Payment / General Payment | 一次性结账 |
| General PayPal Debit Card Transaction | PayPal 借记卡刷卡 |
| Payment Refund | 退款 |
| General Card Deposit | 卡支付的**内部对冲**行（不是消费） |
| General Authorization | 授权占款行（Completed 是有效授权快照，Pending 是中间状态） |
| Account Hold for Open Authorization | 授权占款的开始状态（不是消费） |
| Reversal of General Account Hold | 占款释放（不是消费） |
| ReAuthorization / Void of Authorization | 授权流程中间状态（不是消费） |
| Bank Deposit to PP Account | 从你银行账户调钱进 PayPal 余额（PayPal 内部资金调度，不是消费） |

**一笔订阅可能产生多行**：比如一笔 $25 Visible 订阅扣款，PayPal 会同时记 4 行——一笔真实扣款（`PreApproved` Completed）+ 一笔授权快照 Completed + 一笔授权快照 Pending + 一笔"从银行调 $25 进余额" Pending。我们的逻辑会把后 3 行作为 `paypal_internal` 丢掉，把真实那笔再交给跨卡去重（如果信用卡有 `PAYPAL *VISIBLE $25` 就再丢一次，由信用卡那行代表它）。

### "Transfers panel" 面板

展示所有被识别为转账的行，方便你 sanity check。多一列 `transfer_layer`：

- `layer1` — 由 `config/transfer_rules.json` 规则命中
- `layer2` — 跨账户配对命中

如果你看到一行被误标成转账，可以反过来调 `transfer_rules.json`。

### "Spending transactions" 表

主表，列出所有非转账的行。底下的 checkbox 切换"是否包含 transfer"。

---

## 7. 完成度

| 步骤 | 状态 |
|---|---|
| 1. 项目骨架 | 完成 |
| 2. 各银行 parser | 完成（9 个源） |
| 3. Pipeline 合并 + 原始数据展示 | 完成 |
| 4. Transfer detection（两层） | 完成 |
| 5. PayPal dedup（内部 + 跨卡） | 完成 |
| 6. OpenAI 分类（10 个 category） | 待做 |
| 7. 完整 dashboard（4 张图 + 筛选 + 内联改类别） | 待做 |
| 8. Polish | 待做 |

---

## 8. 如何排查异常数据

- **某个金额对不上**：先去原始 CSV（`Card Statements/<bank>/...`）里搜这个日期 + 金额，确认是 parser 问题还是 CSV 本身的问题。我们的 parser 用 Python `csv` 模块解析，对含逗号的描述安全，不会列错位。
- **某个商家被错误识别为转账**：到 `config/transfer_rules.json` 里看是不是 `description_contains` 命中了不该命中的关键词，调整规则后重启 dashboard。
- **某个 PayPal 订阅消费被错误丢掉**：在 PayPal dropped rows 面板里找它，看 `drop_reason`：
  - 若是 `paypal_cross_card`，去对应信用卡的 CSV 里找 `PAYPAL *<商家>` 同金额的行——通常这才是真正应该保留的"那一笔"。
  - 若是 `paypal_internal`，看 `raw_type` 是不是真的属于内部记账。
