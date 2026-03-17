import argparse
import json
import os

from prompt_tuning_engine import ContextLoader


def extract_context(history_json_path: str, output_path: str) -> None:
    print(f"正在读取历史报告: {history_json_path}")
    if not os.path.exists(history_json_path):
        print(f"错误: 找不到文件 {history_json_path}")
        return

    context = ContextLoader().load(history_json_path)
    extracted = {
        "stock_name": context.stock_name,
        "time_frame": context.time_frame,
        "price_summary": context.price_summary,
        "price_info_str": context.price_info_str,
        "latest_price_str": context.latest_price_str,
        "indicator_report": context.indicator_report,
        "pattern_report": context.pattern_report,
        "trend_report": context.trend_report,
    }

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(extracted, file, ensure_ascii=False, indent=2)

    print(f"成功提取上下文，已保存到: {output_path}")
    print(f"包含字段: {list(extracted.keys())}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="提取历史 JSON 中的决策上下文")
    parser.add_argument("--input", "-i", required=True, help="输入历史 JSON 文件路径")
    parser.add_argument(
        "--output",
        "-o",
        default="extracted_context.json",
        help="输出 JSON 文件路径",
    )
    args = parser.parse_args()
    extract_context(args.input, args.output)
