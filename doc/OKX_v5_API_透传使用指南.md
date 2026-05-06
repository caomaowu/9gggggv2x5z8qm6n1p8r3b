# OKX API v5 透传使用指南

## 概述

`/api/v5/*` 是 OKX 官方 API v5 的**透明反向代理**。所有请求原封转发到 `https://www.okx.com/api/v5/*`，参数和返回格式与 OKX 官方完全一致。

这意味着你可以直接参考 [OKX API v5 官方文档](https://www.okx.com/docs-v5/) 来调用任意接口，无需等待服务端逐个适配。

## 基础信息

| 项目 | 值 |
|------|-----|
| 服务器地址 | `https://webui.caomaowu.lol` |
| 代理前缀 | `/api/v5` |
| 上游地址 | `https://www.okx.com/api/v5` |
| 认证方式 | `Authorization: Bearer <token>` |
| 支持方法 | GET, POST |
| 限流 | 600 次/分钟/IP |

## 认证

所有 `/api/v5/*` 请求必须带 Bearer Token：

```bash
curl -H "Authorization: Bearer <your-token>" \
     "https://webui.caomaowu.lol/api/v5/public/funding-rate?instId=BTC-USDT-SWAP"
```

也支持以下替代头：
- `X-API-Token: <token>`
- `api-token: <token>`

## 原理

```
你的应用                       代理服务                        OKX 官方
───────                       ────────                       ────────
GET /api/v5/market/ticker     strip Auth 头                  GET /api/v5/market/ticker
Authorization: Bearer xxx ──▶ 追加 User-Agent ────────────▶
                              转发 query/body/OKX签名头
                                                          ◀── {"code":"0","data":[...]}
◀── 原样返回 ─────────────────
```

代理层不做任何数据解析、转换、包装。你拿到的就是 OKX 返回的原始 JSON。

## 公共行情接口（无需 OKX 密钥）

### 资金费率

```bash
curl -H "Authorization: Bearer <token>" \
     "https://webui.caomaowu.lol/api/v5/public/funding-rate?instId=BTC-USDT-SWAP"
```

返回示例：
```json
{
  "code": "0",
  "msg": "",
  "data": [{
    "instId": "BTC-USDT-SWAP",
    "instType": "SWAP",
    "fundingRate": "0.0001",
    "nextFundingRate": "0.00015",
    "fundingTime": "1764921600000",
    "nextFundingTime": "1764943200000"
  }]
}
```

### 未平仓合约 (OI)

```bash
curl -H "Authorization: Bearer <token>" \
     "https://webui.caomaowu.lol/api/v5/public/open-interest?instId=BTC-USDT-SWAP"
```

### 多空持仓比

```bash
curl -H "Authorization: Bearer <token>" \
     "https://webui.caomaowu.lol/api/v5/public/long-short-ratio?instId=BTC-USDT-SWAP&period=5m&limit=50"
```

### 强平数据

```bash
curl -H "Authorization: Bearer <token>" \
     "https://webui.caomaowu.lol/api/v5/public/liquidation-orders?instId=BTC-USDT-SWAP&limit=50"
```

### K线

```bash
# 获取最新 100 根 1 小时 K 线
curl -H "Authorization: Bearer <token>" \
     "https://webui.caomaowu.lol/api/v5/market/candles?instId=BTC-USDT-SWAP&bar=1H&limit=100"

# 获取 2026-05-01 12:00 之前的 3 根 K 线（历史回测场景）
# ⚠️ 注意：OKX 原生语义中 after 返回指定时间之前的数据
curl -H "Authorization: Bearer <token>" \
     "https://webui.caomaowu.lol/api/v5/market/candles?instId=BTC-USDT-SWAP&bar=1H&limit=3&after=1777612800000"
```

> **⚠️ `after` / `before` 参数说明**：
> OKX 原生 API 的分页参数语义如下，与直觉相反：
> - `after`：返回指定时间**之前**的 K 线（用于"获取某时间为止的 N 根 K 线"）
> - `before`：返回指定时间**之后**的 K 线
> 
> 如需更直观的 `start_time` / `end_time`（ISO8601 格式），可使用 `/api/v1/ohlcv`。

### Ticker（24hr 行情）

```bash
curl -H "Authorization: Bearer <token>" \
     "https://webui.caomaowu.lol/api/v5/market/ticker?instId=BTC-USDT-SWAP"
```

### 订单簿

```bash
curl -H "Authorization: Bearer <token>" \
     "https://webui.caomaowu.lol/api/v5/market/books?instId=BTC-USDT-SWAP&sz=10"
```

### 指数K线

```bash
curl -H "Authorization: Bearer <token>" \
     "https://webui.caomaowu.lol/api/v5/market/index-candles?instId=BTC-USD&bar=1H&limit=100"
```

### 合约信息

```bash
curl -H "Authorization: Bearer <token>" \
     "https://webui.caomaowu.lol/api/v5/public/instruments?instType=SWAP"

# 单个合约
curl -H "Authorization: Bearer <token>" \
     "https://webui.caomaowu.lol/api/v5/public/instruments?instType=SPOT&instId=BTC-USDT"
```

## 私有接口（需要 OKX 密钥签名）

私有接口（如账户持仓、下单等）需要客户端自行生成 OKX 签名。代理层会透传以下签名头：

| 请求头 | 说明 |
|--------|------|
| `OK-ACCESS-KEY` | API Key |
| `OK-ACCESS-SIGN` | 签名（HMAC SHA256） |
| `OK-ACCESS-TIMESTAMP` | 时间戳（ISO8601） |
| `OK-ACCESS-PASSPHRASE` | API 密码短语 |

### Python 示例（带签名）

```python
import hmac
import hashlib
import base64
import time
import requests
import json

OKX_API_KEY = "your-okx-api-key"
OKX_SECRET = "your-okx-secret"
OKX_PASSPHRASE = "your-passphrase"
PROXY_BASE = "https://webui.caomaowu.lol"
PROXY_TOKEN = "<your-proxy-token>"


def okx_v5(path: str, params: dict = None, method: str = "GET") -> dict:
    """通过代理调用 OKX API v5（自动签名）"""
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

    body = json.dumps(params) if method == "POST" and params else ""
    prehash = timestamp + method.upper() + f"/api/v5/{path}" + body
    sign = base64.b64encode(
        hmac.new(
            OKX_SECRET.encode(), prehash.encode(), hashlib.sha256
        ).digest()
    ).decode()

    headers = {
        "Authorization": f"Bearer {PROXY_TOKEN}",
        "OK-ACCESS-KEY": OKX_API_KEY,
        "OK-ACCESS-SIGN": sign,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": OKX_PASSPHRASE,
        "Content-Type": "application/json",
    }

    url = f"{PROXY_BASE}/api/v5/{path}"
    kwargs = {"headers": headers}
    if params:
        if method == "GET":
            kwargs["params"] = params
        else:
            kwargs["data"] = json.dumps(params)

    resp = requests.request(method, url, **kwargs, timeout=10)
    return resp.json()


# 获取持仓
positions = okx_v5("account/positions", {"instType": "SWAP"})
print(positions)
```

## Python 快速集成

```python
import requests


class OKXProxy:
    """OKX v5 代理客户端 — 一行代码调用任意 OKX 接口"""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token

    def call(self, path: str, params: dict = None, method: str = "GET",
             okx_headers: dict = None) -> dict:
        """调用 OKX API v5 任意接口

        Args:
            path:    OKX API 路径（不含 /api/v5 前缀），如 'market/ticker'
            params:  Query 参数（GET）或请求体（POST）
            method:  GET 或 POST
            okx_headers: 私有接口签名头（可选）
        """
        headers = {"Authorization": f"Bearer {self.token}"}
        if okx_headers:
            headers.update(okx_headers)

        url = f"{self.base_url}/api/v5/{path}"
        kwargs = {"headers": headers, "timeout": 10}

        if method == "GET":
            kwargs["params"] = params
        else:
            kwargs["json"] = params

        resp = requests.request(method, url, **kwargs)
        return resp.json()


# 使用
client = OKXProxy("https://webui.caomaowu.lol", "<your-token>")

# 公共接口 — 一行搞定
funding = client.call("public/funding-rate", {"instId": "BTC-USDT-SWAP"})
oi      = client.call("public/open-interest", {"instId": "BTC-USDT-SWAP"})
ticker  = client.call("market/ticker", {"instId": "ETH-USDT-SWAP"})
books   = client.call("market/books", {"instId": "BTC-USDT-SWAP", "sz": "10"})
```

## 与旧 `/api/v1/*` 接口的区别

| | `/api/v1/*`（旧） | `/api/v5/*`（新） |
|---|---|---|
| 接口范围 | 仅 ohlcv / ticker / orderbook 等 4 个 | OKX v5 **全部**接口 |
| 响应格式 | 服务端包装 `{status, data}` | OKX 原始 JSON `{code, data}` |
| 参数名 | 自定义（如 `timeframe`） | OKX 原生（如 `bar`） |
| 新增接口 | 需服务端逐个开发 | **零开发，立即可用** |
| 适用场景 | 现有代码 | 新接入 / 需要完整 OKX API |

**建议**：新代码统一使用 `/api/v5/*`。

## 错误处理

| 状态码 | 含义 |
|--------|------|
| 200 | 正常。检查 `code` 字段：`"0"` 成功，其他值见 OKX 错误码 |
| 401 | 代理层认证失败（Token 无效或缺失） |
| 429 | 触发代理层限流（600次/分钟） |
| 502 | 无法连接 OKX API（网络故障或 OKX 不可达） |
| 504 | OKX API 超时（30秒） |

OKX 自身的业务错误码会包含在 200 响应体的 `code` 和 `msg` 字段中，参考 [OKX 错误码文档](https://www.okx.com/docs-v5/#error-code)。

## 可用接口速查

所有 OKX API v5 接口均可使用，以下是常用类别：

| 类别 | 路径前缀 | 认证 |
|------|---------|------|
| 市场行情 | `market/*` | 无需 OKX 密钥 |
| 公共数据 | `public/*` | 无需 OKX 密钥 |
| 交易 | `trade/*` | 需要 OKX 签名 |
| 账户 | `account/*` | 需要 OKX 签名 |
| 资金 | `asset/*` | 需要 OKX 签名 |

完整列表 → [OKX API v5 官方文档](https://www.okx.com/docs-v5/)

## 注意事项

1. **任何 OKX v5 接口都能调** — 看到好的接口不用提需求，直接 `proxy.call('path', params)` 即可
2. **私有接口签名由客户端负责** — 代理层不接触你的 OKX API 密钥
3. **限流是代理层 + OKX 双重限制** — 建议客户端也做适当频率控制
4. **POST 请求需要设置 `Content-Type: application/json`**

---

## 📌 实战经验：`market/candles` vs `market/history-candles`

> 记录日期：2026-05-06
> 问题：批量回测工具对较早日期返回空数据（0条K线）

### 发现

OKX 有两个蜡烛图端点，**对历史数据的支持能力完全不同**：

| 端点 | 用途 | `after` 翻页范围 | 适用场景 |
|------|------|------------------|----------|
| `/api/v5/market/candles` | 实时查询 | **~500 条** (1H≈21天) | `latest` 模式、实时行情 |
| `/api/v5/market/history-candles` | 历史查询 | **不受限** (500天+) | `to_end` / `date_range` 回测模式 |

### 测试数据（2026-05-06 实测）

| after 回溯天数 | candles | history-candles |
|---------------|---------|-----------------|
| 30天 | 40条 ✅ | 40条 ✅ |
| 60天 | **0条 ❌** | 40条 ✅ |
| 180天 | 0条 ❌ | 40条 ✅ |
| 500天 | 0条 ❌ | 40条 ✅ |

### 按K线周期的影响

`market/candles` 的 ~500 条限制对不同周期的影响：

| 周期 | 500条约覆盖 | 实际影响 |
|------|------------|---------|
| 1m | ~8小时 | 严重受限 |
| 15m | ~5天 | 严重受限 |
| 1h | ~21天 | 受限 |
| 4h | ~83天 | 基本够用 |
| 1d | ~500天 | 充裕 |

### 最佳实践

```python
# ✅ 正确：根据查询类型选择端点
if start_date or end_date:
    endpoint = "market/history-candles"  # 历史查询，全量数据
else:
    endpoint = "market/candles"          # 实时查询，更快

data = proxy.call(endpoint, params)
```

### 链式翻页也受同样的限制

即使通过多次请求链式翻页（用上一批最早时间戳作为下一批的 `after`），`market/candles` 最多也只能拿到 ~500 条。要突破限制，必须切到 `market/history-candles`。

### 与 v1 API (`/api/v1/ohlcv`) 的关系

反代的 v1 `/api/v1/ohlcv` 能拿到长历史数据，推测是因为 v1 内部调用的也是 `market/history-candles` 端点（而非 `market/candles`）。


---


## 📌 实战经验：衍生品/情绪数据端点能力

> 记录日期：2026-05-06 | 修正日期：2026-05-06
> 目的：测试各端点对历史数据的回溯能力和 `after` 翻页支持

### 端点能力总览（修正版）

| 端点 | `after`翻页 | 数据窗口 | 最长回溯 | 粒度 |
|------|:--:|------|------|------|
| `market/history-candles` | ✅ | 300条/次 | **730天+** | 任意周期 |
| `public/funding-rate-history` | ✅ | 50条/次 | **~90天** | 每8h |
| `rubik/.../open-interest-volume` | ❌ | 5m:576 / 1H:720 / 1D:180 | 2天/30天/180天 | 5m/1H/1D |
| `rubik/.../long-short-account-ratio` | ❌ | 1H:720 / 1D:180 | 30天/180天 | 1H/1D |
| `rubik/stat/margin/loan-ratio` | 待测 | 180条 | 待验证 | 1D |
| `public/liquidation-orders` | ❌ | ~16条 | 仅最近 | 实时 |
| `public/open-interest` | ❌ | 1条 | 无(快照) | — |
| `public/funding-rate` | ❌ | 1条 | 无(快照) | — |

### ⚠️ 关键发现：rubik 端点忽略 `after` 参数

**rubik 统计端点返回固定数量的最新数据，`after` 参数完全无效**。

实测验证：
```
多空比 1D, after=  7d: 180条, 最早=2025-11-07  ← 最新180条，非7天前
多空比 1D, after=365d: 180条, 最早=2025-11-07  ← after完全没变！
OI 1D,    after=  7d: 180条, 最早=2025-11-07  ← 同上
OI 1D,    after=365d: 180条, 最早=2025-11-07  ← 同上
```

结论：无论 `after` 传什么值，rubik 端点永远返回最新的 180 条（1D）或 720 条（1H）。

只有 `funding-rate-history` 和 `market/history-candles` 这两个端点真正支持 `after` 翻页。

### 各端点详细说明

#### 1. OI 持仓量 (`rubik/stat/contracts/open-interest-volume`)

```bash
curl -H "Authorization: Bearer <token>" \
  "https://webui.caomaowu.lol/api/v5/rubik/stat/contracts/open-interest-volume?ccy=BTC&period=1D&limit=100"
```

- **参数**：`ccy` 必填（如 `BTC`），`period` 支持 `5m`/`1H`/`1D`（不支持 4H）
- **after**：❌ 忽略，永远返回最新固定条数
- **时间戳**：周期结束时间，精确到整点（分钟和秒为 `:00`）
- **1D 时间戳示例**：`2026-05-05 16:00:00 UTC`（= 北京时间次日 00:00，是 UTC+8 的日线收盘时间）
- **数据格式**：`[ts, oi, vol]`，倒序排列（最新在前）

#### 2. 多空比 (`rubik/stat/contracts/long-short-account-ratio`)

```bash
curl -H "Authorization: Bearer <token>" \
  "https://webui.caomaowu.lol/api/v5/rubik/stat/contracts/long-short-account-ratio?ccy=BTC&period=1D&limit=100"
```

规则同 OI，`after` 同样被忽略。

#### 3. 资金费率 (`public/funding-rate-history`)

```bash
curl -H "Authorization: Bearer <token>" \
  "https://webui.caomaowu.lol/api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP&limit=50&after=<ts>"
```

- **after**：✅ 支持，可翻页到 ~90 天前
- 每次结算产生一条记录（每8h），约 200-300 条总数据

#### 4. 清算订单 (`public/liquidation-orders`)

```bash
# ✅ 正确参数
curl -H "Authorization: Bearer <token>" \
  "https://webui.caomaowu.lol/api/v5/public/liquidation-orders?instType=SWAP&uly=BTC-USDT&state=filled&limit=100"
```

- **参数陷阱**：必须用 `uly` 或 `instFamily`（不能用 `instId`），必须有 `instType` 和 `state`
- **after**：❌ 不支持，仅返回最近 ~16 条

### 回测场景的实用建议

| 回测周期 | OI | 多空比 | 资金费率 |
|---------|-----|--------|---------|
| 4H | 1H聚合(~30天) | 1H聚合(~30天) | ✅ 直接可用(~90天) |
| 1D | ✅ 直接可用(180天) | ✅ 直接可用(180天) | ✅ 直接可用(~90天) |
| 1H | ✅ 直接可用(30天) | ✅ 直接可用(30天) | ✅ 直接可用(~90天) |

### 最佳实践：区分端点类型

| 类型 | 特征 | `after` | 示例 |
|------|------|:--:|------|
| 历史端点 | 支持翻页，可回溯 | ✅ | `history-candles`, `funding-rate-history` |
| rubik统计 | 固定窗口，不可翻页 | ❌ | `open-interest-volume`, `long-short-account-ratio` |
| 快照端点 | 仅当前值 | N/A | `open-interest`, `funding-rate` |
| 实时端点 | 仅最近事件 | ❌ | `liquidation-orders` |

