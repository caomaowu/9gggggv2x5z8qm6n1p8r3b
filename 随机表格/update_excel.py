import pandas as pd
import random
from datetime import datetime, timedelta
import os

def read_crypto_pairs(file_path):
    """从MD文件中读取加密货币交易对列表"""
    crypto_pairs = []
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        for line in lines:
            line = line.strip()
            # 跳过标题行和空行
            if line and not line.startswith('#') and not line.startswith('>') and not line.startswith('##'):
                # 去掉-USDT-SWAP后缀
                if line.endswith('-USDT-SWAP'):
                    line = line[:-10]  # 去掉最后10个字符("-USDT-SWAP")
                elif line.endswith('-USD-SWAP'):
                    line = line[:-9]   # 去掉最后9个字符("-USD-SWAP")
                elif line.endswith('-USD_UM-SWAP'):
                    line = line[:-13]  # 去掉最后13个字符("-USD_UM-SWAP")
                elif line.endswith('-USDC-SWAP'):
                    line = line[:-10]  # 去掉最后10个字符("-USDC-SWAP")
                crypto_pairs.append(line)
    return crypto_pairs

def generate_random_dates(start_date, end_date, count):
    """生成指定范围内的随机日期，包含随机的小时和分钟（24小时制）"""
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    dates = []
    for _ in range(count):
        random_days = random.randint(0, (end - start).days)
        random_hours = random.randint(0, 23)  # 0-23小时
        random_minutes = random.randint(0, 59)  # 0-59分钟
        
        random_date = start + timedelta(days=random_days, hours=random_hours, minutes=random_minutes)
        dates.append(random_date.strftime('%Y-%m-%d %H:%M'))
    
    return dates

def update_csv_file(csv_path, crypto_pairs, dates, start_from_b3=False):
    """更新CSV文件中的B2-B11和C2-C11单元格，或者B3-B12和C3-C12单元格"""
    # 读取CSV文件
    df = pd.read_csv(csv_path)
    
    # 确保我们有足够的数据
    if len(crypto_pairs) < 5:
        raise ValueError("需要至少5个加密货币交易对")
    
    if len(dates) < 10:
        raise ValueError("需要至少10个日期")
    
    # 随机选择5个加密货币
    selected_cryptos = random.sample(crypto_pairs, 5)
    
    # 重复选择的加密货币以填充B列（每个加密货币使用两次）
    cryptos_for_b_column = []
    for crypto in selected_cryptos:
        cryptos_for_b_column.extend([crypto, crypto])
    
    # 只取前10个
    cryptos_for_b_column = cryptos_for_b_column[:10]
    
    # 确定起始行索引
    start_row = 2 if start_from_b3 else 1  # 如果从B3开始，则起始行索引为2；否则为1
    
    # 更新B列（加密货币）
    for i, crypto in enumerate(cryptos_for_b_column):
        row_num = start_row + i
        cell_position = f"B{row_num + 1}"  # Excel行号从1开始
        print(f"填充 {cell_position} 单元格: {crypto}")
        df.iloc[row_num, 1] = crypto  # B列是第1列（索引从0开始）
    
    # 更新C列（日期）
    for i, date in enumerate(dates[:10]):
        row_num = start_row + i
        cell_position = f"C{row_num + 1}"  # Excel行号从1开始
        print(f"填充 {cell_position} 单元格: {date}")
        df.iloc[row_num, 2] = date  # C列是第2列（索引从0开始）
    
    # 保存修改后的CSV文件
    df.to_csv(csv_path, index=False)
    
    return selected_cryptos, dates[:10]

def main():
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 文件路径 - 使用绝对路径，确保文件能被找到
    csv_path = os.path.join(script_dir, '测试表.csv')
    excel_path = os.path.join(script_dir, '测试表.xlsx')
    crypto_list_path = os.path.join(script_dir, 'OKX_交易对列表_简化.md')
    
    # 如果Excel文件存在但CSV文件不存在，先转换Excel为CSV
    if os.path.exists(excel_path) and not os.path.exists(csv_path):
        print("将Excel文件转换为CSV格式...")
        df_excel = pd.read_excel(excel_path)
        df_excel.to_csv(csv_path, index=False)
        print("转换完成!")
    
    # 读取加密货币交易对列表
    crypto_pairs = read_crypto_pairs(crypto_list_path)
    print(f"读取到 {len(crypto_pairs)} 个加密货币交易对")
    
    # 生成2024-2025范围内的随机日期
    dates = generate_random_dates('2024-01-01', '2025-12-31', 10)
    print(f"生成了 {len(dates)} 个随机日期")
    
    # 更新CSV文件 - 从B2和C2开始填充
    selected_cryptos, used_dates = update_csv_file(csv_path, crypto_pairs, dates, start_from_b3=False)
    
    print("CSV文件已更新!")
    print("随机选择的加密货币:", selected_cryptos)
    print("使用的日期:", used_dates)

if __name__ == "__main__":
    main()