# OKX 衍生品历史数据获取指南

> 基于 2026-05-09 实测，通过 `/api/v5/*` 透明代理访问 OKX API v5

---

## 一、数据概览

| 数据类型 | REST 端点 | 粒度 | 指定日期段？ | 回溯范围 | 翻页 | 单次条数 |
|----------|----------|:----:|:----------:|:--------:|:----:|:--------:|
| 资金费率历史 | `public/funding-rate-history` | 8H | ✅ 能 | ~3 个月 | ✅ after | 50 |
| OI 历史 | `rubik/stat/contracts/open-interest-volume` | 1H | ❌ 不能 | 30 天固定 | ❌ | 720 |
| 多空比 | `rubik/stat/contracts/long-short-account-ratio` | 1H / 1D | ❌ 不能 | 30 天固定 | ❌ | 720 |
| Taker 成交量 | `rubik/stat/taker-volume-contract` | 1H | ❌ 不能 | ~4 天固定 | ❌ | 100 |
| 清算数据 | `public/liquidation-orders` | 实时 | ❌ 不能 | 极短（小时级） | ❌ | 16 |

---

## 二、"指定日期段"的真实情况

### ✅ 资金费率 — 唯一支持翻页的衍生品端点

```bash
# 第一页：最近
GET /api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP&limit=50

# 翻页：取上一页最老记录的 fundingTime 作为 after
GET /api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP&limit=50&after=<最老TS>

# 持续翻页可回溯至 ~3 个月前
```

- 费率每 8 小时结算一次（UTC 0/8/16）
- 单页 50 条约覆盖 16 天
- 唯一可以按时间翻页找到历史数据的衍生品端点

### ❌ OI / 多空比 / Taker 量 / 清算 — 固定窗口，无法指定

这几个端点虽然有 `begin`/`end`/`after`/`before` 参数，但**OKX 服务端实际忽略它们**：

```bash
# 以下三种写法返回完全相同的数据
GET /api/v5/rubik/stat/contracts/open-interest-volume?ccy=BTC&period=1H
GET /api/v5/rubik/stat/contracts/open-interest-volume?ccy=BTC&period=1H&after=1744233600000
GET /api/v5/rubik/stat/contracts/open-interest-volume?ccy=BTC&period=1H&before=1744233600000
```

行为等价于：「从此刻往前 N 条」固定窗口，你无法框定 4 月 1 日～4 月 7 日这样的时间范围。

---

## 三、各端点详解

### 3.1 OI 历史

**端点**: `GET /api/v5/rubik/stat/contracts/open-interest-volume`

| 参数 | 说明 |
|------|------|
| `ccy` | 货币，如 `BTC` |
| `period` | `1H`（默认） |
| `begin`/`end` | 毫秒时间戳 — **实际被忽略** |
| `after`/`before` | **实际被忽略** |

- 固定返回 720 条（1H 粒度 = 30 天）
- limit 设为 1000 也只返回 720

**还有当前快照端点**（无历史功能）：
```
GET /api/v5/public/open-interest?instId=BTC-USDT-SWAP
```

---

### 3.2 资金费率

**端点**: `GET /api/v5/public/funding-rate-history`

| 参数 | 说明 |
|------|------|
| `instId` | 永续合约 ID，如 `BTC-USDT-SWAP` |
| `after` | ✅ **有效**，翻页获取更早历史 |
| `limit` | 最大 100，默认 100（实测返回 50） |

- 最大回溯：约 3 个月

**当前费率快照**：
```
GET /api/v5/public/funding-rate?instId=BTC-USDT-SWAP
```

---

### 3.3 多空比

OKX 提供多个维度的多空比端点：

| 维度 | 端点 | 参数 |
|------|------|------|
| 账户维度 | `rubik/stat/contracts/long-short-account-ratio` | `ccy`, `period` |
| 合约维度 | `rubik/stat/contracts/long-short-account-ratio-contract` | `instId`, `period` |
| 顶级交易者（账户） | `rubik/stat/contracts/long-short-account-ratio-contract-top-trader` | `instId`, `period` |
| 顶级交易者（仓位） | `rubik/stat/contracts/long-short-position-ratio-contract-top-trader` | `instId`, `period` |
| 杠杆借币比 | `rubik/stat/margin/loan-ratio` | `ccy`, `period` |

**实测限制**（以 `long-short-account-ratio` 为例）：
- `period` 仅支持 `1H` 和 `1D`（5H/2H/4H/1W 均报错 51000）
- 固定返回 720 条
- `after` 翻页不生效

---

### 3.4 Taker 成交量

**端点**: `GET /api/v5/rubik/stat/taker-volume-contract`

| 参数 | 说明 |
|------|------|
| `instId` | 交易对 ID |
| `period` | `1H`（默认） |
| `unit` | `coin`（币本位）或 `cont`（张数） |
| `begin`/`end` | **实际被忽略** |

- 固定返回 100 条（~4 天）
- `after`/`before` 均不生效

**还有通用 Taker 量端点**：
```
GET /api/v5/rubik/stat/taker-volume?ccy=BTC&instType=SWAP&period=1H
```

---

### 3.5 清算数据

**端点**: `GET /api/v5/public/liquidation-orders`

⚠️ OKX 没有历史清算 REST API，以下端点仅返回极短窗口。

| 参数 | 必填 | 说明 |
|------|:----:|------|
| `instFamily` | ✅ | 产品族，如 `BTC-USDT` |
| `instType` | ✅ | `SWAP` / `FUTURES` / `OPTION` |
| `state` | ✅ | `filled`（已成交）或 `unfilled`（排队中）；`done` 无效 |
| `after` | | **实际被忽略** |

- 固定返回 16 条
- 传 `after=7天前` 直接返回 0 条
- 回溯窗口极短（数小时内）

**如需长期清算历史数据，必须通过 WebSocket 实时订阅并自建存储：**

```json
{
  "op": "subscribe",
  "args": [{
    "channel": "liquidation-orders",
    "instType": "SWAP"
  }]
}
```

连接：`wss://ws.okx.com:8443/ws/v5/public`

---

## 四、翻页能力总表

| 端点 | after 翻页 | before 翻页 | 结论 |
|------|:---------:|:----------:|------|
| `funding-rate-history` | ✅ | — | **唯一可翻页** |
| `open-interest-volume` | ❌ | ❌ | 固定窗口 720 条 |
| `long-short-account-ratio` | ❌ | — | 固定窗口 720 条 |
| `taker-volume-contract` | ❌ | ❌ | 固定窗口 100 条 |
| `liquidation-orders` | ❌ | — | 固定窗口 16 条 |
| `candles` (K线) | ✅ | ✅ | 翻页正常，可框定时间范围 |

> **根本原因**：这些 rubik 统计端点本质是「近期固定窗口快照」而非真正的历史查询接口，`after`/`before` 参数存在但被 OKX 服务端忽略。此行为与代理层无关——直接请求 `www.okx.com` 结果完全一致。

---

## 五、如何突破限制

### 方案 A：定时采集 + 本地存库（推荐）

| 数据类型 | 采集频率 | 每次量 | 存储建议 |
|----------|:--------:|:------:|----------|
| OI | 每小时 | 720 条 | 去重后 append |
| 多空比 | 每小时 | 720 条 | 去重后 append |
| Taker 量 | 每小时 | 100 条 | 去重后 append |
| 资金费率 | 每天 1 次 | 翻页拉全量 | 替换或 upsert |
| 清算 | WebSocket 实时 | 逐条 | append only |

日积月累即可形成自己的历史数据库，超越 OKX 的固定窗口限制。

### 方案 B：直接使用（零开发）

通过项目的透明代理 `/api/v5/*` 即时访问所有 OKX API，无封装层开销。

---

## 六、快速参考卡片

```
资金费率  ✅ 可翻页    ✅ 可指定时间    ~3 个月回溯    50条/页
OI 历史   ❌ 不可翻页  ❌ 固定窗口    30 天固定       720条
多空比    ❌ 不可翻页  ❌ 固定窗口    30 天固定       720条
Taker 量  ❌ 不可翻页  ❌ 固定窗口    ~4 天固定        100条
清算数据  ❌ 不可翻页  ❌ 极短窗口    几小时            16条
```

---

*文档生成时间：2026-05-10*
*数据来源：通过 `https://webui.caomaowu.lol/api/v5/*` 透明代理实测*
