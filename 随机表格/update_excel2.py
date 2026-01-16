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

def read_crypto_from_csv_source(file_path):
    """从CSV源文件中读取加密货币列表 (格式: 序号,币种)"""
    crypto_pairs = []
    # 尝试使用不同的编码读取，优先尝试 GBK (常见的中文编码)
    encodings = ['gbk', 'utf-8', 'gb18030']
    
    lines = []
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as file:
                lines = file.readlines()
            break
        except UnicodeDecodeError:
            continue
    
    if not lines:
        print(f"无法读取文件: {file_path}")
        return []

    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 跳过可能存在的表头（简单判断：如果不包含数字且包含中文或乱码）
        # 这里直接尝试分割
        parts = line.split(',')
        if len(parts) >= 2:
            symbol = parts[1].strip()
            
            # 忽略看起来像表头的行（比如第二列也是中文）
            # 简单判断：如果symbol包含大写字母且包含USDT，或者看起来像币种
            if 'USDT' in symbol:
                if symbol.endswith('USDT'):
                    symbol = symbol[:-4] # 去掉 USDT
                crypto_pairs.append(symbol)
            # 如果不包含USDT但看起来是有效数据的处理（这里主要针对提供的 1-25币种.csv）
    
    return crypto_pairs

def generate_random_dates(start_date, end_date, count):
    """生成指定范围内的随机日期，包含随机的小时和分钟（24小时制）"""
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    dates = []
    allowed_hours = [3, 7, 11, 15, 19, 23]
    for _ in range(count):
        random_days = random.randint(0, (end - start).days)
        random_hours = random.choice(allowed_hours)
        random_minutes = random.randint(45, 59)
        random_date = start + timedelta(days=random_days, hours=random_hours, minutes=random_minutes)
        dates.append(random_date.strftime('%Y-%m-%d %H:%M'))
    
    return dates

def generate_random_times(count):
    """生成随机时间，小时固定为[4, 8, 12, 16, 20, 0]，分钟为0-15"""
    times = []
    allowed_hours = [4, 8, 12, 16, 20, 0]  # 0代表午夜0点
    for _ in range(count):
        random_hour = random.choice(allowed_hours)
        random_minute = random.randint(0, 15)
        times.append(f"{random_hour:02d}:{random_minute:02d}")
    
    return times

def update_csv_file(csv_path, crypto_pairs, dates, times=None, start_from_b3=False):
    """更新CSV文件中的B2-B11和C2-C11单元格，或者B3-B12和C3-C12单元格，以及D列的时间"""
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
    
    # 更新D列（时间）- 如果提供了时间数据
    if times is not None:
        for i, time in enumerate(times[:10]):
            row_num = start_row + i
            cell_position = f"D{row_num + 1}"  # Excel行号从1开始
            print(f"填充 {cell_position} 单元格: {time}")
            df.iloc[row_num, 3] = time  # D列是第3列（索引从0开始）
    
    # 保存修改后的CSV文件
    df.to_csv(csv_path, index=False)
    
    return selected_cryptos, dates[:10], times[:10] if times is not None else None

def main():
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 文件路径 - 使用绝对路径，确保文件能被找到
    csv_path = os.path.join(script_dir, '测试表.csv')
    excel_path = os.path.join(script_dir, '测试表.xlsx')
    crypto_list_path_md = os.path.join(script_dir, 'OKX_交易对列表_简化.md')
    crypto_list_path_csv = os.path.join(script_dir, '1-25币种.csv')
    
    # 如果Excel文件存在但CSV文件不存在，先转换Excel为CSV
    if os.path.exists(excel_path) and not os.path.exists(csv_path):
        print("将Excel文件转换为CSV格式...")
        df_excel = pd.read_excel(excel_path)
        df_excel.to_csv(csv_path, index=False)
        print("转换完成!")
    
    # 用户选择数据源
    print("\n请选择加密货币数据来源:")
    print("1. OKX_交易对列表_简化.md (默认)")
    print("2. 1-25币种.csv")
    choice = input("请输入选项 (1 或 2): ").strip()
    
    crypto_pairs = []
    
    if choice == '2':
        print(f"正在读取: {crypto_list_path_csv}")
        if os.path.exists(crypto_list_path_csv):
            crypto_pairs = read_crypto_from_csv_source(crypto_list_path_csv)
            print(f"从CSV读取到 {len(crypto_pairs)} 个加密货币")
        else:
            print(f"错误: 找不到文件 {crypto_list_path_csv}")
            return
    else:
        print(f"正在读取: {crypto_list_path_md}")
        if os.path.exists(crypto_list_path_md):
            crypto_pairs = read_crypto_pairs(crypto_list_path_md)
            print(f"从MD读取到 {len(crypto_pairs)} 个加密货币")
        else:
            print(f"错误: 找不到文件 {crypto_list_path_md}")
            return
            
    if not crypto_pairs:
        print("警告: 未找到有效的加密货币数据！")
        return
    
    # 生成2024-2026范围内的随机日期 (截止2026.1.10)
    dates = generate_random_dates('2024-01-01', '2026-01-10', 10)
    print(f"生成了 {len(dates)} 个随机日期")
    
    # 生成随机时间，小时固定为[4, 8, 12, 16, 20, 0]，分钟为0-15
    times = generate_random_times(10)
    print(f"生成了 {len(times)} 个随机时间")
    
    # 更新CSV文件 - 从B2和C2开始填充，并填充D列的时间
    selected_cryptos, used_dates, used_times = update_csv_file(csv_path, crypto_pairs, dates, times, start_from_b3=False)
    
    print("CSV文件已更新!")
    print("随机选择的加密货币:", selected_cryptos)
    print("使用的日期:", used_dates)
    print("使用的时间:", used_times)

if __name__ == "__main__":
    main()
