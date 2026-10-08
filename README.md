# sellersprite-skills

> 基于 **卖家精灵（SellerSprite）** MCP 数据接口的 Amazon 选品与市场调研工具集。
> 包含 3 部分：**AI Skill（43 个 MCP 工具）** + **SOP V3.1 全自动选品调研流水线** + **真实调研报告样板**。

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Skill](https://img.shields.io/badge/Skill-Claude%20Code-8A63D2)](https://claude.ai/code)
[![MCP](https://img.shields.io/badge/Protocol-MCP-000000)](https://modelcontextprotocol.io/)

---

## 目录

- [项目简介](#项目简介)
- [仓库结构](#仓库结构)
- [一、AI Skill：sellersprite-amazon-research](#一ai-skillsellersprite-amazon-research)
- [二、SOP V3.1 选品调研流水线](#二sop-v31-选品调研流水线)
- [三、真实调研报告样板](#三真实调研报告样板)
- [四、安装与配置](#四安装与配置)
- [五、已知限制与数据陷阱](#五已知限制与数据陷阱)
- [许可](#许可)

---

## 项目简介

本仓库把「卖家精灵」的电商数据能力封装成可直接落地的调研工作流，覆盖 **选品 → 关键词 → 竞品 → 市场 → 定价 → 评论 → 广告 → 流量 → Listing** 全链路：

| 组成 | 位置 | 说明 |
|------|------|------|
| **AI Skill** | [`skills/`](skills) | Claude Code 技能包：43 个 MCP 工具 + 10 个综合工作流命令 + 17 张战术策略卡 |
| **SOP 流水线** | [`reports-all/catagory-reports/`](reports-all/catagory-reports) | 纯 Python 标准库实现的「抓取 → 六维评分 → 渲染 → 后处理」全自动选品定档 |
| **报告样板** | [`reports-all/`](reports-all) | 真实跑出的多站点选品调研 + 单品类市场全景报告 |

**适用人群**：跨境电商卖家、Amazon 运营、产品开发与选品决策者。

---

## 仓库结构

```
sellersprite-skills/
├── README.md
├── skills/
│   ├── category-selection                          # 类目选择（占位）
│   └── sellersprite-amazon-research-Claude-from_liangdabiao/
│       ├── skill.md                                # Skill 入口（即 SKILL.md）
│       ├── README.md                               # Skill 英文说明
│       ├── comprehensive/                          # 10 个综合分析工作流
│       ├── tactical/                               # 17 张战术策略卡
│       ├── reference/                              # 7 份 MCP 工具参考文档
│       └── scripts/                                # MCP 调用辅助脚本
└── reports-all/
    ├── catagory-reports/
    │   └── uk_fr_yoga-mats_202608/                 # SOP V3.1 多站点选品调研样板
    │       ├── data/config.json                    # 项目配置（类目 / 站点 / 方向 / 设计规范）
    │       ├── dev_config.json                     # 开发调试配置（mock / 限流 / 试跑站点）
    │       ├── sp_diagnose_visual.py               # 产出物诊断
    │       ├── fetch_fr.log                        # FR 站抓取日志
    │       ├── raw/{uk,fr}/                        # API 原始返回（每站 23 个 JSON）
    │       ├── score/scoring.json                  # 六维评分与判档结果
    │       ├── output/*.html                       # 11 个可视化页面
    │       └── scripts/                            # SOP 流水线脚本
    └── sellersprite-amazon-research-reports/
        └── tipsyaudio-us-market/                   # 单品类市场全景报告样板
```

---

## 一、AI Skill：sellersprite-amazon-research

一个 Claude Code 技能包，用自然语言驱动 43 个 MCP 工具完成端到端 Amazon 调研。

### 1.1 能力矩阵

- **智能选品** — 按销量 / 评分 / 上架时间 / 价格 / 卖家类型等条件灵活筛选潜力产品
- **市场全景** — 13 个维度的市场拆解：规模、集中度、价格分布、评分、上架时间、卖家国别、配送方式、A+ 覆盖率等
- **关键词研究** — 挖掘、趋势（ABA / Google Trends）、标题密度漏洞、低垄断蓝海词
- **竞品拆解** — 任意 ASIN 的流量来源、关键词排名、广告策略、评论情感
- **流量分析** — 自然 / 广告流量结构反查，关联流量与广告位识别
- **蓝海机会** — 低品牌垄断、高新品占比、高毛利轻小品
- **评论洞察** — 基于抽样的差评聚类与改良机会提炼
- **定价策略** — 价格区间分布、Keepa 历史趋势、季节定价

### 1.2 综合分析工作流（10 个命令）

见 [`comprehensive/`](skills/sellersprite-amazon-research-Claude-from_liangdabiao/comprehensive)：

| 命令 | 名称 | 核心工具 |
|------|------|----------|
| `/product-research` | 智能选品助手 | `product_research` + `product_node` |
| `/market-analysis` | 市场全景分析 | `market_research` + 12 个分布工具 |
| `/competitor-analysis` | 竞品深度拆解 | `asin_detail` + `traffic_keyword` |
| `/keyword-research` | 关键词选品研究 | `keyword_research` + `keyword_miner` |
| `/listing-optimizer` | Listing 优化诊断 | `traffic_listing` + `keyword_order` |
| `/traffic-analysis` | 流量结构分析 | `traffic_source` + `traffic_keyword_stat` |
| `/opportunity-finder` | 蓝海机会挖掘 | `aba_research_trend` + `google_trend` |
| `/review-insights` | 买家评论洞察 | `review` + NLP 分析 |
| `/pricing-strategy` | 定价策略分析 | `market_price_distribution` |
| `/ad-optimizer` | 广告投放优化 | `keyword_order` + `traffic_keyword` |

### 1.3 战术策略卡（17 张）

见 [`tactical/`](skills/sellersprite-amazon-research-Claude-from_liangdabiao/tactical)，对话中引用名称即可触发：

| 分组 | 策略 | 判定逻辑 |
|------|------|----------|
| **新品爆发** | 新品快速爆发 | 上架 ≤2 月 + 月销 ≥300 + Review ≤100 |
| | 隐形爆款 | 上架 ≤3 月 + 月销 ≥500 + Review ≤50 |
| **关键词趋势** | ABA 高增长趋势词 | 近 3 月持续增长 + 点击不集中 |
| | 流量分散关键词 | 月搜索 ≥5000 + 垄断度 <50% |
| | 标题密度漏洞 | 标题密度 ≤5 的长尾词 |
| **产品缺陷** | 热销低评分产品 | 月销 ≥1000 + 评分 ≤4.2 |
| | 评论语义分析 | 差评 NLP 聚类 → 改良指南 |
| **类目结构** | 低品牌垄断类目 | 品牌集中度 <45% |
| | 高新品占比市场 | 新品占比 >5% 且新品仍出单 |
| | 高毛利轻小品 | FBA ≤$4 + 毛利 ≥50% |
| **流量防伪** | 自然流量反查 | 自然流量占比 >60% |
| | 变体拆解模型 | 定位未覆盖的变体缺口 |
| **机会捕捉** | 本土溢价降维 | 美国卖家 + 高价 + 高销 |
| | FBM 拦截 | FBM 发货 + 月销 ≥300 |
| | 低质量 Listing 高销量 | LQS ≤60 + 月销 ≥400 |
| | 高客单长尾 | 均价 ≥$80 + 搜索量适中 |
| | 季节前置爆破 | 历史同期环比增长 >100% |

### 1.4 MCP 工具清单（43 个 / 8 大类）

完整参数见 [`reference/tools_index.md`](skills/sellersprite-amazon-research-Claude-from_liangdabiao/reference/tools_index.md)：

| 分类 | 数量 | 代表工具 |
|------|:----:|----------|
| ASIN 分析 | 7 | `asin_detail`、`asin_prediction`、`keepa_info`、`bsr_prediction` |
| 商品与竞品 | 3 | `product_research`、`competitor_lookup`、`product_node` |
| 关键词 | 4 | `keyword_miner`、`keyword_research`、`keyword_research_trends`、`keyword_order` |
| 流量 | 6 | `traffic_keyword`、`traffic_source`、`traffic_listing`、`traffic_extend` |
| 市场研究 | 14 | `market_research` + 13 个分布类工具 |
| ABA / 趋势 | 4 | `aba_research_weekly/monthly/trend`、`google_trend` |
| 评论 | 1 | `review` |
| 商标 | 4 | `trademark_list`、`trademark_detail`、`trademark_stats`、`trademark_country_list` |

### 1.5 调用方式

**方式 A · MCP 客户端（推荐）**
```
mcp__sellersprite__<tool_name>       # 例：mcp__sellersprite__product_research
```

**方式 B · curl**
```bash
curl -s -X POST "https://mcp.sellersprite.com/mcp" \
  -H "Content-Type: application/json" \
  -H "secret-key: <YOUR_KEY>" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"market_research","arguments":{"request":{...}}}}'
```

**方式 C · Python**
```python
import json, urllib.request
payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
    "params": {"name": "market_research", "arguments": {"request": {
        "marketplace": "US", "nodeIdPath": "...", "topNum": 10}}}}).encode()
req = urllib.request.Request("https://mcp.sellersprite.com/mcp", data=payload,
    headers={"Content-Type": "application/json", "secret-key": "<KEY>"})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode("utf-8"))
    result = json.loads(data["result"]["content"][0]["text"])
```

**方式 D · 预置脚本**
```bash
python3 scripts/mcp_call.py <tool_name> '{"param":"value"}'
```

### 1.6 参数模式

| 模式 | 形态 | 适用工具 |
|------|------|----------|
| **A 扁平参数** | `{"marketplace":"US","asin":"B0XXXXX"}` | `asin_detail`、`review`、`keyword_research_trends`、`traffic_source` |
| **B `request` 嵌套** | `{"request":{"marketplace":"US","nodeIdPath":"...","size":50}}` | 绝大多数筛选 / 搜索类工具 |

> 识别方法：看工具 schema 的 `required` —— `["request"]` 用嵌套对象，其余为扁平参数。

---

## 二、SOP V3.1 选品调研流水线

`catagory-reports/` 下的样板由一套**零人工、纯标准库**的 Python 流水线驱动，实现 "多站点类目 → 六维评分 → 自动判档 → 可视化报告" 的闭环。

### 2.1 流水线阶段

```
STEP 1-6  抓取      sp_fetch_data.py            # sellersprite CLI → raw/{mp}/*.json
STEP 7    评分      sp_score.py                 # 归一化 → 六维打分 → 加权 → 判档 → score/scoring.json
STEP 8    渲染      sp_render_split.py          # index.html + {mp}.html
                   sp_render_seasonality.py / sp_render_needs.py / sp_render_kwneeds.py
                   sp_render_report.py
         后处理    sp_add_gtrend.py / sp_add_xnav.py / sp_add_methodology_nav.py
共享库    ─         sp_common.py（渲染 + 业务计算）、utils.py（限流 / mock / 退避）
诊断      ─         sp_diagnose.py / sp_diagnose_visual.py
```

### 2.2 方向判定（Direction）

| 供需比中位数 | 方向 | 策略 |
|:---:|------|------|
| > 10 | **D1 需求驱动** | 蓝海 / 供不应求，优先切入 |
| 3 ~ 10 | **D2 红海差异化** | 供需均衡，拼供应链与微创新 |
| < 3 | **D3 垂直细分** | 极度内卷，必须深耕细作 |

### 2.3 六维评分权重

| 维度 | 考核点 | D1 | D2 | D3 |
|------|--------|:--:|:--:|:--:|
| 1 市场需求 | GMV / 销量波动 | 25% | 5% | 10% |
| 2 分散度 | CR10 | 20% | 15% | 30% |
| 3 定价空间 | 毛利率 | 15% | 25% | 15% |
| 4 新品机会 | New Release / 头部硬伤 | 15% | 25% | 20% |
| 5 需求强度 | 同比 / 环比 / 评论增速 | 25% | 10% | 25% |
| 6 品牌与合规 | 认证 / 专利 | 一票否决 | 20% | 一票否决 |

### 2.4 三档判定（Tier）

加权总分（六维加权，满分为 5 分）对应三档；报告页面按 ×20 归一化为 100 分制展示。

| 档位 | D1 阈值 | D2 阈值 | D3 阈值 |
|------|:--:|:--:|:--:|
| **T1 必做** | ≥ 4.00（80） | ≥ 4.25（85） | ≥ 3.75（75） |
| **T2 可做（复议）** | 3.00 ~ 3.99（60~79） | 3.50 ~ 4.24（70~84） | 2.75 ~ 3.74（55~74） |
| **T3 放弃** | < 3.00（<60） | < 3.50（<70） | < 2.75（<55） |

**否决规则（Veto）**：如 `D6 = 0` → 直接 T3；`D3 = 1~2`（D2 方向）→ 强制 T3；`D1 = 1`（D3 方向但 `D5 = 5`）→ 破格保 T2。
**唯一破格通道**：Skill 25 季节前置爆破可在双条件满足时升 1 级。

### 2.5 产出页面

以 `uk` / `fr` 双站点为例，输出 **11 个单文件 HTML**（无外部依赖，可直接浏览器打开）：

| 文件 | 内容 |
|------|------|
| `index.html` | 选品总览：站点矩阵、Top 3、避坑速查、六维评分矩阵 |
| `{mp}.html` | 单站详情：六维评分卡、KPI、方向判定、集中度与分布图 |
| `{mp}_seasonality.html` | 季节性 & 趋势：月搜索量折线、旺淡季、12 月热力图、Google Trends 漏斗 |
| `{mp}_needs.html` | 用户需求：差评痛点聚类（Skill 24）、变体缺口（Skill 27） |
| `{mp}_kwneeds.html` | 关键词机会：高转化长尾（Skill 26）、流量分散蓝海词（Skill 20） |
| `{mp}_report.html` | 选品报告：最终评分、六维明细、核心结论、进入策略 / ROI |

### 2.6 可视化设计规范

统一使用 Amazon 风格深色调色板（定义于 `data/config.json` 与 `sp_common.py`）：

```css
--topbar-bg:#0A1A2F;  --brand-yellow:#FCD34D;  --link:#2A7DE1;
--price:#D97A2E;      --cta:#FCD34D;
```

图表基于 [Chart.js](https://www.chartjs.org/) CDN，含 380 / 640 / 900 / 1100 四档响应式断点。

---

## 三、真实调研报告样板

### 3.1 `uk_fr_yoga-mats_202608` — 多站点类目选品

- **类目**：Yoga Mats（瑜伽垫） ｜ **站点**：UK + FR ｜ **方向**：D2 ｜ **SOP**：V3.1
- **结论**：UK 六维 `3/3/3/3/1` 加权 3.0 → **T3**；FR 六维 `3/1/4/3/3` 加权 3.1 → **T3**
- **关键 KPI**：UK 月 GMV ≈ $0.79M（同比 -30.8%）、FR 月 GMV ≈ $0.24M、FR CR10 达 81%（高度垄断）
- **数据源**：经 `sellersprite-cli` 抓取的 20 余类原始 JSON（市场分布 / 关键词 / Google 趋势 / 竞品 / 评论 / 销量预测）

### 3.2 `tipsyaudio-us-market` — 单品类市场全景

- **站点**：Amazon US ｜ **叶子节点**：`11091801:11974521:8882489011:11974711:11974761`（Wireless Lavalier Condenser Microphones）
- **产出**：[market_report.md](reports-all/sellersprite-amazon-research-reports/tipsyaudio-us-market/market_report.md) + `market_report.html` + `research_data.json`
- 该样板同时演示了 **鉴权失败时的降级路径**（MCP 返回 `secret_invalid` 时改用公开数据源并逐项标注估计值）

---

## 四、安装与配置

### 4.1 环境要求

- Python **≥ 3.10**（样板脚本使用 3.13 运行）
- `sellersprite-cli`（用于 SOP 流水线抓取数据）
- 一个可用的 **卖家精灵账号** 及其 API 密钥
- （可选）Claude Code CLI + MCP 客户端

### 4.2 克隆仓库

```bash
git clone https://github.com/Livin-0/sellersprite-skills.git
cd sellersprite-skills
```

### 4.3 配置 MCP 连接

在项目根目录创建 `.mcp.json`：

```json
{
  "mcpServers": {
    "sellersprite": {
      "url": "https://mcp.sellersprite.com/mcp",
      "headers": {
        "secret-key": "YOUR_SECRET_KEY"
      }
    }
  }
}
```

> **必须遵守**：密钥通过 `headers.secret-key` 传入，**不是** URL 参数（`?key=`）、**不是** `Authorization` 头；endpoint 必须为 `/mcp`，
> **不是** `/sse`。调用时建议补上 `Accept: application/json, text/event-stream`，否则可能 HTTP 400。

### 4.4 安装 Skill

Skill 从 `skills/sellersprite-amazon-research-Claude-from_liangdabiao/`（入口 `skill.md`）自动发现；将目录放到 Claude Code 的 `.claude/skills/` 下即可通过 `/product-research`、`/market-analysis` 等命令调用。

### 4.5 运行 SOP 流水线

```bash
cd reports-all/catagory-reports/<项目目录>
# 1) 先改 data/config.json 指定类目与站点，dev_config.json 可开 mock 试跑
python scripts/sp_fetch_data.py      # 抓取原始数据
python scripts/sp_score.py           # 六维评分 + 判档
python scripts/sp_render_split.py    # 渲染 index / 站点页
python scripts/sp_render_seasonality.py
python scripts/sp_render_needs.py
python scripts/sp_render_kwneeds.py
python scripts/sp_render_report.py
python scripts/sp_diagnose.py        # 产出物自查
```

调试可设 `dev_config.json` 中 `"mock_mode": true`，在**零 API 消耗**下复用 `mock_data/` 走通全链路渲染。

### 4.6 密钥安全

⚠️ **请勿把真实密钥提交到仓库。** 所有脚本均通过环境变量读取密钥，不再硬编码：

```python
import os
SECRET_KEY = os.environ["SELLERSPRITE_SECRET_KEY"]   # 从环境变量读取
```

```bash
set SELLERSPRITE_SECRET_KEY=你的密钥        # Windows
export SELLERSPRITE_SECRET_KEY=你的密钥     # macOS / Linux
```

`.env`、`.mcp.json` 已加入 [`.gitignore`](.gitignore)。**若历史上曾提交过真实密钥，请立即在卖家精灵后台轮换**——从工作区删除文件并不能清除 git 历史中的记录。

---

## 五、已知限制与数据陷阱

> 以下为实测踩坑结论，直接决定报告可信度，务必遵守。

### 5.1 工具行为限制

| 工具 | 限制 | 应对 |
|------|------|------|
| `review` | 每次最多返回 **20 条**，`size` 参数无效 | 报告中必须注明「仅 20 条样本」，评分分布不代表总体 |
| `traffic_source` | 可能返回**无关产品**流量；需扁平参数 + `"q":"asin"` | 改用 `traffic_keyword` + `traffic_keyword_stat` 组合 |
| `keyword_research` | **忽略 `keyword` 筛选**，返回全局热词 | 定向挖词改用 `keyword_miner` |
| SSE 传输 | CDN 会话亲和导致 302 / 504 | 始终用 HTTP POST 到 `/mcp`，放弃 SSE |
| `product_node` | `nodeLabelLocale`（中文翻译）**经常错**（Microphones → 显微镜） | 始终以英文 `nodeLabelPath` 为准；类目必须用**叶子节点** |

### 5.2 字段映射与刻度陷阱

- **改名规律**：`totalUnits→units`、`totalAmount→revenue`、`reviews→ratings`、`bsrRank→bsr`、`sellerType→fulfillment`、`*Ratio→*Proportion`
- **刻度换算**：集中度类 `top*Crn` / `l*NewRatio` / `purchaseRate` / `cvsShareRate` 为 **0~1 小数** → 展示需 ×100；`returnRatio` / `*Proportion` 已是百分数，不再换算
- **响应字段与文档不符**（按实际取值）：
  - `keyword_research_trends`：用 `time` / `search` / `chainGrowth` / `yearlyGrowth` / `purchase`，**不是** `month` / `searches` / `growth`
  - `aba_research_trend`：只有 `searches` / `rank`，**没有** `clickShareRate` / `conversionShareRate`
  - `traffic_keyword_stat`：用 `keywords` / `ranks` / `ads`
  - `review`：用 `content` / `date`，**不是** `body` / `createTime`
  - `keepa_info`：用 `buyBox` / `bsr` 数组（`{timePoint, value}`），**不是** `currentPrice` / `bsrHistory`

### 5.3 报告质量门禁（20 项）

生成报告后必须自查，重点包括：HTML 实体解码（`html.unescape`）、多卖家/多变体销量汇总去重标注 ⚠️、关键词列表排除品牌词与无关泛词、ASIN 自身数据与市场数据分区标注、混合类目识别、数值格式化（千分位 / 一位小数 / `$X.XX`）、筛查口径记录等。完整清单见 `skill.md` 第八节。

---

## 许可

MIT

---

## 致谢

- 卖家精灵（SellerSprite）提供电商数据与 MCP 接口
- Skill 部分参考并整合自 `liangdabiao` 的开源实现
</content>