
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

# Data from the report
# Truncating to 10 rounds as per report description
rounds = np.arange(1, 11)

data = {
    "Customer": [1, 6, 2, 1, 4, 5, 6, 2, 0, 8, 2][:10],
    "Retailer": [1, 6, 2, 2, 5, 5, 6, 2, 5, 8, 2][:10],
    "Wholesaler": [1, 7, 2, 2, 5, 5, 7, 4, 5, 8],
    "Distributor": [2, 7, 2, 2, 5, 7, 7, 6, 5, 9],
    "Manufacturer": [2, 7, 2, 3, 5, 7, 7, 7, 5, 9]
}

# Setup Chinese font
import matplotlib.font_manager as fm
font_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
prop = fm.FontProperties(fname=font_path)
plt.rcParams['font.family'] = prop.get_name()


# 1. Line Chart: Orders over time
plt.figure(figsize=(12, 6))
markers = ['o', 's', '^', 'D', 'v']
for i, (role, values) in enumerate(data.items()):
    plt.plot(rounds, values, marker=markers[i], label=role, linewidth=2)

plt.title('各级订货量趋势 (Order Quantity Trend)', fontsize=16, fontproperties=prop)
plt.xlabel('模拟轮次 (Round)', fontsize=12, fontproperties=prop)
plt.ylabel('订货量 (Order Quantity)', fontsize=12, fontproperties=prop)
plt.xticks(rounds)
plt.grid(True, linestyle='--', alpha=0.7)
plt.legend(prop=prop)
plt.tight_layout()
plt.savefig('bullwhip_orders.png')
print("Generated bullwhip_orders.png")

# 2. Demand Coverage / Amplification Analysis
# Since we don't have inventory/shipment data, we analyze "Order vs Demand"
# We can plot the ratio of (Order Placed / Demand Received) for each level
# Retailer Demand = Customer Order
# Wholesaler Demand = Retailer Order
# ...

plt.figure(figsize=(12, 6))

# Calculate Ratios (avoid division by zero)
def safe_div(a, b):
    return np.divide(a, b, out=np.zeros_like(a, dtype=float), where=b!=0)

# Retailer Coverage (Retailer Order / Customer Demand)
r_coverage = safe_div(data['Retailer'], data['Customer'])
# Wholesaler Coverage (Wholesaler Order / Retailer Order)
w_coverage = safe_div(data['Wholesaler'], data['Retailer'])
# Distributor Coverage (Distributor Order / Wholesaler Order)
d_coverage = safe_div(data['Distributor'], data['Wholesaler'])
# Manufacturer Coverage (Manufacturer Order / Distributor Order)
m_coverage = safe_div(data['Manufacturer'], data['Distributor'])

plt.plot(rounds, r_coverage, marker='s', label='Retailer/Customer', linestyle='--')
plt.plot(rounds, w_coverage, marker='^', label='Wholesaler/Retailer', linestyle='--')
plt.plot(rounds, d_coverage, marker='D', label='Distributor/Wholesaler', linestyle='--')
plt.plot(rounds, m_coverage, marker='v', label='Manufacturer/Distributor', linestyle='--')

plt.axhline(y=1.0, color='r', linestyle='-', alpha=0.3, label='Balance (1.0)')

plt.title('各级需求放大/覆盖率 (Order Amplification/Coverage Ratio)', fontsize=16, fontproperties=prop)
plt.xlabel('模拟轮次 (Round)', fontsize=12, fontproperties=prop)
plt.ylabel('订货/需求比率 (Order/Demand Ratio)', fontsize=12, fontproperties=prop)
plt.xticks(rounds)
plt.grid(True, linestyle='--', alpha=0.7)
plt.legend(prop=prop)
plt.tight_layout()
plt.savefig('bullwhip_coverage.png')
print("Generated bullwhip_coverage.png")
