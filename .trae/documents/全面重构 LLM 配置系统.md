## 重构目标
将混乱的多层配置系统重构为清晰、类型安全、易于使用的配置架构

## 重构步骤

### 1. 创建新的配置模块结构
- `llm_config.py` - LLM 配置核心（枚举、供应商映射、配置类）
- `app_settings.py` - 应用配置（CORS、市场数据API等）
- `llm_factory.py` - LLM 客户端工厂（独立的客户端创建逻辑）
- `config_repository.py` - 配置持久化（.env 文件读写）

### 2. 重构 LLM 配置
- 简化为单一配置类 `LLMSettings`，使用 Pydantic 模型
- 移除 `LLMConfig` 和 `Config` 类的冗余层
- 统一配置访问方式

### 3. 重构 LLM 客户端工厂
- 将 `create_llm_client()` 移到独立模块
- 移除修改全局状态的逻辑
- 支持参数化配置，不依赖临时修改 settings

### 4. 安全改进
- 移除硬编码的 API Key
- 添加环境变量验证
- 使用 `SecretStr` 类型保护敏感信息

### 5. 类型安全
- 使用 Pydantic 模型替代 `Dict[str, Any]`
- 添加类型提示和验证

### 6. 更新所有引用
- 更新 `trading_engine.py`
- 更新 `analyze.py`
- 更新 `system.py`
- 更新 `market_data.py`
- 更新 `main.py`

### 7. 清理和测试
- 删除旧的 `config_examples.py`
- 运行测试验证重构正确性