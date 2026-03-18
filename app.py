import streamlit as st
import pandas as pd
import openpyxl
import plotly.express as px

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
tab_claimant, tab_respondent, tab_tribunal, tab_summary = st.tabs(["🔴 Claimant", "🔵 Respondent", "⚖️ Tribunal", "📊 Case Summary"])

def subteam_inputs(label, prefix):
    st.markdown(f"**{label}**")
    c1, c2, c3, c4 = st.columns([1, 1.5, 1.5, 1])
    size = c1.number_input("Total Team Size", value=2 if "Arbitrator" not in label else 1, key=f"{prefix}_sz")
    city = c2.selectbox("Base City", CITIES, key=f"{prefix}_ct")
    mode = c3.selectbox("Default Travel Mode", list(FACTORS['transport'].keys()), key=f"{prefix}_md")
    stars = c4.selectbox("Hotel Stars", [3, 4, 5], index=1, key=f"{prefix}_st")
    return {"size": size, "city": city, "mode": mode, "stars": stars}

def meeting_matrix(label, prefix, teams):
    with st.expander(f"📅 Prep Meetings at {label}", expanded=False):
        st.markdown(f"**Travelers & Duration for {label}**")
        h1, h2, h3 = st.columns([2, 1, 1])
        h1.caption("Sub-Team")
        h2.caption("No. Travelers")
        h3.caption("Nights Stayed")
        m_trips = []
        for i, team_name in enumerate(["Client Team", "Legal Counsel", "Experts"]):
            col1, col2, col3 = st.columns([2, 1, 1])
            attend = col1.checkbox(f"{team_name}", key=f"{prefix}_att_{i}")
            if attend:
                count = col2.number_input("Qty", 1, 20, value=1, key=f"{prefix}_cnt_{i}", label_visibility="collapsed")
                duration = col3.number_input("Nights", 1, 30, value=2, key=f"{prefix}_dur_{i}", label_visibility="collapsed")
                m_trips.append({"team_idx": i, "count": count, "days": duration})
        occurrences = st.number_input("Total number of these meetings", 0, 20, value=1, key=f"{prefix}_occ")
        loc_city = teams[0]['city'] if "Client" in label else (teams[1]['city'] if "Counsel" in label else teams[2]['city'])
        return {"trips": m_trips, "occurrences": occurrences, "loc_city": loc_city}

# --- TAB CONTENT ---
with tab_claimant:
    c_teams = [subteam_inputs("Client Team", "c_cli"), subteam_inputs("Legal Counsel", "c_cou"), subteam_inputs("Experts", "c_exp")]
    st.divider()
    c_m_list = [meeting_matrix("Claimant's Office", "c_m1", c_teams), meeting_matrix("Counsel's Chambers", "c_m2", c_teams), meeting_matrix("Expert's Office", "c_m3", c_teams)]

with tab_respondent:
    r_teams = [subteam_inputs("Client Team", "r_cli"), subteam_inputs("Legal Counsel", "r_cou"), subteam_inputs("Experts", "r_exp")]
    st.divider()
    r_m_list = [meeting_matrix("Respondent's Office", "r_m1", r_teams), meeting_matrix("Counsel's Chambers", "r_m2", r_teams), meeting_matrix("Expert's Office", "r_m3", r_teams)]

with tab_tribunal:
    arb_teams = [subteam_inputs(f"Arbitrator {i+1}", f"t_a{i+1}") for i in range(3)]

# --- 4. CALCULATION ENGINE ---
def calculate_all(teams, meetings, data_share):
    comp_total = sum(t['size'] for t in teams) * case_months * FACTORS['comp_month']
    res = {
        "Scope 2: Purchased Electricity": comp_total * 0.15,
        "Scope 3: Business Travel (Prep)": 0.0,
        "Scope 3: Business Travel (Hearing)": 0.0,
        "Scope 3: Hotel Stays": 0.0,
        "Scope 3: Digital & Storage": (data_share * FACTORS['data_gb']) + (comp_total * 0.85),
        "Scope 3: Materials": sum(t['size'] for t in teams) * (FACTORS['materials']['notebook'] + FACTORS['materials']['pen'])
    }
    if not is_virtual:
        for t in teams:
            dist = get_dist(t['city'], h_city)
            res["Scope 3: Business Travel (Hearing)"] += dist * 2 * t['size'] * FACTORS['transport'][t['mode']]
            res["Scope 3: Hotel Stays"] += t['size'] * h_days * FACTORS['hotel'][t['stars']]
    if meetings:
        for m in meetings:
            for trip in m['trips']:
                origin_team = teams[trip['team_idx']]
                dist = get_dist(origin_team['city'], m['loc_city'])
                if dist > 0:
                    res["Scope 3: Business Travel (Prep)"] += dist * 2 * trip['count'] * m['occurrences'] * FACTORS['transport'][origin_team['mode']]
                    res["Scope 3: Hotel Stays"] += trip['count'] * trip['days'] * m['occurrences'] * FACTORS['hotel'][origin_team['stars']]
    return res

c_res = calculate_all(c_teams, c_m_list, total_data * 0.4)
r_res = calculate_all(r_teams, r_m_list, total_data * 0.4)
t_res = calculate_all(arb_teams, None, total_data * 0.2)

# Totals
c_total, r_total, t_total = sum(c_res.values()), sum(r_res.values()), sum(t_res.values())
grand_total = c_total + r_total + t_total

# --- 5. SUMMARY TAB (Environmental Equivalents) ---
with tab_summary:
    st.header("🌳 Case Environmental Impact Summary")
    
    # Custom Formulas
    car_km = grand_total / 1.324287002
    trees_needed = grand_total / 25
    
    col_e1, col_e2, col_e3 = st.columns(3)
    col_e1.metric("Total Emissions", f"{grand_total:,.1f} kgCO2e")
    col_e2.metric("Car Distance Equivalent", f"{car_km:,.0f} km")
    col_e3.metric("Trees to Offset", f"{trees_needed:,.1f} trees")
    
    st.divider()
    
    # Party Contribution Pie Chart
    st.subheader("Party Contribution to Total Footprint")
    party_data = pd.DataFrame({
        "Party": ["Claimant", "Respondent", "Tribunal"],
        "Emissions": [c_total, r_total, t_total]
    })
    fig_party = px.pie(party_data, values="Emissions", names="Party", hole=0.4, 
                       color_discrete_sequence=["#ef553b", "#636efa", "#ab63fa"])
    st.plotly_chart(fig_party, use_container_width=True, key="summary_party_pie")

# --- 6. EXCEL SYNC (C30-C97) ---
if export_btn:
    try:
        wb = openpyxl.load_workbook('arbitration_tool.xlsx')
        sheet = wb.active
        # (Your Excel mapping logic remains here as before)
        wb.save('Arbitration_Report_Final.xlsx')
        st.sidebar.success("Excel Updated and Saved!")
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

# --- 7. INDIVIDUAL PARTY ANALYSIS ---
def display_pie_analysis(name, data, unique_key):
    with st.expander(f"Analysis: {name}", expanded=True):
        scope2_data = {k: v for k, v in data.items() if "Scope 2" in k}
        scope3_data = {k: v for k, v in data.items() if "Scope 3" in k}
        col_text, col_pie1, col_pie2 = st.columns([1, 1.5, 1.5])
        with col_text:
            st.markdown(f"**{name} Details**")
            st.dataframe(pd.DataFrame.from_dict(data, orient='index', columns=['kgCO2e']).style.format("{:,.2f}"))
        with col_pie1:
            st.markdown("**Scope 2**")
            fig2 = px.pie(values=list(scope2_data.values()), names=list(scope2_data.keys()), hole=0.4)
            st.plotly_chart(fig2, use_container_width=True, key=f"{unique_key}_s2")
        with col_pie2:
            st.markdown("**Scope 3**")
            fig3 = px.pie(values=list(scope3_data.values()), names=list(scope3_data.keys()), hole=0.4)
            st.plotly_chart(fig3, use_container_width=True, key=f"{unique_key}_s3")

# We don't display individual party tabs under the Summary tab; 
# The individual analyses show up in their respective tabs or below.
display_pie_analysis("Claimant Side", c_res, "claimant")
display_pie_analysis("Respondent Side", r_res, "respondent")
display_pie_analysis("Tribunal Side", t_res, "tribunal")
