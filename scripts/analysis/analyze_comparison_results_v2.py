
import json
import matplotlib.pyplot as plt
import numpy as np
import os
from pathlib import Path

def analyze_and_plot():
    repo_root = Path(__file__).resolve().parents[2]
    artifacts_json = repo_root / "artifacts" / "results" / "json" / "comparison_results_v2.json"
    legacy = Path("comparison_results_v2.json")
    input_path = artifacts_json if artifacts_json.exists() else legacy

    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Create output directory for plots
    output_dir = "论文/experiment_results_v2"
    os.makedirs(output_dir, exist_ok=True)

    # ==========================================
    # 1. Newsvendor Analysis
    # ==========================================
    nv_data = data["newsvendor"]["data"]
    conditions = [d["condition"] for d in nv_data]
    optimals = [d["optimal"] for d in nv_data]
    avg_decisions = [np.mean(d["decisions"]) for d in nv_data]
    std_decisions = [np.std(d["decisions"]) for d in nv_data]

    plt.figure(figsize=(8, 6))
    x = np.arange(len(conditions))
    width = 0.35

    plt.bar(x - width/2, optimals, width, label='Optimal (Theory)', color='gray', alpha=0.7)
    plt.bar(x + width/2, avg_decisions, width, label='LLM Decision (Avg)', color='skyblue', yerr=std_decisions, capsize=5)

    plt.ylabel('Order Quantity')
    plt.title('Newsvendor Problem: LLM vs Optimal')
    plt.xticks(x, conditions)
    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    plt.savefig(f"{output_dir}/newsvendor_comparison.png")
    plt.close()

    # ==========================================
    # 2. Beer Game Analysis (Bullwhip Effect)
    # ==========================================
    bg_data = data["beer_game"]
    # bg_data keys: Retailer, Wholesaler, Distributor, Factory, prompts
    
    agents = ["Retailer", "Wholesaler", "Distributor", "Factory"]
    orders = {agent: bg_data[agent]["orders"] for agent in agents}
    
    rounds = len(orders["Retailer"])
    weeks = np.arange(1, rounds + 1)
    
    # Reconstruct Demand (Step at week 5)
    demand = [4 if t < 5 else 8 for t in weeks]

    plt.figure(figsize=(12, 8))
    plt.plot(weeks, demand, 'k--', label='Customer Demand', linewidth=3)
    
    colors = ['b', 'g', 'orange', 'r']
    markers = ['o', 's', '^', 'x']
    
    variances = {}
    
    for i, agent in enumerate(agents):
        agent_orders = orders[agent]
        plt.plot(weeks, agent_orders, color=colors[i], marker=markers[i], label=f'{agent} Orders', linewidth=1.5, alpha=0.8)
        variances[agent] = np.var(agent_orders)

    plt.xlabel('Week')
    plt.ylabel('Order Quantity')
    plt.title('Beer Game: Bullwhip Effect (Amplification Upstream)')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    
    plt.savefig(f"{output_dir}/beer_game_bullwhip.png")
    plt.close()

    # ==========================================
    # 3. Single Echelon Analysis
    # ==========================================
    se_data = data["single_echelon"]
    se_orders = se_data["orders"]
    optimal_S = se_data["optimal_S"]
    
    rounds_se = len(se_orders)
    periods = np.arange(1, rounds_se + 1)
    
    plt.figure(figsize=(10, 6))
    plt.plot(periods, se_orders, 'g-s', label='LLM Orders')
    plt.axhline(y=5, color='r', linestyle='--', label='Mean Demand (lambda=5)')
    
    plt.xlabel('Period')
    plt.ylabel('Order Quantity')
    plt.title('Single Echelon: Dynamic Ordering')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    
    plt.savefig(f"{output_dir}/single_echelon_orders.png")
    plt.close()

    print("Plots generated successfully.")
    
    # Generate Markdown Report
    generate_markdown_report(nv_data, bg_data, se_data, variances)

def extract_key_reasoning(reasoning_list):
    """Simple extraction of key phrases or just sampling the first few."""
    # Just take the first one and one from the middle/end to show evolution
    if not reasoning_list:
        return []
    
    samples = []
    indices = [0, len(reasoning_list)//2, len(reasoning_list)-1]
    for i in indices:
        if i < len(reasoning_list):
            samples.append(f"Week {i+1}: {reasoning_list[i]}")
    return samples

def generate_markdown_report(nv_data, bg_data, se_data, bg_variances):
    
    # Beer Game Reasoning Analysis
    bg_reasoning_summary = ""
    agents = ["Retailer", "Wholesaler", "Distributor", "Factory"]
    for agent in agents:
        r_list = bg_data[agent]["reasoning"]
        samples = extract_key_reasoning(r_list)
        bg_reasoning_summary += f"### {agent} 思考过程采样\n"
        for s in samples:
            bg_reasoning_summary += f"- {s}\n"
        bg_reasoning_summary += "\n"

    # Newsvendor Reasoning
    nv_reasoning_summary = ""
    for item in nv_data:
        cond = item["condition"]
        r_list = item["reasonings"]
        # Just take the first one
        if r_list:
            nv_reasoning_summary += f"- **{cond}**: {r_list[0]}\n"

    md_content = f"""# 库存管理对比实验结果分析 (v2)

**日期**: 2025年12月15日
**模型**: DeepSeek-V3 (via API)
**实验设置**: 
- 提示词语言: 中文
- 强制推理 (Chain-of-Thought): 是
- 实验包含: 报童问题, 啤酒游戏 (4级供应链), 单级动态库存

## 1. 报童问题 (Newsvendor Problem)

### 实验结果
| 情景 | 理论最优 (Optimal) | AI 平均决策 (Mean) | 标准差 (Std) | 偏差 (Bias) |
|------|-------------------|-------------------|-------------|-------------|
{chr(10).join([f"| {d['condition']} | {d['optimal']:.2f} | {np.mean(d['decisions']):.2f} | {np.std(d['decisions']):.2f} | {np.mean(d['decisions']) - d['optimal']:.2f} |" for d in nv_data])}

### 决策分析
![Newsvendor Comparison](experiment_results_v2/newsvendor_comparison.png)

### AI 推理采样
{nv_reasoning_summary}

---

## 2. 啤酒游戏 (Beer Game) - 牛鞭效应分析

### 牛鞭效应量化 (方差放大)
牛鞭效应通常表现为需求方差沿供应链上游逐级放大。

| 角色 (Role) | 订单方差 (Variance) | 放大倍数 (相对于消费者需求) |
|-------------|---------------------|----------------------------|
| Customer Demand | 0.0 (Step Change) | 1.0 |
| Retailer | {bg_variances['Retailer']:.2f} | - |
| Wholesaler | {bg_variances['Wholesaler']:.2f} | {bg_variances['Wholesaler']/bg_variances['Retailer']:.2f} (vs Retailer) |
| Distributor | {bg_variances['Distributor']:.2f} | {bg_variances['Distributor']/bg_variances['Wholesaler']:.2f} (vs Wholesaler) |
| Factory | {bg_variances['Factory']:.2f} | {bg_variances['Factory']/bg_variances['Distributor']:.2f} (vs Distributor) |

### 趋势图
![Beer Game Bullwhip](experiment_results_v2/beer_game_bullwhip.png)

### 归因分析 (基于 AI 思考过程)
通过分析 AI 的 `reasoning` 字段，我们可以观察到导致波动的心理因素：

{bg_reasoning_summary}

**观察总结**:
1. **恐慌性订货 (Panic Ordering)**: 当库存下降或出现缺货时，上游节点倾向于过度订货以补偿 backlog。
2. **忽视在途库存 (Pipeline Neglect)**: 尽管提示词中提供了 pipeline 数据，AI 往往低估了即将到达的货物，导致重复订货。
3. **需求预测偏差**: 在需求发生阶跃变化 (Step Change) 后，AI 需要多个周期适应，期间产生了剧烈的震荡。

---

## 3. 单级动态库存 (Single Echelon)

### 实验结果
- **理论最优 S**: {se_data['optimal_S']:.2f}
- **AI 平均订单**: {np.mean(se_data['orders']):.2f} (Mean Demand = 5)

### 趋势图
![Single Echelon](experiment_results_v2/single_echelon_orders.png)

### AI 推理采样
{extract_key_reasoning(se_data['reasoning'])[0] if se_data['reasoning'] else "无"}

"""
    
    report_path = repo_root / "artifacts" / "reports" / "Inventory_Comparison_Results_v2.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(md_content, encoding="utf-8")
    print(f"Markdown report generated: {report_path}")

if __name__ == "__main__":
    analyze_and_plot()
