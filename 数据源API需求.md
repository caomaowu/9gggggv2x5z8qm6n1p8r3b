# 数据源 API 需求 — 全套 OKX API v5 透传

## 当前问题

逐条开需求（OI、资金费率、多空比、清算...）效率太低，且后续可能还需要更多衍生品数据（持仓量历史、合约信息、期权数据等）。

## 需求

**直接将 OKX API v5 完整反向代理一套**，所有 `/api/v5/*` 路径透传到 OKX 官方接口，保持参数和返回格式完全一致。

### 实现方式

```
客户端请求:
  GET https://webui.caomaowu.lol/api/v5/public/funding-rate?instId=BTC-USDT-SWAP

代理转发:
  → https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USDT-SWAP
  ← (原样返回 OKX 的 JSON 响应)
```

### 关键要点

1. **路径前缀兼容** — 当前已有 `/api/v1/ohlcv` 等自定义接口保持不动，新增 `/api/v5/*` 全透传
2. **鉴权** — 现有 `Authorization: Bearer <token>` 认证机制维持不变
3. **无需改造客户端** — 代理层透传后，`MarketDataService` 只需加一行 `base_url` 拼接即可调用任意 OKX 原生接口

### 透传后能直接使用的接口（举例）

| 类别 | OKX 端点 | 用途 |
|------|----------|------|
| 行情 | `/api/v5/market/candles` | K线（替代现有 `/api/v1/ohlcv`） |
| 合约 | `/api/v5/public/open-interest` | 未平仓合约 OI |
| 费率 | `/api/v5/public/funding-rate` | 资金费率 |
| 多空 | `/api/v5/public/long-short-ratio` | 多空持仓比 |
| 清算 | `/api/v5/public/liquidation-orders` | 强平数据 |
| 持仓 | `/api/v5/account/positions` | 持仓信息 |
| 深度 | `/api/v5/market/books` | 订单簿 |
| Ticker | `/api/v5/market/ticker` | 24hr行情 |
| 指数 | `/api/v5/market/index-candles` | 指数K线 |

### 当前客户端改动量

透传方案下，客户端几乎不改——`MarketDataService` 加一个通用方法即可：

```python
def _call_okx_v5(self, path: str, params: dict = None) -> dict:
    """直接调用 OKX v5 API（通过代理透传）"""
    return self._make_request(f"/api/v5/{path}", params)
```

后续所有衍生品数据都可以通过一行代码获取，无需逐个接口提需求。
