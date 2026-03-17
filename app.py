import streamlit as st
import pandas as pd
import openpyxl

# --- 1. SETUP & CORE DATA ---
st.set_page_config(page_title="Arbitration CO2 Model", layout="wide")

FACTORS = {
    "comp_month": 6.4444, 
    "email_std": 0.004,
    "email_large": 0.05,
    "hotel": {3: 15.5, 4: 21.7, 5: 35.2}, 
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

CITIES = ["Munich", "Madrid", "London", "Milan", "Frankfurt", "Paris", "Warsaw", "Geneva", "New York", "Singapore"]

def get_dist(origin, destination):
    if origin == destination: return 0
    return 850 

# --- 2. SIDEBAR PARAMETERS ---
with st.sidebar:
    st.header("🌍 Global Case Parameters")
    case_months = st.number_input("Arbitration Duration (Months)", value=24)
    total_data = st.number_input("Total Data Generated (GB)", value=10)
    is_virtual = st.toggle("Virtual Hearing", value=False)
    
    if not is_virtual:
        h_city = st.selectbox("Hearing City", CITIES, index=5)
        h_days = st.slider("Hearing Duration (Days)", 1, 21, 5)
    else:
        h_city, h_days = "Virtual", 0
    
    st.divider()
    st.info("Complete all tabs, then click below to export:")
    export_btn = st.button("💾 Update Excel Template (C30-C55)")

# --- 3. UI TABS ---
st.title("⚖️ Professional Arbitration Carbon Impact Model")
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
    return {"count": m_count, "days": m_days}

with tab_claimant:
    c_cli = subteam_inputs("Client Team", "c_cli")
    c_cou = subteam_inputs("Legal Counsel", "c_cou")
    c_exp = subteam_inputs("Experts", "c_exp")
    st.divider()
    c_meet_cli = meeting_inputs("Claimant Office", "c_m_cli")
    c_meet_cou = meeting_inputs("Counsel Chambers", "c_m_cou")
    c_meet_exp = meeting_inputs("Expert Office", "c_m_exp")

with tab_respondent:
    r_cli = subteam_inputs("Client Team", "r_cli")
    r_cou = subteam_inputs("Legal Counsel", "r_cou")
    r_exp = subteam_inputs("Experts", "r_exp")
    st.divider()
    r_meet_cli = meeting_inputs("Respondent Office", "r_m_cli")
    r_meet_cou = meeting_inputs("Counsel Chambers", "r_m_cou")
    r_meet_exp = meeting_inputs("Expert Office", "r_m_exp")

with tab_tribunal:
    arb1 = subteam_inputs("Arbitrator 1", "t_a1")
    arb2 = subteam_inputs("Arbitrator 2", "t_a2")
    arb3 = subteam_inputs("Arbitrator 3", "t_a3")

# --- 4. CALCULATION ENGINE ---
def calculate_party(teams, meetings, data_share):
    res = {
        "Digital (Comp/Data)": (sum(t['size'] for t in teams) * case_months * FACTORS['comp_month']) + (data_share * FACTORS['data_gb']),
        "Travel (Prep & Hearing)": 0,
        "Hotel Stays": 0,
        "Materials": sum(t['size'] for t in teams) * (FACTORS['materials']['notebook'] + FACTORS['materials']['pen'])
    }
    # Hearing travel
    if not is_virtual:
        for t in teams:
            res["Travel (Prep & Hearing)"] += get_dist(t['city'], h_city) * 2 * t['size'] * FACTORS['transport'][t['mode']]
            res["Hotel Stays"] += t['size'] * h_days * FACTORS['hotel'][t['stars']]
    # Meeting travel
    if meetings:
        loc_cities = [teams[0]['city'], teams[1]['city'], teams[2]['city']]
        for i, m in enumerate(meetings):
            if m['count'] > 0:
                for j, t in enumerate(teams):
                    if i != j:
                        res["Travel (Prep & Hearing)"] += get_dist(t['city'], loc_cities[i]) * 2 * m['count'] * t['size'] * FACTORS['transport'][t['mode']]
                        res["Hotel Stays"] += t['size'] * m['days'] * FACTORS['hotel'][t['stars']]
    return res

c_res = calculate_party([c_cli, c_cou, c_exp], [c_meet_cli, c_meet_cou, c_meet_exp], total_data * 0.4)
r_res = calculate_party([r_cli, r_cou, r_exp], [r_meet_cli, r_meet_cou, r_meet_exp], total_data * 0.4)
t_res = calculate_party([arb1, arb2, arb3], None, total_data * 0.2)

# --- 5. TOP-LEVEL SUMMARY DASHBOARD ---
st.divider()
col_sum1, col_sum2, col_sum3, col_sum4 = st.columns(4)
c_total = sum(c_res.values())
r_total = sum(r_res.values())
t_total = sum(t_res.values())
grand_total = c_total + r_total + t_total

col_sum1.metric("GRAND TOTAL (kg)", f"{grand_total:,.1f}")
col_sum2.metric("Claimant Total", f"{c_total:,.1f}")
col_sum3.metric("Respondent Total", f"{r_total:,.1f}")
col_sum4.metric("Tribunal Total", f"{t_total:,.1f}")

# --- 6. EXCEL EXPORT (Triggered by Sidebar Button) ---
if export_btn:
    try:
        wb = openpyxl.load_workbook('arbitration_tool.xlsx')
        sheet = wb.active
        # Excel Mapping
        sheet['C31'] = c_res["Digital (Comp/Data)"]
        sheet['C32'] = total_data * FACTORS['data_gb']
        # Split travel/hotel into the requested blocks
        sheet['C40'], sheet['C41'] = c_res["Travel (Prep & Hearing)"]*0.3, c_res["Hotel Stays"]*0.3
        sheet['C44'], sheet['C45'] = c_res["Travel (Prep & Hearing)"]*0.3, c_res["Hotel Stays"]*0.3
        sheet['C48'], sheet['C49'] = c_res["Travel (Prep & Hearing)"]*0.4, c_res["Hotel Stays"]*0.4
        
        wb.save('Arbitration_Report_Final.xlsx')
        st.sidebar.success("Excel Updated!")
    except Exception as e:
        st.sidebar.error(f"Excel Error: {str(e)}")

# --- 7. VISUAL BREAKDOWNS ---
st.header("Detailed Breakdown per Party")
def display_party(name, data):
    with st.expander(f"Show {name} Breakdown", expanded=True):
        df = pd.DataFrame.from_dict(data, orient='index', columns=['kgCO2e'])
        c1, c2 = st.columns([1, 2])
        c1.table(df.style.format("{:,.2f}"))
        c2.bar_chart(df)

display_party("Claimant", c_res)
display_party("Respondent", r_res)
display_party("Tribunal", t_res)
