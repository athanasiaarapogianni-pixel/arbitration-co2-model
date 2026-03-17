import streamlit as st
import pandas as pd

# --- 1. DATA & CONSTANTS (From your Assumptions Sheet) ---
st.set_page_config(page_title="Arbitration CO2 Model", layout="wide")

FACTORS = {
    "comp_month": 6.4444, 
    "email": 0.004,
    "data_gb": 0.021,
    "hotel_avg": 25.0,
    "transport": {
        "Plane (Business)": 0.274,
        "Plane (Economy)": 0.182,
        "Rail": 0.035,
        "Car (non-electric)": 0.151,
        "Car (electric)": 0.055
    }
}

CITIES = ["London", "Paris", "Munich", "Madrid", "Milan", "Frankfurt", "Warsaw", "Geneva", "New York", "Singapore"]

def get_dist(city_a, city_b):
    if city_a == city_b: return 0
    return 850 # In full version, this maps to your Travel Matrix

# --- 2. THE UI ---
st.title("⚖️ Arbitration Carbon Impact Model")

with st.sidebar:
    st.header("Global Case Settings")
    months = st.number_input("Case Duration (Months)", value=24)
    total_data = st.number_input("Total Data Generated (GB)", value=10)
    is_virtual = st.toggle("Virtual Hearing", value=False)
    
    if not is_virtual:
        h_city = st.selectbox("Hearing City", CITIES, index=1)
        h_days = st.slider("Hearing Days", 1, 20, 5)
    else:
        h_city, h_days = "Virtual", 0

# Input Tabs
t1, t2, t3 = st.tabs(["🔴 Claimant", "🔵 Respondent", "⚖️ Tribunal"])

def get_team_inputs(prefix):
    st.markdown(f"**Group Locations & Sizes**")
    c1, c2, c3 = st.columns(3)
    cli_sz = c1.number_input("Client Size", value=3, key=f"{prefix}1")
    cou_sz = c1.number_input("Counsel Size", value=4, key=f"{prefix}2")
    exp_sz = c1.number_input("Expert Size", value=2, key=f"{prefix}3")
    
    city = c2.selectbox("Base City", CITIES, key=f"{prefix}4")
    mode = c3.selectbox("Travel Mode", list(FACTORS['transport'].keys()), key=f"{prefix}5")
    return {"total_sz": cli_sz + cou_sz + exp_sz, "city": city, "mode": mode}

with t1: c_data = get_team_inputs("c")
with t2: r_data = get_team_inputs("r")
with t3:
    st.markdown("**Tribunal (3 Arbitrators)**")
    t_city = st.selectbox("Tribunal City", CITIES, key="t_ct")
    t_mode = st.selectbox("Tribunal Travel", list(FACTORS['transport'].keys()), key="t_md")
    t_data = {"total_sz": 3, "city": t_city, "mode": t_mode}

# --- 3. THE CALCULATION ENGINE (Matching 'Outputs' Tab) ---
def get_party_breakdown(group, data_share, virtual):
    # Digital (Scope 2 & 3 Computer Use)
    digital = group['total_sz'] * months * FACTORS['comp_month']
    
    # Data Storage (Pro-rated share of total GB)
    data_impact = data_share * FACTORS['data_gb']
    
    # Travel & Hotel
    if virtual or group['total_sz'] == 0:
        travel, hotel = 0, 0
    else:
        dist = get_dist(group['city'], h_city)
        travel = dist * 2 * group['total_sz'] * FACTORS['transport'][group['mode']]
        hotel = group['total_sz'] * h_days * FACTORS['hotel_avg']
        
    return {
        "Digital (Computer/Email)": digital,
        "Data Storage": data_impact,
        "Travel": travel,
        "Hotel Stays": hotel,
        "Total": digital + data_impact + travel + hotel
    }

# Assign data shares (1/3 each for simplicity, or 40/40/20)
c_results = get_party_breakdown(c_data, total_data * 0.4, is_virtual)
r_results = get_party_breakdown(r_data, total_data * 0.4, is_virtual)
t_results = get_party_breakdown(t_data, total_data * 0.2, is_virtual)

# --- 4. OUTPUTS (The 'Excel' Structure) ---
st.divider()
st.header("Results Summary (kgCO2e)")

def display_party_card(name, results, color):
    with st.container():
        st.markdown(f"### {color} {name}")
        col_a, col_b = st.columns([1, 2])
        
        # Table of results
        df = pd.DataFrame.from_dict(results, orient='index', columns=['kgCO2e'])
        col_a.table(df.style.format("{:,.2f}"))
        
        # Mini chart
        col_b.bar_chart(df.drop("Total"))

display_party_card("Claimant", c_results, "🔴")
st.divider()
display_party_card("Respondent", r_results, "🔵")
st.divider()
display_party_card("Tribunal", t_results, "⚖️")

# Grand Total Metric
st.sidebar.divider()
st.sidebar.metric("GRAND TOTAL", f"{c_results['Total'] + r_results['Total'] + t_results['Total']:,.0f} kg")
