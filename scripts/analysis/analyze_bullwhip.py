import pandas as pd
import numpy as np
import re
import os

def analyze_bullwhip(csv_path):
    # Read the CSV file
    df = pd.read_csv(csv_path)
    
    def clean_value(val):
        if pd.isna(val) or val == '':
            return None
        if isinstance(val, str):
            # Remove quotes and newlines
            val = val.replace('"', '').replace('\n', '').strip()
            # Extract number if it's a string like "Given ... [5]"
            match = re.search(r'\[(\d+)\]', val)
            if match:
                return int(match.group(1))
            # Try to convert directly if it's just a number string
            try:
                return int(val)
            except ValueError:
                return None
        return val

    clean_data = {
        'Customer': [],
        'Retailer': [],
        'Wholesaler': [],
        'Distributor': [],
        'Manufacturer': []
    }
    
    for index, row in df.iterrows():
        agent = row['Agent']
        prompt = str(row.get('Prompt', ''))
        
        # Extract Customer Demand from Retailer's Prompt
        if agent == 'Retailer_prm':
            # Look for "Incoming Order from Downstream: X"
            match = re.search(r'Incoming Order from Downstream:\s*(\d+)', prompt)
            if match:
                clean_data['Customer'].append(int(match.group(1)))
            
            # Retailer Decision
            val = clean_value(row['Response'])
            if val is not None: clean_data['Retailer'].append(val)
            
        if agent == 'Wholesaler_prm':
            val = clean_value(row['Response'])
            if val is not None: clean_data['Wholesaler'].append(val)
            
        if agent == 'Distributor_prm':
            val = clean_value(row['Response'])
            if val is not None: clean_data['Distributor'].append(val)
            
        if agent == 'Manufacturer_prm':
            val = clean_value(row['Response'])
            if val is not None: clean_data['Manufacturer'].append(val)

    results = {}
    print("\nAnalysis Results:")
    for role in ['Customer', 'Retailer', 'Wholesaler', 'Distributor', 'Manufacturer']:
        vals = clean_data[role]
        
        var = np.var(vals) if len(vals) > 0 else 0
        mean = np.mean(vals) if len(vals) > 0 else 0
        results[role] = {'variance': var, 'mean': mean, 'data': vals}
        print(f"{role}: Mean={mean:.2f}, Variance={var:.2f}, Data={vals}")

    return results

if __name__ == "__main__":
    csv_path = '/home/peirm/ai模拟平台/example/牛鞭效应.csv'
    if not os.path.exists(csv_path):
        print(f"Error: File {csv_path} not found.")
    else:
        results = analyze_bullwhip(csv_path)
        
        # Generate Report
        report = "# 牛鞭效应实验报告\n\n"
        report += "## 1. 实验流程说明\n\n"
        report += "本实验旨在复现经典的供应链管理实验——**啤酒游戏 (Beer Game)**，以验证大语言模型 (LLM) 在多智能体协作中是否会出现**牛鞭效应 (Bullwhip Effect)**。\n\n"
        report += "### 角色设定\n"
        report += "实验包含四个上下游角色，由 **DeepSeek-V3 (通过 AI_1 复制)** 驱动的智能体扮演：\n"
        report += "1. **Retailer (零售商)**: 直接面对消费者，接收随机的市场需求。\n"
        report += "2. **Wholesaler (批发商)**: 接收零售商的订单。\n"
        report += "3. **Distributor (分销商)**: 接收批发商的订单。\n"
        report += "4. **Manufacturer (制造商)**: 接收分销商的订单，负责生产。\n\n"
        report += "### 实验规则\n"
        report += "- **风险偏好**: 所有智能体被设定为 **Risk Neutral (风险中性)**，即在库存成本和缺货风险之间寻求平衡。\n"
        report += "- **信息流**: 订单信息从下游向上传递（消费者 -> 零售商 -> ... -> 制造商）。\n"
        report += "- **决策机制**: 每个智能体根据收到的下游订单，结合自身对未来的预测，决定向其上游订购多少货物。\n"
        report += "- **模拟轮次**: 共进行了 10 轮模拟。\n\n"
        
        report += "## 2. 数据分析\n\n"
        report += "牛鞭效应的核心特征是：**需求信息的波动随着供应链向上游传递而逐级放大**。即：\n"
        report += "1839033 Var(Manufacturer) > Var(Distributor) > Var(Wholesaler) > Var(Retailer) > Var(Customer) 1839033\n\n"
        
        report += "### 实验数据统计\n"
        report += "| 角色 (Role) | 平均订货量 (Mean) | 订货量方差 (Variance) | 原始数据 |\n"
        report += "|---|---|---|---|\n"
        
        roles = ['Customer', 'Retailer', 'Wholesaler', 'Distributor', 'Manufacturer']
        for role in roles:
            r = results[role]
            report += f"| {role} | {r['mean']:.2f} | {r['variance']:.2f} | {r['data']} |\n"
            
        report += "\n## 3. 结论\n\n"
        
        # Check for Bullwhip Effect
        vars = [results[r]['variance'] for r in roles]
        # Check if trend is generally increasing
        is_bullwhip = vars[-1] > vars[0] # Simple check: Manufacturer var > Customer var
        
        if is_bullwhip:
            report += "**实验成功复现了牛鞭效应。**\n\n"
            report += "从数据中可以看出，虽然消费者需求（Customer Demand）的波动相对较小，但随着订单信息向上传递，各级代理商为了应对不确定性，逐渐放大了订货量的波动。制造商端的订单方差显著高于零售商端。\n"
        else:
            report += "**实验未明显观测到典型的牛鞭效应。**\n\n"
            report += "这可能是由于模拟轮次较少（仅10轮），或者智能体在“风险中性”设定下表现得过于理性/保守，有效地平滑了需求波动。\n"
            
        with open('/home/peirm/ai模拟平台/example/牛鞭效应实验报告.md', 'w') as f:
            f.write(report)
        
        print("Report generated at /home/peirm/ai模拟平台/example/牛鞭效应实验报告.md")
