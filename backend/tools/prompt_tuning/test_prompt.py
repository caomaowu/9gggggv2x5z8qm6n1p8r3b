import json
import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# 添加后端目录到 sys.path，以便导入 app 模块
backend_dir = Path(__file__).parent.parent.parent
sys.path.append(str(backend_dir))

from app.core.config import create_llm_client
from app.agents.decision.decision_agent_original import ORIGINAL_PROMPT_TEMPLATE
from app.agents.decision.decision_agent_lite import LITE_PROMPT_TEMPLATE

def test_decision_prompt(context_path, prompt_version="original"):
    """
    使用提取的上下文数据测试指定的 Prompt
    """
    from dotenv import load_dotenv
    load_dotenv(backend_dir / ".env")
    
    if not os.path.exists(context_path):
        print(f"错误: 找不到上下文文件 {context_path}")
        return
        
    with open(context_path, 'r', encoding='utf-8') as f:
        context = json.load(f)
        
    # 选择 Prompt
    prompt_template = ORIGINAL_PROMPT_TEMPLATE if prompt_version == "original" else LITE_PROMPT_TEMPLATE
    
    print(f"--- 正在使用 {prompt_version} 版本的 Prompt 进行测试 ---")
    
    # 格式化 Prompt
    try:
        prompt = prompt_template.format(
            stock_name=context.get("stock_name", "Unknown"),
            time_frame=context.get("time_frame", "Unknown"),
            price_summary=context.get("price_summary", ""),
            price_info_str=context.get("price_info_str", ""),
            latest_price_str=context.get("latest_price_str", ""),
            indicator_report=context.get("indicator_report", ""),
            pattern_report=context.get("pattern_report", ""),
            trend_report=context.get("trend_report", "")
        )
    except Exception as e:
        print(f"Prompt 格式化失败: {e}")
        return
        
    print("\n[生成的 Prompt 预览 (前500字符)]")
    print(prompt[:500] + "...\n")
    
    # 获取 LLM 实例 (对应配置中的 AGENT_MODEL)
    print("正在初始化 LLM...")
    llm = create_llm_client(role="agent")
    
    # 调用 LLM
    print("正在请求 LLM (可能需要几秒钟)...\n")
    try:
        response = llm.invoke(prompt)
        print("====== 🤖 决策智能体输出 ======")
        print(response.content)
        print("===============================\n")
    except Exception as e:
        print(f"❌ 调用 LLM 失败: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="测试决策智能体Prompt")
    parser.add_argument("--context", "-c", required=True, help="提取的上下文JSON文件路径")
    parser.add_argument("--version", "-v", choices=["original", "lite"], default="original", help="使用的Prompt版本")
    
    args = parser.parse_args()
    test_decision_prompt(args.context, args.version)
