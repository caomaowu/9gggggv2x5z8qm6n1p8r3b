import json
import os
import argparse

def extract_context(history_json_path, output_path):
    """
    从历史分析报告中提取决策智能体需要的上下文信息，并保存为精简的JSON。
    """
    print(f"正在读取历史报告: {history_json_path}")
    
    if not os.path.exists(history_json_path):
        print(f"错误: 找不到文件 {history_json_path}")
        return
        
    with open(history_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # 提取决策智能体所需的字段
    extracted = {
        "stock_name": data.get("stock_name", "Unknown"),
        "time_frame": data.get("time_frame", "Unknown"),
        "price_summary": data.get("price_summary", "No price summary available."),
        "price_info_str": data.get("price_info_str", "No price info available."),
        "latest_price_str": str(data.get("latest_price", "Unknown")),
        "indicator_report": "",
        "pattern_report": "",
        "trend_report": ""
    }
    
    # 尝试从外层直接获取（兼容旧格式）
    if "indicator_report" in data:
        extracted["indicator_report"] = data["indicator_report"]
    if "pattern_report" in data:
        extracted["pattern_report"] = data["pattern_report"]
    if "trend_report" in data:
        extracted["trend_report"] = data["trend_report"]
        
    # 如果外层没有，尝试从 analysis_results 中获取（兼容新格式）
    if "analysis_results" in data:
        results = data["analysis_results"]
        if "Indicator" in results and "indicator_report" in results["Indicator"]:
            extracted["indicator_report"] = results["Indicator"]["indicator_report"]
        if "Pattern" in results and "pattern_report" in results["Pattern"]:
            extracted["pattern_report"] = results["Pattern"]["pattern_report"]
        if "Trend" in results and "trend_report" in results["Trend"]:
            extracted["trend_report"] = results["Trend"]["trend_report"]

    # 保存提取的内容
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(extracted, f, ensure_ascii=False, indent=4)
        
    print(f"✅ 成功提取上下文数据！已保存至: {output_path}")
    print(f"包含的字段: {list(extracted.keys())}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="提取历史JSON中的决策分析上下文")
    parser.add_argument("--input", "-i", required=True, help="输入的历史JSON文件路径")
    parser.add_argument("--output", "-o", default="extracted_context.json", help="输出的精简JSON文件路径")
    
    args = parser.parse_args()
    extract_context(args.input, args.output)
