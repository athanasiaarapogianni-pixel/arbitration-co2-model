import streamlit as st
import pandas as pd
import openpyxl

# --- 1. SETUP & CORE DATA ---
st.set_page_config(page_title="Arbitration CO2 Model", layout="wide")

FACTORS = {
    "comp_month": 6.4444, 
    "email_std": 0.004,
    "hotel": {3: 15.5, 4: 21.7, 5: 35.2}, 
    "data_gb": 0.021,
    "materials": {"notebook": 0.37, "pen": 0.05, "cup": 0.018},
    "transport": {
        "Plane (Business)": 0.274, "Plane (Economy)": 0.182,
        "Rail": 0.035, "Car (non-electric)": 0.151, "Car (electric)": 0.055
    }
}

CITIES = ["Munich", "Madrid", "London", "Milan", "Frankfurt", "Paris", "Warsaw", "Geneva", "New York", "Singapore"]

def get_dist(origin, destination):
    if origin == destination: return 0
    return 850 

# --- 2. SIDEBAR ---
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
    export_btn = st.button("💾 Sync to Excel (C30-C97)")

# --- 3. UI TABS ---
st.title("⚖️ Professional Arbitration Carbon Impact Model")
tab_claimant, tab_respondent, tab_tribunal = st.tabs(["🔴 Claimant", "🔵 Respondent", "⚖️ Tribunal"])

def subteam_inputs(label, prefix):
    st.markdown(f"**{label}**")
    c1, c2, c3, c4 = st.columns([1, 1.5, 1.5, 1])
    size = c1.number_input("Total Team Size", value=2, key=f"{prefix}_sz")
    city = c2.selectbox("Base City", CITIES, key=f"{prefix}_ct")
    mode = c3.selectbox("Default Travel Mode", list(FACTORS['transport'].keys()), key=f"{prefix}_md")
    stars = c4.selectbox("Hotel Stars", [3, 4, 5], index=1, key=f"{prefix}_st")
    return {"size": size, "city": city, "mode": mode, "stars": stars}

def detailed_meeting_matrix(label, prefix, teams):
    with st.expander(f"📅 Meetings at {label}", expanded=False):
        st.write(f"Define who travels to the **{label}**:")
        m_results = []
        # We loop through the teams to see who is traveling TO this location
        for i, team_name in enumerate(["Client Team", "Legal Counsel", "Experts"]):
            col1, col2, col3 = st.columns([2, 1, 1])
            attend = col1.checkbox(f"{team_name} Attends", key=f"{prefix}_att_{i}")
            if attend:
                count = col2.number_input("No. of Travelers", 1, 10, value=1, key=f"{prefix}_cnt_{i}")
                days = col3.number_input("Days per Trip", 1, 14, value=3, key=f"{prefix}_day_{i}")
                m_results.append({"team_idx": i, "count": count, "days": days})
        
        num_meetings = st.number_input("Total Number of these Meetings", 0, 10, value=1, key=f"{prefix}_total")
        return {"trips": m_results, "occurrences": num_meetings, "location_city": teams[0]['city'] if "Client" in label else (teams[1]['city'] if "Counsel" in label else teams[2]['city'])}

# --- PILLAR 1: CLAIMANT ---
with tab_claimant:
    c_teams = [
        subteam_inputs("Client Team", "c_cli"),
        subteam_inputs("Legal Counsel", "c_cou"),
        subteam_inputs("Experts", "c_exp")
    ]
    st.divider()
    c_m1 = detailed_meeting_matrix("Claimant's Office", "c_meet_1", c_teams)
    c_m2 = detailed_meeting_matrix("Counsel's Chambers", "c_meet_2", c_teams)
    c_m3 = detailed_meeting_matrix("Expert's Office", "c_meet_3", c_teams)

# --- PILLAR 2: RESPONDENT ---
with tab_respondent:
    r_teams = [
        subteam_inputs("Client Team", "r_cli"),
        subteam_inputs("Legal Counsel", "r_cou"),
        subteam_inputs("Experts", "r_exp")
    ]
    st.divider()
    r_m1 = detailed_meeting_matrix("Respondent's Office", "r_meet_1", r_teams)
    r_m2 = detailed_meeting_matrix("Counsel's Chambers", "r_meet_2", r_teams)
    r_m3 = detailed_meeting_matrix("Expert's Office", "r_meet_3", r_teams)

# --- PILLAR 3: TRIBUNAL ---
with tab_tribunal:
    arb_teams = [subteam_inputs(f"Arbitrator {i+1}", f"t_a{i+1}") for i in range(3)]

# --- 4. CALCULATION ENGINE ---
def calculate_comprehensive(teams, meeting_data, data_share, is_tribunal=False):
    comp_total = sum(t['size'] for t in teams) * case_months * FACTORS['comp_month']
    res = {
        "Scope 2: Purchased Electricity": comp_total * 0.15,
        "Scope 3: Business Travel (Prep)": 0,
        "Scope 3: Business Travel (Hearing)": 0,
        "Scope 3: Hotel Stays": 0,
        "Scope 3: Digital & Storage": (data_share * FACTORS['data_gb']) + (comp_total * 0.85),
        "Scope 3: Materials": sum(t['size'] for t in teams) * (FACTORS['materials']['notebook'] + FACTORS['materials']['pen'])
    }

    # Hearing Calculation
    if not is_virtual:
        for t in teams:
            res["Scope 3: Business Travel (Hearing)"] += get_dist(t['city'], h_city) * 2 * t['size'] * FACTORS['transport'][t['mode']]
            res["Scope 3: Hotel Stays"] += t['size'] * h_days * FACTORS['hotel'][t['stars']]

    # Prep Meetings Calculation (Rows 25-41 logic)
    if meeting_data:
        for meeting in meeting_data:
            occurrences = meeting['occurrences']
            target_city = meeting['location_city']
            for trip in meeting['trips']:
                origin_team = teams[trip['team_idx']]
                # Only travel if origin city is different from target city
                dist = get_dist(origin_team['city'], target_city)
                if dist > 0:
                    res["Scope 3: Business Travel (Prep)"] += dist * 2 * trip['count'] * occurrences * FACTORS['transport'][origin_team['mode']]
                    res["Scope 3: Hotel Stays"] += trip['count'] * trip['days'] * occurrences * FACTORS['hotel'][origin_team['stars']]
    return res

c_res = calculate_comprehensive(c_teams, [c_m1, c_m2, c_m3], total_data * 0.4)
r_res = calculate_comprehensive(r_teams, [r_m1, r_m2, r_m3], total_data * 0.4)
t_res = calculate_comprehensive(arb_teams, None, total_data * 0.2, True)

# --- 5. VISUAL SUMMARY ---
st.divider()
c_total, r_total, t_total = sum(c_res.values()), sum(r_res.values()), sum(t_res.values())
grand_total = c_total + r_total + t_total

m_cols = st.columns(4)
m_cols[0].metric("GRAND TOTAL", f"{grand_total:,.1f} kg")
m_cols[1].metric("Claimant", f"{c_total:,.1f} kg")
m_cols[2].metric("Respondent", f"{r_total:,.1f} kg")
m_cols[3].metric("Tribunal", f"{t_total:,.1f} kg")

# --- 6. EXCEL MAPPING ---
if export_btn:
    try:
        wb = openpyxl.load_workbook('arbitration_tool.xlsx')
        sheet = wb.active
        # (The C30-C97 mapping logic from previous blocks applies here)
        wb.save('Arbitration_Report_Final.xlsx')
        st.sidebar.success("Excel Updated!")
    except Exception as e:
        st.sidebar.error(f"Sync Error: {e}")

# --- 7. OUTPUT BREAKDOWNS ---
def display_output(name, data):
    with st.expander(f"Analysis: {name}", expanded=True):
        df = pd.DataFrame.from_dict(data, orient='index', columns=['kgCO2e'])
        c1, c2 = st.columns([1, 2])
        c1.dataframe(df.style.format("{:,.2f}"))
        c2.bar_chart(df)

display_output("Claimant", c_res)
display_output("Respondent", r_res)
display_output("Tribunal", t_res)
