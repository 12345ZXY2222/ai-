import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os

# Configuration
RESULTS_DIR = "/home/peirm/ai模拟平台/论文/experiment_results"
CSV_FILE = os.path.join(RESULTS_DIR, "morality_results_v2.csv")
PLOT_1 = os.path.join(RESULTS_DIR, "model_comparison_action_a.png")
PLOT_2 = os.path.join(RESULTS_DIR, "model_comparison_payoffs.png")

def main():
    # 1. Load Data
    if not os.path.exists(CSV_FILE):
        print(f"Error: CSV file not found at {CSV_FILE}")
        return
    
    df = pd.read_csv(CSV_FILE)
    print(f"Loaded data from {CSV_FILE}, {len(df)} rows.")

    # 2. Remove old plots
    for p in [PLOT_1, PLOT_2]:
        if os.path.exists(p):
            os.remove(p)
            print(f"Removed old plot: {p}")

    # 3. Set Style
    sns.set_theme(style="whitegrid")

    # 4. Plot 1: Action A by Game, Condition, and Model
    print("Generating Plot 1...")
    g1 = sns.catplot(
        data=df, x="Game", y="Action_A", hue="Condition", col="Model", 
        kind="bar", height=5, aspect=1.2,
        errorbar=None  # Remove error bars
    )
    g1.fig.subplots_adjust(top=0.9)
    g1.fig.suptitle("Primary Action (Offer/Contrib/Transfer) by Game & Condition")
    plt.savefig(PLOT_1)
    print(f"Saved {PLOT_1}")
    plt.close()

    # 5. Plot 2: Payoff Distribution
    print("Generating Plot 2...")
    df_melted = df.melt(id_vars=["Model", "Game", "Condition"], value_vars=["Payoff_A", "Payoff_B"], var_name="Player", value_name="Payoff")
    
    g2 = sns.catplot(
        data=df_melted, x="Game", y="Payoff", hue="Player", col="Model", row="Condition",
        kind="bar", height=4, aspect=1.5,
        errorbar=None # Remove error bars
    )
    g2.fig.subplots_adjust(top=0.9)
    g2.fig.suptitle("Average Payoffs by Game & Player")
    plt.savefig(PLOT_2)
    print(f"Saved {PLOT_2}")
    plt.close()

if __name__ == "__main__":
    main()
