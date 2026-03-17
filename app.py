import streamlit as st
import pandas as pd

# --- 1. SETTINGS & FACTORS ---
st.set_page_config(page_title="Arbitration CO2 Tool", layout="wide")

# From your "Assumptions" sheet
FACTORS = {
    "comp_month": 6.444, # kgCO2e/person
    "email": 0.004,      # kgCO2e/unit
    "data_gb": 0.021,    # kgCO2e/GB
    "transport": {
        "Plane (Business)": 0.274,
        "Plane (Economy)": 0.182,
        "Rail": 0.035,
        "Car (non-electric)": 0.151
    }
}

# --- 2. THE THREE-PILLAR ENGINE ---
def calculate_arbitration_co2(data):
    # Base Case Data
    months = data['global_months']
    
    # 1. CLAIMANT PILLAR (Team + Counsel + Experts)
    c_people = data['c_team'] + data['c_counsel'] + data['c_experts']
    c_digital = c_people * months * FACTORS['comp_month']
    c_travel = get_distance(data['c_city'], data['hearing_city']) * 2 * c_people * FACTORS['transport'].get(data['c_mode'], 0.18)
    
    # 2. RESPONDENT PILLAR (Team + Counsel + Experts)
    r_people = data['r_team'] + data['r_counsel'] + data['r_experts']
    r_digital = r_people * months * FACTORS['comp_month']
    r_travel = get_distance(data['r_city'], data['hearing_city']) * 2 * r_people * FACTORS['transport'].get(data['r_mode'], 0.18)
    
    # 3. TRIBUNAL PILLAR (Arbitrators Only)
    t_people = data['arbitrators']
    t_digital = t_people * months * FACTORS['comp_month']
    # Arbitrators often travel from different cities, here we use a collective average
    t_travel = get_distance(data['t_city'], data['hearing_city']) * 2 * t_people * FACTORS['transport'].get(data['t_mode'], 0.18)
    
    return {
        "Claimant": c_digital + c_travel,
        "Respondent": r_digital + r_travel,
        "Tribunal": t_digital + t_travel
    }

def get_distance(city_a, city_b):
    # Simplified lookup (Matches your Travel Matrix logic)
    distances = {("Munich", "Paris"): 684, ("London", "Paris"): 344, ("Milan", "Paris"): 640}
    return distances.get(tuple(sorted((city_a, city_b))), 1000)

# --- 3. THE INTERFACE ---
st.title("⚖️ Arbitration Carbon Impact Model")

# Global Settings
with st.sidebar:
    st.header("Case Parameters")
    case_months = st.number_input("Arbitration Duration (Months)", value=24)
    hearing_city = st.selectbox("Hearing Location", ["Paris", "London", "Munich", "Geneva"])

# The 3 Pillars Layout
col1, col2, col3 = st.columns(3)

with col1:
    st.header("Claimant")
    c_team = st.number_input("Client Team", 1, 20, 3)
    c_counsel = st.number_input("Counsel", 1, 20, 4)
    c_experts = st.number_input("Experts", 0, 20, 2)
    c_city = st.text_input("Home City (Claimant)", "Munich")
    c_mode = st.selectbox("Travel Mode (C)", list(FACTORS['transport'].keys()))

with col2:
    st.header("Respondent")
    r_team = st.number_input("Client Team ", 1, 20, 2)
    r_counsel = st.number_input("Counsel ", 1, 20, 5)
    r_experts = st.number_input("Experts ", 0, 20, 3)
    r_city = st.text_input("Home City (Respondent)", "Milan")
    r_mode = st.selectbox("Travel Mode (R)", list(FACTORS['transport'].keys()))

with col3:
    st.header("Tribunal")
    arbitrators = st.number_input("Number of Arbitrators", 1, 3, 3)
    t_city = st.text_input("Home City (Tribunal)", "London")
    t_mode = st.selectbox("Travel Mode (T)", list(FACTORS['transport'].keys()))

# Calculations
results = calculate_arbitration_co2({
    "global_months": case_months, "hearing_city": hearing_city,
    "c_team": c_team, "c_counsel": c_counsel, "c_experts": c_experts, "c_city": c_city, "c_mode": c_mode,
    "r_team": r_team, "r_counsel": r_counsel, "r_experts": r_experts, "r_city": r_city, "r_mode": r_mode,
    "arbitrators": arbitrators, "t_city": t_city, "t_mode": t_mode
})

# --- 4. OUTPUTS ---
st.divider()
total_co2 = sum(results.values())
st.subheader(f"Total Case Footprint: {total_co2:,.0f} kgCO2e")

res_col1, res_col2, res_col3 = st.columns(3)
res_col1.metric("Claimant Share", f"{results['Claimant']:,.0f} kg")
res_col2.metric("Respondent Share", f"{results['Respondent']:,.0f} kg")
res_col3.metric("Tribunal Share", f"{results['Tribunal']:,.0f} kg")
