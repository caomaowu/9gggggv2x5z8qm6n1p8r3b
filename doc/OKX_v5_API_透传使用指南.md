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
