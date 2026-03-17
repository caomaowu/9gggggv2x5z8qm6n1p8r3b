# Auto-Optimizer: 决策智能体 Prompt 自动化进化系统设计方案
工作目录：backend\tools\prompt_tuning
保持现有的功能的基础上，开发 Auto-Optimizer 功能。
## 1. 核心目标
构建一个全自动化的闭环系统，利用大模型（Optimizer）来优化另一个大模型（Evaluator/Agent）的 System Prompt。
通过在固定的历史数据集上反复回测，不断迭代 Prompt 内容，以最大化 **胜率 (Win Rate)** 和优化 **多空比 (Long/Short Ratio)**。

## 2. 架构设计：双模型独立配置

为了平衡成本、速度与智能深度，系统采用 **双模型 (Dual-Model)** 架构，两者配置完全独立。

### 2.1 角色定义

| 角色 | 职责 | 推荐配置 | 特性要求 |
| :--- | :--- | :--- | :--- |
| **Evaluator (回测执行者)** | 批量运行 100+ 个历史 JSON，做出 Long/Short 决策 | `gpt-4o-mini` 或 `haiku` | **速度快**，**低成本**，**确定性高** (Temp=0) |
| **Optimizer (优化专家)** | 分析历史回测数据，生成新的 Prompt | `gpt-4o` 或 `claude-3-5-sonnet` | **推理能力强**，**创造性适中** (Temp=0.7) |

### 2.2 配置管理 (`.env` 扩展)

在现有 `.env` 基础上，新增 `OPTIMIZER_` 专用配置区。（这个必须先了解项目的具体代码）

```ini
# --- Existing Config (Used by Evaluator) ---
AGENT_PROVIDER=openai
AGENT_MODEL=gpt-4o-mini

# --- New Config (Used by Optimizer) ---
OPTIMIZER_PROVIDER=openai
OPTIMIZER_MODEL=gpt-4o
OPTIMIZER_TEMPERATURE=0.7
OPTIMIZER_API_KEY=sk-xxx...  # 如果与默认 Key 不同可单独设置，否则复用
```

## 3. 系统工作流 (The Evolutionary Loop)

系统运行在一个无限循环中（或直到达到指定轮次），每一轮称为一个 **Generation**。

### Step 1: Initialization (初始化)
1. 加载 `backtest_data_dir` 下的所有 `.json` 文件（作为固定的训练集）。
2. 加载初始 Prompt（通常为 `ORIGINAL_PROMPT_TEMPLATE`）。
3. 初始化 `optimization_history.json` 用于记录进化史。

### Step 2: Evaluation (回测评估)
1. **并发执行**：使用当前的 Prompt，调用 **Evaluator LLM** 对所有 JSON 进行决策。
3. **指标计算**：
   - **Win Rate**: (Winning Trades / Total Trades) * 100%
   - **L/S Ratio**: Long Count / Short Count
   - **Parse Rate**: 成功解析 JSON 的比例

### Step 3: Reflection (反思与生成)
1. **构建上下文**：将**完整**的历史记录（包含过去每一代的 Prompt 内容、胜率、多空比）组装成 Meta-Prompt。
2. **调用 Optimizer**：
   - 输入：历史记录 + 任务目标（最大化胜率）。
   - 输出：一段分析（Reasoning）+ 一个全新的 Prompt（XML 包裹）。
3. **策略**：Optimizer 被指示要根据历史数据，分析当前 Prompt 的表现，然后生成一个新的 Prompt，该 Prompt 要提高胜率基础。

### Step 4: Update & Persistence (更新与存档)
1. 将本轮结果存入 `history`。
2. 将新生成的 Prompt 保存为 `current_prompt.txt`。
3. 如果本轮胜率创历史新高，额外保存为 `best_prompt_gen_{N}.txt`。
4. 进入下一轮 Step 2。

## 4. 关键数据结构

### OptimizationRecord
```python
@dataclass
class OptimizationRecord:
    generation: int
    timestamp: str
    prompt_content: str
    prompt_hash: str
    
    # Metrics
    total_trades: int
    win_rate: float
    long_count: int
    short_count: int
    long_short_ratio: float
    
    # Optimizer's thoughts
    reasoning: str
```

## 5. 实现步骤规划

### Phase 1: 配置与基础设置
- [ ] 修改 `backend/app/core/config.py`，增加 `OPTIMIZER_*` 配置项。
- [ ] 实现 `create_optimizer_llm()` 工厂函数。

### Phase 2: 核心优化器逻辑 (`auto_optimizer.py`)
- [ ] 实现 `OptimizationHistory` 管理类。
- [ ] 实现 `run_evolution_loop()` 主循环。
- [ ] 集成 `BatchBacktestRunner` 进行静默回测（不弹 GUI）。

### Phase 3: Meta-Prompt 工程
- [ ] 设计精妙的 System Prompt，引导 Optimizer 有效利用历史数据。
- [ ] 实现历史记录的格式化输出（Markdown 格式）。

## 6. 预期产出
- 一个可长期运行的脚本 `backend/tools/prompt_tuning/auto_optimizer.py`。
- 运行后会在 `backend/tools/prompt_tuning/optimization_logs/` 目录下生成一系列进化的 Prompt 和详细的 CSV 报表。
