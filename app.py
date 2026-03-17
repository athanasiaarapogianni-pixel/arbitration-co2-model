import streamlit as st
import pandas as pd

# --- 1. SETUP & CORE DATA ---
st.set_page_config(page_title="Arbitration CO2 Model", layout="wide")

# Emission Factors (from your Assumptions sheet)
FACTORS = {
    "comp_month": 6.4444, # kgCO2e/person
    "email": 0.004,
    "hotel": {3: 15.5, 4: 21.7, 5: 35.2}, # kgCO2e/night (Germany avg)
    "data_gb": 0.021,
    "materials": {"notebook": 0.37, "pen": 0.05, "cup": 0.018},
    "transport": {
        "Plane (Business)": 0.274,
        "Plane (Economy)": 0.182,
        "Rail": 0.035,
        "Car (non-electric)": 0.151,
        "Car (electric)": 0.055
    }
}

# Standardized City List (Extend as needed)
CITIES = ["Munich", "Madrid", "London", "Milan", "Frankfurt", "Paris", "Warsaw", "Geneva", "New York", "Singapore"]

def get_dist(origin, destination):
    if origin == destination: return 0
    # Average European travel distance for calculation logic
    return 850 

# --- 2. USER INTERFACE ---
st.title("⚖️ Professional Arbitration Carbon Impact Model")

with st.sidebar:
    st.header("🌍 Global Case Parameters")
    case_months = st.number_input("Arbitration Duration (Months)", value=24)
    total_data = st.number_input("Total Data Generated (GB)", value=10)
    is_virtual = st.toggle("Virtual Hearing", value=False)
    
    if not is_virtual:
        h_city = st.selectbox("Hearing City", CITIES, index=5) # Default Paris
        h_days = st.slider("Hearing Duration (Days)", 1, 21, 5)
    else:
        h_city, h_days = "Virtual", 0

# Tabs for Granular Inputs
tab_claimant, tab_respondent, tab_tribunal = st.tabs(["🔴 Claimant", "🔵 Respondent", "⚖️ Tribunal"])

def subteam_inputs(label, prefix):
    st.markdown(f"**{label}**")
    c1, c2, c3, c4 = st.columns([1, 1.5, 1.5, 1])
    size = c1.number_input("Size", value=2, key=f"{prefix}_sz", min_value=0)
    city = c2.selectbox("Base City", CITIES, key=f"{prefix}_ct")
    mode = c3.selectbox("Travel Mode", list(FACTORS['transport'].keys()), key=f"{prefix}_md")
    stars = c4.selectbox("Hotel", [3, 4, 5], index=1, key=f"{prefix}_st")
    return {"size": size, "city": city, "mode": mode, "stars": stars}

def meeting_inputs(label, prefix):
    st.markdown(f"**Meetings at {label} Location**")
    col1, col2 = st.columns(2)
    m_count = col1.number_input("Number of Meetings", value=1 if "Claimant" in label else 0, key=f"{prefix}_mc")
    m_days = col2.number_input("Total Days (Sum)", value=3 if "Claimant" in label else 0, key=f"{prefix}_md")
    
    st.write("Attendees from other sub-teams:")
    at1, at2 = st.columns(2)
    # Note: Logic is "everyone else travels to this location"
    return {"count": m_count, "days": m_days}

# --- PILLAR 1: CLAIMANT ---
with tab_claimant:
    c_cli = subteam_inputs("Client Team", "c_cli")
    c_cou = subteam_inputs("Legal Counsel", "c_cou")
    c_exp = subteam_inputs("Experts", "c_exp")
    st.divider()
    c_meet_cli = meeting_inputs("Claimant Office", "c_m_cli")
    c_meet_cou = meeting_inputs("Counsel Chambers", "c_m_cou")
    c_meet_exp = meeting_inputs("Expert Office", "c_m_exp")

# --- PILLAR 2: RESPONDENT ---
with tab_respondent:
    r_cli = subteam_inputs("Client Team", "r_cli")
    r_cou = subteam_inputs("Legal Counsel", "r_cou")
    r_exp = subteam_inputs("Experts", "r_exp")
    st.divider()
    r_meet_cli = meeting_inputs("Respondent Office", "r_m_cli")
    r_meet_cou = meeting_inputs("Counsel Chambers", "r_m_cou")
    r_meet_exp = meeting_inputs("Expert Office", "r_m_exp")

# --- PILLAR 3: TRIBUNAL ---
with tab_tribunal:
    st.info("Arbitrators only travel to the Hearing location.")
    arb1 = subteam_inputs("Arbitrator 1", "t_a1")
    arb2 = subteam_inputs("Arbitrator 2", "t_a2")
    arb3 = subteam_inputs("Arbitrator 3", "t_a3")

# --- 3. CALCULATION ENGINE ---
def calculate_party(party_name, teams, meetings, data_share):
    # Base Categories
    res = {
        "Scope 2: Printing & Email": 2.5, # Placeholder baseline
        "Scope 2: Computer Use": sum(t['size'] for t in teams) * case_months * FACTORS['comp_month'] * 0.15,
        "Scope 3: Printing & Email (WTT)": 2.5,
        "Scope 3: Data Storage": data_share * FACTORS['data_gb'],
        "Scope 3: Computer (Mfg/Ops)": sum(t['size'] for t in teams) * case_months * FACTORS['comp_month'] * 0.85,
        "Scope 3: Travel": 0,
        "Scope 3: Hotel Stays": 0,
        "Scope 3: Material Use": sum(t['size'] for t in teams) * (FACTORS['materials']['notebook'] + FACTORS['materials']['pen'])
    }

    # A. Hearing Travel & Hotel
    if not is_virtual:
        for t in teams:
            dist = get_dist(t['city'], h_city)
            res["Scope 3: Travel"] += dist * 2 * t['size'] * FACTORS['transport'][t['mode']]
            res["Scope 3: Hotel Stays"] += t['size'] * h_days * FACTORS['hotel'][t['stars']]

    # B. Prep Meetings Matrix (Claimant & Respondent Only)
    if meetings:
        # Locations: 0=Client, 1=Counsel, 2=Expert
        loc_cities = [teams[0]['city'], teams[1]['city'], teams[2]['city']]
        for i, m in enumerate(meetings):
            if m['count'] > 0:
                target_city = loc_cities[i]
                for j, t in enumerate(teams):
                    if i != j: # If you are NOT at home, you travel
                        dist = get_dist(t['city'], target_city)
                        res["Scope 3: Travel"] += dist * 2 * m['count'] * t['size'] * FACTORS['transport'][t['mode']]
                        res["Scope 3: Hotel Stays"] += t['size'] * m['days'] * FACTORS['hotel'][t['stars']]
    
    return res

# Run Calcs
c_res = calculate_party("Claimant", [c_cli, c_cou, c_exp], [c_meet_cli, c_meet_cou, c_meet_exp], total_data * 0.4)
r_res = calculate_party("Respondent", [r_cli, r_cou, r_exp], [r_meet_cli, r_meet_cou, r_meet_exp], total_data * 0.4)
t_res = calculate_party("Tribunal", [arb1, arb2, arb3], None, total_data * 0.2)

# --- 4. OUTPUTS (The Excel 'Results' Structure) ---
st.divider()
st.header("Detailed Emissions Breakdown (kgCO2e)")

def display_results(name, data):
    with st.expander(f"View {name} Results Breakdown", expanded=True):
        col_t, col_c = st.columns([1, 1.5])
        df = pd.DataFrame.from_dict(data, orient='index', columns=['kgCO2e'])
        col_t.table(df.style.format("{:,.2f}"))
        col_t.markdown(f"**Total {name}: {df['kgCO2e'].sum():,.2f} kg**")
        col_c.bar_chart(df)

display_results("Claimant", c_res)
display_results("Respondent", r_res)
display_results("Tribunal", t_res)

# Summary Sidebar Metric
st.sidebar.divider()
grand_total = sum(c_res.values()) + sum(r_res.values()) + sum(t_res.values())
st.sidebar.metric("GRAND TOTAL IMPACT", f"{grand_total:,.0f} kg")
