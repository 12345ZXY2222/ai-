
import json
import matplotlib.pyplot as plt
import numpy as np
import os

def main():
    with open("bullwhip_reproduction_full.json", "r") as f:
        data = json.load(f)
        
    # Load new Sterman LLM data
    try:
        with open("sterman_llm_results.json", "r") as f:
            llm_data = json.load(f)
            data.update(llm_data)
    except FileNotFoundError:
        print("Warning: sterman_llm_results.json not found. Skipping LLM comparison.")
        llm_data = {}

    # Load Wang Blind data
    try:
        with open("wang_blind_results.json", "r") as f:
            blind_data = json.load(f)
            data.update(blind_data)
    except FileNotFoundError:
        print("Warning: wang_blind_results.json not found. Skipping Blind comparison.")
        blind_data = {}
        
    output_dir = "论文/experiment_results_v2"
    os.makedirs(output_dir, exist_ok=True)
    
    stages = ["Retailer", "Wholesaler", "Distributor", "Factory"]
    colors = ['b', 'g', 'orange', 'r']
    markers = ['o', 's', '^', 'x']
    
    # ==========================================
    # 1. Sterman Plot (Classic Oscillation)
    # ==========================================
    sterman = data["sterman"]
    rounds = len(sterman["Retailer"]["orders"])
    weeks = np.arange(1, rounds + 1)
    demand = [4 if t < 5 else 8 for t in weeks]
    
    # Plot 1: Orders
    plt.figure(figsize=(10, 6))
    plt.plot(weeks, demand, 'k--', label='Customer Demand', linewidth=2)
    
    for i, stage in enumerate(stages):
        plt.plot(weeks, sterman[stage]["orders"], color=colors[i], label=stage, marker=markers[i], markersize=5, alpha=0.8)
        
    plt.title("Sterman (1989): Orders (Replication)")
    plt.xlabel("Week")
    plt.ylabel("Orders (cases/week)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(f"{output_dir}/sterman_full.png")
    plt.close()

    # Plot 2: Inventory (New)
    plt.figure(figsize=(10, 6))
    for i, stage in enumerate(stages):
        plt.plot(weeks, sterman[stage]["inventory"], color=colors[i], label=stage, marker=markers[i], markersize=5, alpha=0.8)
    
    plt.title("Sterman (1989): Inventory Levels (Replication)")
    plt.xlabel("Week")
    plt.ylabel("Inventory (cases)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(f"{output_dir}/sterman_inventory.png")
    plt.close()
    
    # ==========================================
    # 1.5 Sterman vs DeepSeek Comparison (New)
    # ==========================================
    if "sterman_llm_neutral" in data:
        sterman_llm = data["sterman_llm_neutral"]
        
        # Plot: DeepSeek Orders on Sterman Demand
        plt.figure(figsize=(10, 6))
        plt.plot(weeks, demand, 'k--', label='Customer Demand', linewidth=2)
        
        for i, stage in enumerate(stages):
            plt.plot(weeks, sterman_llm[stage]["orders"], color=colors[i], label=stage, marker=markers[i], markersize=5, alpha=0.8)
            
        plt.title("DeepSeek-V3 (Risk Neutral) on Sterman Step Demand")
        plt.xlabel("Week")
        plt.ylabel("Orders (cases/week)")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.savefig(f"{output_dir}/sterman_deepseek_comparison.png")
        plt.close()
        
        # Plot: DeepSeek Inventory on Sterman Demand
        plt.figure(figsize=(10, 6))
        for i, stage in enumerate(stages):
            plt.plot(weeks, sterman_llm[stage]["inventory"], color=colors[i], label=stage, marker=markers[i], markersize=5, alpha=0.8)
        
        plt.title("DeepSeek-V3 (Risk Neutral) Inventory on Sterman Step Demand")
        plt.xlabel("Week")
        plt.ylabel("Inventory (cases)")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.savefig(f"{output_dir}/sterman_deepseek_inventory.png")
        plt.close()


    # ==========================================
    # 2. Wang Plots (3 Risk Profiles) - Combined 2x2 Figure
    # ==========================================
    profiles = ["wang_averse", "wang_neutral", "wang_seeking"]
    titles = ["Risk Averse", "Risk Neutral", "Risk Seeking"]
    
    # Create 2x2 subplot
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    axes = axes.flatten() # 0, 1, 2, 3
    
    # Plot 1-3: Orders for each profile
    for idx, profile_key in enumerate(profiles):
        ax = axes[idx]
        wang_data = data[profile_key]
        rounds_w = len(wang_data["Retailer"]["orders"])
        weeks_w = np.arange(1, rounds_w + 1)
        
        for i, stage in enumerate(stages):
            ax.plot(weeks_w, wang_data[stage]["orders"], color=colors[i], label=stage if idx==0 else "", marker=markers[i], markersize=4, alpha=0.7)
            
        ax.set_title(f"({chr(97+idx)}) {titles[idx]}") # (a), (b), (c)
        ax.set_xlabel("Round")
        ax.set_ylabel("Orders")
        ax.grid(True, alpha=0.3)
        if idx == 0:
            ax.legend(loc='upper right')

    # Plot 4: Variance Comparison (Replication of Fig 6d)
    ax = axes[3]
    
    # Calculate metrics first
    def get_vars(d):
        return {s: np.var(d[s]["orders"]) for s in stages}
        
    metrics = {
        "Wang Neutral": get_vars(data["wang_neutral"]),
        "Wang Averse": get_vars(data["wang_averse"]),
        "Wang Seeking": get_vars(data["wang_seeking"])
    }
    
    x = np.arange(len(stages))
    width = 0.25
    
    ax.bar(x - width, list(metrics["Wang Averse"].values()), width, label='Risk Averse', color='blue', alpha=0.7)
    ax.bar(x, list(metrics["Wang Neutral"].values()), width, label='Risk Neutral', color='orange', alpha=0.7)
    ax.bar(x + width, list(metrics["Wang Seeking"].values()), width, label='Risk Seeking', color='green', alpha=0.7)
    
    ax.set_xlabel('Supply Chain Stage')
    ax.set_ylabel('Order Variance')
    ax.set_title('(d) Variance Amplification')
    ax.set_xticks(x)
    ax.set_xticklabels(stages)
    ax.legend()
    ax.grid(True, axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/wang_combined_2x2.png")
    plt.close()

    # Keep the combined comparison plot as well
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=True)
    for idx, profile_key in enumerate(profiles):
        ax = axes[idx]
        wang_data = data[profile_key]
        rounds_w = len(wang_data["Retailer"]["orders"])
        weeks_w = np.arange(1, rounds_w + 1)
        for i, stage in enumerate(stages):
            ax.plot(weeks_w, wang_data[stage]["orders"], color=colors[i], label=stage if idx==0 else "", marker=markers[i], markersize=4, alpha=0.7)
        ax.set_title(f"{titles[idx]}")
        ax.set_xlabel("Round")
        if idx == 0:
            ax.set_ylabel("Orders")
        ax.grid(True, alpha=0.3)
    fig.legend(loc='upper right', bbox_to_anchor=(0.95, 0.95))
    plt.tight_layout()
    plt.savefig(f"{output_dir}/wang_risk_comparison.png")
    plt.close()

    # ==========================================
    # 2.5 Wang Blind Plots (No Capacity/Info)
    # ==========================================
    blind_profiles = ["wang_blind_neutral", "wang_blind_averse", "wang_blind_seeking"]
    blind_titles = ["Risk Neutral (Blind)", "Risk Averse (Blind)", "Risk Seeking (Blind)"]
    blind_filenames = ["wang_blind_neutral.png", "wang_blind_averse.png", "wang_blind_seeking.png"]
    
    for idx, profile_key in enumerate(blind_profiles):
        if profile_key in data:
            plt.figure(figsize=(10, 6))
            wang_data = data[profile_key]
            rounds_w = len(wang_data["Retailer"]["orders"])
            weeks_w = np.arange(1, rounds_w + 1)
            
            for i, stage in enumerate(stages):
                plt.plot(weeks_w, wang_data[stage]["orders"], color=colors[i], label=stage, marker=markers[i], markersize=4, alpha=0.7)
                
            plt.title(f"Wang Blind (No Cap/Info): {blind_titles[idx]}")
            plt.xlabel("Round")
            plt.ylabel("Orders")
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.savefig(f"{output_dir}/{blind_filenames[idx]}")
            plt.close()

    # ==========================================
    # 3. Metrics Calculation & Variance Plot
    # ==========================================
    print("Calculating Metrics...")
    
    def get_vars(d):
        return {s: np.var(d[s]["orders"]) for s in stages}
        
    metrics = {
        "Sterman": get_vars(sterman),
        "Wang Neutral": get_vars(data["wang_neutral"]),
        "Wang Averse": get_vars(data["wang_averse"]),
        "Wang Seeking": get_vars(data["wang_seeking"])
    }
    
    if "wang_blind_neutral" in data:
        metrics["Wang Blind Neutral"] = get_vars(data["wang_blind_neutral"])
        metrics["Wang Blind Averse"] = get_vars(data["wang_blind_averse"])
        metrics["Wang Blind Seeking"] = get_vars(data["wang_blind_seeking"])

    # Plot 3: Variance Comparison (Bar Chart) - Replicating Wang Fig 6d
    plt.figure(figsize=(12, 6))
    x = np.arange(len(stages))
    width = 0.15
    
    # Plotting standard Wang results
    plt.bar(x - width, list(metrics["Wang Averse"].values()), width, label='Risk Averse', color='blue', alpha=0.7)
    plt.bar(x, list(metrics["Wang Neutral"].values()), width, label='Risk Neutral', color='orange', alpha=0.7)
    plt.bar(x + width, list(metrics["Wang Seeking"].values()), width, label='Risk Seeking', color='green', alpha=0.7)
    
    plt.xlabel('Supply Chain Stage')
    plt.ylabel('Order Variance')
    plt.title('Variance Amplification (Replication of Wang Fig 6d)')
    plt.xticks(x, stages)
    plt.legend()
    plt.grid(True, axis='y', alpha=0.3)
    plt.savefig(f"{output_dir}/wang_variance_reproduction.png")
    plt.close()
    
    # Print metrics table to console instead of overwriting report
    print("\nVariance Metrics Table:")
    print("| Model | Retailer | Wholesaler | Distributor | Factory |")
    print("|---|---|---|---|---|")
    for model, vars in metrics.items():
        print(f"| {model} | {vars['Retailer']:.2f} | {vars['Wholesaler']:.2f} | {vars['Distributor']:.2f} | {vars['Factory']:.2f} |")

# Removed generate_report to prevent overwriting the manually edited MD file

if __name__ == "__main__":
    main()
