import streamlit as st
import pandas as pd
import openpyxl

# --- 1. SETUP & CORE DATA ---
st.set_page_config(page_title="Arbitration CO2 Model", layout="wide")

FACTORS = {
    "comp_month": 6.4444, # kgCO2e per person per month
    "email_std": 0.004,
    "hotel": {3: 15.5, 4: 21.7, 5: 35.2}, # kgCO2e per night
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
    """Placeholder for distance logic - ideally replaced with a distance matrix"""
    if origin == destination: return 0
    return 850 

# --- 2. SIDEBAR CONFIGURATION ---
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
    st.info("Ensure all tabs are filled before syncing with Excel.")
    export_btn = st.button("💾 Sync to Excel (C30-C97)")

# --- 3. UI TABS ---
st.title("⚖️ Professional Arbitration Carbon Impact Model")
tab_claimant, tab_respondent, tab_tribunal = st.tabs(["🔴 Claimant", "🔵 Respondent", "⚖️ Tribunal"])

def subteam_inputs(label, prefix):
    st.markdown(f"**{label}**")
    c1, c2, c3, c4 = st.columns([1, 1.5, 1.5, 1])
    size = c1.number_input("Total Team Size", value=2 if "Arbitrator" not in label else 1, key=f"{prefix}_sz")
    city = c2.selectbox("Base City", CITIES, key=f"{prefix}_ct")
    mode = c3.selectbox("Default Travel Mode", list(FACTORS['transport'].keys()), key=f"{prefix}_md")
    stars = c4.selectbox("Hotel Stars", [3, 4, 5], index=1, key=f"{prefix}_st")
    return {"size": size, "city": city, "mode": mode, "stars": stars}

def meeting_matrix_with_days(label, prefix, teams):
    with st.expander(f"📅 Prep Meetings at {label}", expanded=False):
        st.write("Define traveler details for this location:")
        m_trips = []
        for i, team_name in enumerate(["Client Team", "Legal Counsel", "Experts"]):
            col1, col2, col3 = st.columns([2, 1, 1])
            attend = col1.checkbox(f"{team_name} travels here", key=f"{prefix}_att_{i}")
            if attend:
                count = col2.number_input("No. of Travelers", 1, 20, value=1, key=f"{prefix}_cnt_{i}")
                days = col3.number_input("Nights Stayed", 1, 30, value=2, key=f"{prefix}_day_{i}")
                m_trips.append({"team_idx": i, "count": count, "days": days})
        
        occurrences = st.number_input("Number of Meetings", 0, 20, value=1, key=f"{prefix}_occ")
        # Determine location city based on office ownership
        loc_city = teams[0]['city'] if "Client" in label else (teams[1]['city'] if "Counsel" in label else teams[2]['city'])
        return {"trips": m_trips, "occurrences": occurrences, "loc_city": loc_city}

# --- TAB LOGIC ---
with tab_claimant:
    c_teams = [subteam_inputs("Client Team", "c_cli"), subteam_inputs("Legal Counsel", "c_cou"), subteam_inputs("Experts", "c_exp")]
    st.divider()
    c_m = [meeting_matrix_with_days("Claimant Office", "c_m1", c_teams), 
           meeting_matrix_with_days("Counsel Chambers", "c_m2", c_teams), 
           meeting_matrix_with_days("Expert Office", "c_m3", c_teams)]

with tab_respondent:
    r_teams = [subteam_inputs("Client Team", "r_cli"), subteam_inputs("Legal Counsel", "r_cou"), subteam_inputs("Experts", "r_exp")]
    st.divider()
    r_m = [meeting_matrix_with_days("Respondent Office", "r_m1", r_teams), 
           meeting_matrix_with_days("Counsel Chambers", "r_m2", r_teams), 
           meeting_matrix_with_days("Expert Office", "r_m3", r_teams)]

with tab_tribunal:
    arb_teams = [subteam_inputs(f"Arbitrator {i+1}", f"t_a{i+1}") for i in range(3)]

# --- 4. CALCULATION ENGINE ---
def calculate_all(teams, meetings, data_share):
    comp_total = sum(t['size'] for t in teams) * case_months * FACTORS['comp_month']
    res = {
        "Scope 2: Purchased Electricity": comp_total * 0.15,
        "Scope 3: Business Travel (Prep)": 0,
        "Scope 3: Business Travel (Hearing)": 0,
        "Scope 3: Hotel Stays": 0,
        "Scope 3: Digital & Storage": (data_share * FACTORS['data_gb']) + (comp_total * 0.85),
        "Scope 3: Materials": sum(t['size'] for t in teams) * (FACTORS['materials']['notebook'] + FACTORS['materials']['pen'])
    }

    # 1. Hearing Travel & Stays
    if not is_virtual:
        for t in teams:
            dist = get_dist(t['city'], h_city)
            res["Scope 3: Business Travel (Hearing)"] += dist * 2 * t['size'] * FACTORS['transport'][t['mode']]
            res["Scope 3: Hotel Stays"] += t['size'] * h_days * FACTORS['hotel'][t['stars']]

    # 2. Prep Meetings (Rows 25-41 Logic)
    if meetings:
        for m in meetings:
            for trip in m['trips']:
                origin_team = teams[trip['team_idx']]
                dist = get_dist(origin_team['city'], m['loc_city'])
                if dist > 0:
                    res["Scope 3: Business Travel (Prep)"] += dist * 2 * trip['count'] * m['occurrences'] * FACTORS['transport'][origin_team['mode']]
                    res["Scope 3: Hotel Stays"] += trip['count'] * trip['days'] * m['occurrences'] * FACTORS['hotel'][origin_team['stars']]
    return res

c_res = calculate_all(c_teams, c_m, total_data * 0.4)
r_res = calculate_all(r_teams, r_m, total_data * 0.4)
t_res = calculate_all(arb_teams, None, total_data * 0.2)

# --- 5. DASHBOARD SUMMARY ---
st.divider()
c_total, r_total, t_total = sum(c_res.values()), sum(r_res.values()), sum(t_res.values())
grand_total = c_total + r_total + t_total

m1, m2, m3, m4 = st.columns(4)
m1.metric("GRAND TOTAL IMPACT", f"{grand_total:,.1f} kg")
m2.metric("Claimant", f"{c_total:,.1f} kg")
m3.metric("Respondent", f"{r_total:,.1f} kg")
m4.metric("Tribunal", f"{t_total:,.1f} kg")

# --- 6. EXCEL EXPORT (C30-C97) ---
if export_btn:
    try:
        wb = openpyxl.load_workbook('arbitration_tool.xlsx')
        sheet = wb.active

        # Mapping Scope 2/3 Digital
        sheet['C31'] = c_res["Scope 2: Purchased Electricity"]
        sheet['C32'] = total_data * FACTORS['data_gb']

        # Claimant Side (C40-C55)
        sheet['C40'], sheet['C41'] = c_res["Scope 3: Business Travel (Prep)"]*0.33, c_res["Scope 3: Hotel Stays"]*0.33
        sheet['C44'], sheet['C45'] = c_res["Scope 3: Business Travel (Prep)"]*0.33, c_res["Scope 3: Hotel Stays"]*0.33
        sheet['C48'], sheet['C49'] = c_res["Scope 3: Business Travel (Prep)"]*0.34, c_res["Scope 3: Hotel Stays"]*0.34
        if not is_virtual:
            sheet['C52'] = sum(get_dist(t['city'], h_city) * 2 * t['size'] * FACTORS['transport'][t['mode']] for t in c_teams)
            sheet['C53'] = sum(t['size'] * h_days * FACTORS['hotel'][t['stars']] for t in c_teams)

        # Respondent Side (C70-C85)
        sheet['C70'], sheet['C71'] = r_res["Scope 3: Business Travel (Prep)"]*0.33, r_res["Scope 3: Hotel Stays"]*0.33
        sheet['C74'], sheet['C75'] = r_res["Scope 3: Business Travel (Prep)"]*0.33, r_res["Scope 3: Hotel Stays"]*0.33
        sheet['C78'], sheet['C79'] = r_res["Scope 3: Business Travel (Prep)"]*0.34, r_res["Scope 3: Hotel Stays"]*0.34
        if not is_virtual:
            sheet['C82'] = sum(get_dist(t['city'], h_city) * 2 * t['size'] * FACTORS['transport'][t['mode']] for t in r_teams)
            sheet['C83'] = sum(t['size'] * h_days * FACTORS['hotel'][t['stars']] for t in r_teams)

        # Tribunal Side (C91-C97)
        if not is_virtual:
            sheet['C91'] = get_dist(arb_teams[0]['city'], h_city) * 2 * arb_teams[0]['size'] * FACTORS['transport'][arb_teams[0]['mode']]
            sheet['C92'] = get_dist(arb_teams[1]['city'], h_city) * 2 * arb_teams[1]['size'] * FACTORS['transport'][arb_teams[1]['mode']]
            sheet['C93'] = get_dist(arb_teams[2]['city'], h_city) * 2 * arb_teams[2]['size'] * FACTORS['transport'][arb_teams[2]['mode']]
            sheet['C95'] = arb_teams[0]['size'] * h_days * FACTORS['hotel'][arb_teams[0]['stars']]
            sheet['C96'] = arb_teams[1]['size'] * h_days * FACTORS['hotel'][arb_teams[1]['stars']]
            sheet['C97'] = arb_teams[2]['size'] * h_days * FACTORS['hotel'][arb_teams[2]['stars']]

        wb.save('Arbitration_Report_Final.xlsx')
        st.sidebar.success("Excel Updated and Saved!")
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

# --- 7. DETAILED BREAKDOWNS ---
def display_analysis(name, data):
    with st.expander(f"Analysis: {name}", expanded=True):
        df = pd.DataFrame.from_dict(data, orient='index', columns=['kgCO2e'])
        col_t, col_c = st.columns([1, 2])
        col_t.dataframe(df.style.format("{:,.2f}"))
        col_c.bar_chart(df)

display_analysis("Claimant Side", c_res)
display_analysis("Respondent Side", r_res)
display_analysis("Tribunal Side", t_res)
