[根目录](../../CLAUDE.md) > **utils**

# Utils 模块 - 工具函数层

## 📋 模块职责

Utils 模块是 QuantAgent 系统的工具函数层，提供技术指标计算、图表生成、性能监控、智能文件管理、样式配置等通用工具功能，为整个系统提供基础支撑。

## 🏗️ 模块结构

```
utils/
├── technical_indicators.py   # 技术指标计算工具
├── chart_generator.py        # 图表生成工具
├── performance.py            # 性能监控工具
├── static_util.py            # 静态工具函数（已优化文件管理）
├── graph_util.py             # 图形工具（已优化文件管理）
├── color_style.py            # 颜色样式配置
├── style_config.py           # 样式配置管理
├── file_manager.py           # 🆕 智能文件管理系统
└── temp_file_manager.py      # 🆕 临时文件管理器
```

## 📊 技术指标工具 (`technical_indicators.py`)

### 核心类: `TechnicalTools`

**主要功能**:
- MACD (移动平均收敛散度) 计算
- RSI (相对强弱指数) 计算
- ROC (变动率指标) 计算
- Stochastic (随机指标) 计算
- Williams %R 计算

**技术特性**:
- 基于 TA-Lib 库的专业计算
- 完整的错误处理机制
- 性能监控集成
- 标准化数据输出格式

**核心方法**:
```python
class TechnicalTools:
    @performance_monitor("MACD计算")
    def calculate_macd(self, data: pd.DataFrame, fastperiod: int = 12,
                      slowperiod: int = 26, signalperiod: int = 9) -> dict:

    @performance_monitor("RSI计算")
    def calculate_rsi(self, data: pd.DataFrame, timeperiod: int = 14) -> dict:

    @performance_monitor("ROC计算")
    def calculate_roc(self, data: pd.DataFrame, timeperiod: int = 10) -> dict:

    @performance_monitor("Stochastic计算")
    def calculate_stoch(self, data: pd.DataFrame, fastk_period: int = 5,
                       slowk_period: int = 3, slowd_period: int = 3) -> dict:

    @performance_monitor("Williams %R计算")
    def calculate_willr(self, data: pd.DataFrame, timeperiod: int = 14) -> dict:
```

**输出格式标准化**:
```python
return {
    "indicator_values": [...],  # 指标值数组
    "latest": {                 # 最新值
        "value": float,
        "timestamp": datetime
    },
    "signals": {               # 交易信号
        "bullish": bool,
        "bearish": bool,
        "strength": str
    }
}
```

## 📈 图表生成工具 (`chart_generator.py`)

### 主要功能
- K线图生成
- 趋势图生成
- 技术指标图表
- 自定义样式图表

**核心方法**:
```python
def generate_kline_chart(data: pd.DataFrame, title: str = "K线图") -> str:
    """生成K线图表，返回base64编码的图片"""

def generate_trend_chart(data: pd.DataFrame, trend_lines: list = None) -> str:
    """生成趋势分析图表"""

def generate_indicator_chart(data: pd.DataFrame, indicators: dict) -> str:
    """生成技术指标图表"""
```

**图表特性**:
- 支持多种图表类型
- 自定义颜色和样式
- 高分辨率输出
- Base64编码便于Web传输

## ⚡ 性能监控工具 (`performance.py`)

### 核心功能

#### 1. 性能监控装饰器
```python
@performance_monitor("阶段名称")
def some_function():
    """被监控的函数"""
    pass
```

#### 2. 上下文管理器
```python
with monitor_context("操作名称"):
    # 需要监控的代码块
    pass
```

#### 3. 手动监控
```python
def manual_monitoring_example():
    start_performance_monitoring()
    record_manual_stage("操作名称", duration=0.0)
    # ... 业务逻辑 ...
    end_performance_monitoring()
```

### 监控指标
- **执行时间**: 函数/操作耗时统计
- **内存使用**: 内存占用监控
- **CPU使用**: CPU使用率监控
- **API调用**: API请求统计
- **缓存命中率**: 缓存效率统计

### 输出格式
```python
{
    "stage_name": "操作名称",
    "execution_time": 1.234,
    "memory_usage": 125.6,
    "cpu_usage": 15.2,
    "timestamp": "2025-10-28T11:36:21",
    "additional_metrics": {...}
}
```

## 🎨 静态工具 (`static_util.py`)

### 主要功能
- 图像生成和处理
- 静态资源管理
- 数据格式转换
- 文件操作工具

**核心方法**:
```python
def generate_kline_image(data: pd.DataFrame, **kwargs) -> str:
    """生成K线图像，返回base64编码"""

def generate_trend_image(data: pd.DataFrame, **kwargs) -> str:
    """生成趋势图像"""

def save_image_to_file(image_data: str, filename: str) -> bool:
    """保存图像到文件"""

def compress_image(image_path: str, quality: int = 85) -> str:
    """压缩图像文件"""
```

## 🔗 图形工具 (`graph_util.py`)

### LangChain工具集成
为LangChain智能体提供标准化的工具接口：

```python
class TechnicalTools:
    def compute_macd(self, kline_data: dict, **params) -> dict:
        """LangChain工具: MACD计算"""
        pass

    def compute_rsi(self, kline_data: dict, **params) -> dict:
        """LangChain工具: RSI计算"""
        pass

    def generate_kline_image(self, kline_data: dict, **params) -> dict:
        """LangChain工具: K线图生成"""
        pass
```

**工具特性**:
- 标准化的输入输出格式
- 完整的参数验证
- 详细的错误信息
- 性能监控集成

## 🎨 样式配置

### 颜色样式 (`color_style.py`)
```python
# 主题色彩配置
COLORS = {
    "bullish": "#00C853",      # 看涨颜色
    "bearish": "#D32F2F",      # 看跌颜色
    "neutral": "#757575",      # 中性颜色
    "background": "#FFFFFF",   # 背景色
    "grid": "#E0E0E0",         # 网格线颜色
    "text": "#212121"          # 文本颜色
}

# 图表样式配置
CHART_STYLE = {
    "figure_size": (12, 8),
    "dpi": 100,
    "style": "seaborn-v0_8",
    "font_family": "Arial",
    "font_size": 10
}
```

### 样式配置 (`style_config.py`)
```python
class StyleConfig:
    """样式配置管理类"""

    def __init__(self):
        self.colors = COLORS
        self.chart_style = CHART_STYLE
        self.indicator_styles = {
            "macd": {"color": "blue", "linewidth": 2},
            "rsi": {"color": "purple", "linewidth": 1.5},
            # ... 更多指标样式
        }

    def get_indicator_style(self, indicator_name: str) -> dict:
        """获取指标样式配置"""
        return self.indicator_styles.get(indicator_name, {})
```

## 🔧 工具使用示例

### 技术指标计算
```python
from utils.technical_indicators import TechnicalTools

tools = TechnicalTools()
data = pd.read_csv("ohlcv_data.csv", index_col="Date", parse_dates=True)

# 计算MACD
macd_result = tools.calculate_macd(data, fastperiod=12, slowperiod=26, signalperiod=9)
print(f"MACD最新值: {macd_result['latest']['macd']}")

# 计算RSI
rsi_result = tools.calculate_rsi(data, timeperiod=14)
print(f"RSI最新值: {rsi_result['latest']['rsi']}")
```

### 图表生成
```python
from utils.chart_generator import generate_kline_chart

# 生成K线图
chart_base64 = generate_kline_chart(data, title="BTC/USDT K线图")
# chart_base64可直接用于HTML img标签的src属性
```

### 性能监控
```python
from utils.performance import performance_monitor, monitor_context

@performance_monitor("数据分析")
def analyze_data(data):
    with monitor_context("技术指标计算"):
        # 计算各种技术指标
        pass

    with monitor_context("图表生成"):
        # 生成分析图表
        pass
    return results
```

## 📊 性能特性

### 计算优化
- 使用NumPy向量化计算
- TA-Lib库的高效实现
- 数据缓存机制
- 并行计算支持

### 内存管理
- 及时释放大型数据结构
- 使用生成器处理大数据集
- 内存使用监控和预警

### 缓存策略
- 技术指标计算结果缓存
- 图表生成结果缓存
- 配置数据缓存
- API响应缓存

## 🔗 依赖关系

### 内部依赖
- 被 `core/` 模块广泛使用
- 为 `agents/` 提供工具接口
- 支持 `web/` 的图表展示

### 外部依赖
- `pandas`: 数据处理
- `numpy`: 数值计算
- `talib`: 技术分析库
- `matplotlib`: 图表生成
- `mplfinance`: 金融图表

## 🚨 错误处理

### 计算错误处理
```python
try:
    result = tools.calculate_macd(data)
except ValueError as e:
    logger.error(f"MACD计算失败: {e}")
    # 返回默认值或重试
except Exception as e:
    logger.error(f"未知错误: {e}")
    raise
```

### 数据验证
- 输入数据格式验证
- 必要列存在性检查
- 数据范围和类型验证
- 缺失值处理

## 📝 开发指南

### 新增技术指标
1. 在 `TechnicalTools` 类中添加计算方法
2. 使用 `@performance_monitor` 装饰器
3. 实现标准化输出格式
4. 添加相应的LangChain工具接口
5. 更新配置和样式

### 新增图表类型
1. 在 `chart_generator.py` 中添加生成函数
2. 定义样式配置
3. 实现Base64编码输出
4. 添加参数验证
5. 测试不同数据场景

### 新增性能监控
1. 在 `performance.py` 中定义监控函数
2. 集成到相关业务代码
3. 配置输出格式和存储
4. 设置监控阈值
5. 添加告警机制

## 🆕 智能文件管理系统 (`file_manager.py`)

### 核心类: `TempFileManager`

**主要功能**:
- 零冲突的临时文件生成
- 自动过期清理机制
- 线程安全的并发支持
- 磁盘空间监控管理

**技术特性**:
- 基于时间戳+UUID+线程ID的三重唯一保证
- 24小时自动过期清理
- 后台清理线程
- 会话级别文件管理

**核心方法**:
```python
class TempFileManager:
    def generate_unique_filename(self, prefix: str = "", suffix: str = ".png") -> tuple:
        """生成唯一文件名"""

    def create_session_dir(self, session_id: Optional[str] = None) -> Path:
        """创建会话目录"""

    def cleanup_old_files(self, force: bool = False) -> int:
        """清理过期文件"""

    def get_directory_size(self) -> int:
        """获取目录大小"""
```

**文件命名策略**:
```
{prefix}_{timestamp}_{thread_id}_{uuid_8chars}{suffix}
```

**示例**:
- `record_1730205967123_8336_2dfb1304.csv`
- `kline_chart_1730205967145_8336_aac17865.png`

**API集成**:
- `GET /api/temp-files/stats` - 获取文件统计
- `POST /api/temp-files/cleanup` - 手动清理文件

## 🆕 临时文件管理器 (`temp_file_manager.py`)

### 核心功能

**全局文件管理器实例:**
```python
def get_file_manager() -> TempFileManager:
    """获取全局文件管理器实例（单例模式）"""

def cleanup_all_temp_files():
    """清理所有临时文件"""

def get_temp_file_stats() -> dict:
    """获取临时文件统计信息"""
```

**启动时清理:**
```python
def cleanup_on_startup():
    """应用启动时清理过期文件"""
```

**统计信息API:**
```python
{
    "file_count": 42,
    "directory_size_mb": 15.6,
    "temp_directory": "temp_charts"
}
```

### 技术优势

1. **单例模式**: 全局统一管理，避免资源冲突
2. **自动化**: 启动时自动清理，保持系统清洁
3. **监控友好**: 提供实时统计API
4. **线程安全**: 支持高并发场景

## 📊 相关文件清单

| 文件名 | 主要功能 | 估计行数 | 状态 |
|--------|----------|----------|------|
| `technical_indicators.py` | 技术指标计算 | ~200行 | ✅ 完整 |
| `chart_generator.py` | 图表生成工具 | 待扫描 | 🔄 待完善 |
| `performance.py` | 性能监控工具 | ~100行 | ✅ 完整 |
| `static_util.py` | 静态工具函数 | ~180行 | ✅ 已优化 |
| `graph_util.py` | 图形工具 | ~400行 | ✅ 已优化 |
| `color_style.py` | 颜色样式配置 | 待扫描 | 🔄 待完善 |
| `style_config.py` | 样式配置管理 | 待扫描 | 🔄 待完善 |
| `file_manager.py` | 🆕 智能文件管理 | ~300行 | ✅ 新增 |
| `temp_file_manager.py` | 🆕 临时文件管理器 | ~100行 | ✅ 新增 |

## 🔮 未来扩展

## 🔧 最新优化亮点

### 🎯 文件冲突问题解决 (2025-10-29)
- **问题根因**: 硬编码文件名导致数据污染
- **解决方案**: 智能UUID文件命名 + 自动清理机制
- **影响范围**: `static_util.py`, `graph_util.py`, `agents/*`
- **效果**: 零冲突概率，真正的独立分析

### ⚡ 性能优化
- **并发支持**: 多用户同时分析无冲突
- **内存优化**: 及时释放临时数据
- **文件管理**: 24小时自动过期清理
- **API增强**: 新增文件统计和清理端点

### 📊 使用效果
- **准确性**: 每个币种获得真实的K线分析结果
- **稳定性**: 线程安全，支持高频分析
- **维护性**: 自动清理，无需手动管理
- **监控性**: 实时文件统计和磁盘使用监控

## 🔮 未来扩展

### 计划新增工具
- **风险管理工具**: VaR计算、最大回撤分析
- **投资组合工具**: 相关性分析、有效前沿计算
- **回测工具**: 策略回测、性能评估
- **数据预处理工具**: 数据清洗、异常值检测

### 技术改进方向
- GPU加速计算支持
- 更多技术指标库集成
- 实时数据流处理
- 分布式计算支持
- **智能缓存**: 基于分析结果的智能缓存机制
- **批量分析**: 支持多币种批量分析功能

---

**模块维护者:** 哈雷酱 (傲娇大小姐工程师)
**文档生成时间:** 2025-11-12
**模块状态:** ✅ 核心工具完整，智能文件管理系统全面升级

## 🎉 重要更新说明

### 解决的重大问题
- **模式识别固定输出**: 不同币种不再出现相同的"下降三角形"分析
- **文件名冲突**: 彻底解决了硬编码文件名导致的数据污染
- **并发安全**: 支持多用户同时分析不同币种
- **系统稳定性**: 临时文件自动管理，避免磁盘空间耗尽

### 技术成果
- **零冲突保证**: UUID + 时间戳 + 线程ID三重唯一性
- **自动维护**: 24小时过期清理，磁盘空间智能管理
- **性能提升**: 线程安全设计，支持高频并发分析
- **监控完善**: 实时文件统计和清理API

### 🚀 智能文件管理系统亮点
- **三重唯一保证**: 时间戳 + UUID + 线程ID = 零冲突概率
- **自动化清理**: 后台守护线程，每小时自动清理过期文件
- **会话管理**: 支持按会话批量清理，便于调试和测试
- **API集成**: 提供文件统计和手动清理接口

现在每个币种都会获得基于其真实K线数据的准确分析结果，系统运行更加稳定可靠！