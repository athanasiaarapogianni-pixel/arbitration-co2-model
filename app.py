import streamlit as st
import pandas as pd
import openpyxl
import plotly.express as px

# --- 1. SETUP & CORE DATA ---
st.set_page_config(page_title="Arbitration CO2 Model", layout="wide")

FACTORS = {
    "comp_month": 6.4444, 
    "hotel": {3: 15.5, 4: 21.7, 5: 35.2}, 
    "data_gb": 0.021,
    "materials": {"notebook": 0.37, "pen": 0.05},
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
    
    st.divider()
    st.subheader("Hearing Settings")
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
        occurrences = st.number_input("Total meetings", 0, 20, value=1, key=f"{prefix}_occ")
        loc_city = teams[0]['city'] if "Client" in label else (teams[1]['city'] if "Counsel" in label else teams[2]['city'])
        return {"trips": m_trips, "occurrences": occurrences, "loc_city": loc_city}

# --- PILLARS ---
with tab_claimant:
    c_teams = [subteam_inputs("Client Team", "c_cli"), subteam_inputs("Legal Counsel", "c_cou"), subteam_inputs("Experts", "c_exp")]
    st.divider()
    c_m_list = [meeting_matrix("Claimant Office", "c_m1", c_teams), meeting_matrix("Counsel Chambers", "c_m2", c_teams), meeting_matrix("Expert Office", "c_m3", c_teams)]

with tab_respondent:
    r_teams = [subteam_inputs("Client Team", "r_cli"), subteam_inputs("Legal Counsel", "r_cou"), subteam_inputs("Experts", "r_exp")]
    st.divider()
    r_m_list = [meeting_matrix("Respondent Office", "r_m1", r_teams), meeting_matrix("Counsel Chambers", "r_m2", r_teams), meeting_matrix("Expert Office", "r_m3", r_teams)]

with tab_tribunal:
    arb_teams = [subteam_inputs(f"Arbitrator {i+1}", f"t_a{i+1}") for i in range(3)]

# --- 4. CALCULATION ENGINE ---
def calculate_output_standard(teams, meetings, data_share, virtual_override=False):
    num_people = sum(t['size'] for t in teams)
    comp_total = num_people * case_months * FACTORS['comp_month']
    res = {
        "Scope 2: Computer Use": comp_total * 0.15,
        "Scope 2: Printing & Office Energy": num_people * 4.5,
        "Scope 3: Business Travel (Prep)": 0.0,
        "Scope 3: Business Travel (Hearing)": 0.0,
        "Scope 3: Hotel Stays": 0.0,
        "Scope 3: Digital Storage & Manufacturing": (data_share * FACTORS['data_gb']) + (comp_total * 0.85),
        "Scope 3: Materials & Stationery": num_people * (FACTORS['materials']['notebook'] + FACTORS['materials']['pen'])
    }
    
    # Hearing (Only if NOT virtual)
    if not virtual_override and not is_virtual:
        for t in teams:
            dist = get_dist(t['city'], h_city)
            res["Scope 3: Business Travel (Hearing)"] += dist * 2 * t['size'] * FACTORS['transport'][t['mode']]
            res["Scope 3: Hotel Stays"] += t['size'] * h_days * FACTORS['hotel'][t['stars']]
            
    # Prep Meetings
    if meetings:
        for m in meetings:
            for trip in m['trips']:
                origin_team = teams[trip['team_idx']]
                dist = get_dist(origin_team['city'], m['loc_city'])
                if dist > 0:
                    res["Scope 3: Business Travel (Prep)"] += dist * 2 * trip['count'] * m['occurrences'] * FACTORS['transport'][origin_team['mode']]
                    res["Scope 3: Hotel Stays"] += trip['count'] * trip['days'] * m['occurrences'] * FACTORS['hotel'][origin_team['stars']]
    return res

# Calculate actual results
c_res = calculate_output_standard(c_teams, c_m_list, total_data * 0.4)
r_res = calculate_output_standard(r_teams, r_m_list, total_data * 0.4)
t_res = calculate_output_standard(arb_teams, None, total_data * 0.2)

# Calculate "What-if" Physical (to show savings if virtual is on)
if is_virtual:
    c_phys = calculate_output_standard(c_teams, c_m_list, total_data * 0.4, virtual_override=False)
    r_phys = calculate_output_standard(r_teams, r_m_list, total_data * 0.4, virtual_override=False)
    t_phys = calculate_output_standard(arb_teams, None, total_data * 0.2, virtual_override=False)
    savings = (sum(c_phys.values()) + sum(r_phys.values()) + sum(t_phys.values())) - (sum(c_res.values()) + sum(r_res.values()) + sum(t_res.values()))
else:
    savings = 0

# --- 5. SUMMARY TAB ---
with tab_summary:
    st.header("🌳 Case Environmental Impact Summary")
    c_total, r_total, t_total = sum(c_res.values()), sum(r_res.values()), sum(t_res.values())
    grand_total = c_total + r_total + t_total
    
    num_cars_year = grand_total / 1.324287002
    trees_needed = grand_total / 25
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Grand Total Impact", f"{grand_total:,.1f} kgCO2e")
    m2.metric("Equiv. Cars (per year)", f"{num_cars_year:,.1f}")
    m3.metric("Trees Required", f"{trees_needed:,.1f}")

    if is_virtual and savings > 0:
        st.success(f"🌱 **Virtual Hearing Benefit:** You are avoiding **{savings:,.1f} kgCO2e** by conducting this hearing virtually.")
    
    st.divider()
    
    combined_list = []
    for party, data in [("Claimant", c_res), ("Respondent", r_res), ("Tribunal", t_res)]:
        for cat, val in data.items():
            combined_list.append({"Party": party, "Category": cat, "kgCO2e": val})
    
    df_plot = pd.DataFrame(combined_list)
    fig = px.bar(df_plot, x="Party", y="kgCO2e", color="Category", barmode="stack", title="Impact Breakdown")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📄 Case Report Preview")
    report_text = f"""
    ARBITRATION CARBON FOOTPRINT REPORT
    ----------------------------------
    Duration: {case_months} Months
    Hearing Status: {'VIRTUAL' if is_virtual else 'PHYSICAL (' + h_city + ')'}
    
    TOTAL EMISSIONS: {grand_total:,.2f} kgCO2e
    
    BREAKDOWN:
    - Claimant: {c_total:,.2f} kg
    - Respondent: {r_total:,.2f} kg
    - Tribunal: {t_total:,.2f} kg
    
    ENVIRONMENTAL EQUIVALENCY:
    - This arbitration has the same impact as {num_cars_year:,.2f} average cars on the road for one year.
    - {trees_needed:,.2f} mature trees would be required to offset this case.
    """
    st.code(report_text)

# --- 6. EXCEL SYNC & INDIVIDUALS ---
# [Excel logic remains same]
if export_btn:
    try:
        wb = openpyxl.load_workbook('arbitration_tool.xlsx')
        sheet = wb.active
        sheet['C31'] = c_res["Scope 2: Computer Use"] + c_res["Scope 2: Printing & Office Energy"]
        wb.save('Arbitration_Report_Final.xlsx')
        st.sidebar.success("Excel Updated!")
    except Exception as e: st.sidebar.error(f"Error: {e}")

def display_breakdown(name, data):
    with st.expander(f"Analysis: {name}"):
        st.dataframe(pd.DataFrame.from_dict(data, orient='index', columns=['kgCO2e']).style.format("{:,.2f}"), use_container_width=True)

display_breakdown("Claimant Side", c_res)
display_breakdown("Respondent Side", r_res)
display_breakdown("Tribunal Side", t_res)
