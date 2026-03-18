import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv


backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

from app.agents.decision.decision_agent_lite import LITE_PROMPT_TEMPLATE
from app.agents.decision.decision_agent_original import ORIGINAL_PROMPT_TEMPLATE
from app.core.config import reload_config
from tools.prompt_tuning.prompt_tuning_engine import ContextLoader, DecisionRunner


def test_decision_prompt(context_path: str, prompt_version: str = "original") -> None:
    load_dotenv(backend_dir / ".env")
    reload_config()

    context = ContextLoader().load(context_path)
    prompt_template = (
        ORIGINAL_PROMPT_TEMPLATE
        if prompt_version == "original"
        else LITE_PROMPT_TEMPLATE
    )

    print(f"--- 使用 {prompt_version} 版本 Prompt 进行测试 ---")
    result = DecisionRunner().run(context, prompt_template, prompt_version)
    if result.formatted_prompt:
        print("\n[Prompt 预览（前 500 字符）]")
        print(result.formatted_prompt[:500] + "...\n")

    print("====== 决策输出 ======")
    print(result.raw_response or "(无原始输出)")
    print("=====================\n")
    print(f"状态: {result.status}")
    print(f"决策: {result.decision or '未解析'}")
    print(f"解析模式: {result.decision_parse_mode}")
    print(f"耗时: {result.elapsed_ms} ms")
    if result.error_message:
        print(f"错误: {result.error_message}")
    print(f"K1: close={result.k1_result.close} pct={result.k1_result.pct} outcome={result.k1_result.outcome}")
    print(f"K2: close={result.k2_result.close} pct={result.k2_result.pct} outcome={result.k2_result.outcome}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="测试 Decision Agent Prompt")
    parser.add_argument("--context", "-c", required=True, help="历史 JSON 文件路径")
    parser.add_argument(
        "--version",
        "-v",
        choices=["original", "lite"],
        default="original",
        help="Prompt 版本",
    )
    args = parser.parse_args()
    test_decision_prompt(args.context, args.version)
