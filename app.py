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
    "printing_page": 0.005,
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
    return 850 # Placeholder average

# --- 2. USER INTERFACE ---
st.title("⚖️ Professional Arbitration Carbon Impact Model")

with st.sidebar:
    st.header("🌍 Global Case Parameters")
    case_months = st.number_input("Arbitration Duration (Months)", value=24)
    is_virtual = st.toggle("Virtual Hearing", value=False)
    
    if not is_virtual:
        h_city = st.selectbox("Hearing City", CITIES, index=5)
        h_days = st.slider("Hearing Duration (Days)", 1, 21, 5)
    else:
        h_city, h_days = "Virtual", 0

tab_claimant, tab_respondent, tab_tribunal = st.tabs(["🔴 Claimant", "🔵 Respondent", "⚖️ Tribunal"])

def subteam_inputs(label, prefix):
    st.markdown(f"**{label}**")
    c1, c2, c3, c4 = st.columns([1, 1.5, 1.5, 1])
    size = c1.number_input("Size", value=2, key=f"{prefix}_sz", min_value=0)
    city = c2.selectbox("Base City", CITIES, key=f"{prefix}_ct")
    mode = c3.selectbox("Travel Mode", list(FACTORS['transport'].keys()), key=f"{prefix}_md")
    stars = c4.selectbox("Hotel", [3, 4, 5], index=1, key=f"{prefix}_st")
    return {"size": size, "city": city, "mode": mode, "stars": stars}

# --- PILLAR 1: CLAIMANT ---
with tab_claimant:
    st.subheader("Team Composition")
    c_cli = subteam_inputs("Client Team", "c_cli")
    c_cou = subteam_inputs("Legal Counsel", "c_cou")
    c_exp = subteam_inputs("Experts", "c_exp")
    
    st.divider()
    st.subheader("Digital Activity (Scope 3)")
    col1, col2, col3 = st.columns(3)
    c_emails = col1.number_input("Emails (Total)", value=5000, key="c_emails")
    c_printing = col2.number_input("Pages Printed", value=1000, key="c_print")
    c_data = col3.number_input("Data Share (GB)", value=5, key="c_data")

# --- PILLAR 2 & 3 (Respondent/Tribunal placeholders as per your code) ---
# [Keep your existing UI code for Respondent and Tribunal tabs here]

# --- 3. CALCULATION & EXCEL MAPPING ---
def run_calculations():
    # A. Calculate Digital Emissions (Scope 2 & 3)
    # Mapping to C30 (Email), C31 (Computer), C32 (Data)
    email_emissions = c_emails * FACTORS['email_std']
    comp_emissions = (c_cli['size'] + c_cou['size'] + c_exp['size']) * case_months * FACTORS['comp_month']
    data_emissions = c_data * FACTORS['data_gb']

    # B. Calculate Travel (Claimant Site Visits)
    # We create a list for the 3 sets (Client, Counsel, Expert locations)
    # Target: C40-C42, C44-C46, C48-C50
    claimant_site_trips = []
    teams = [c_cli, c_cou, c_exp]
    for i, t in enumerate(teams):
        # Calculation for travel/stay at this specific sub-team's location
        # This is the logic for C40-C42, C44-C46, etc.
        trip_travel = get_dist(t['city'], "Meeting Location") * 2 * t['size'] * FACTORS['transport'][t['mode']]
        trip_hotel = t['size'] * 3 * FACTORS['hotel'][t['stars']] # Assumes 3 days avg
        claimant_site_trips.append({"travel": trip_travel, "hotel": trip_hotel, "misc": 5.0})

    # C. Calculate Hearing Emissions (C52-C55)
    h_travel = 0
    h_hotel = 0
    if not is_virtual:
        for t in teams:
            h_travel += get_dist(t['city'], h_city) * 2 * t['size'] * FACTORS['transport'][t['mode']]
            h_hotel += t['size'] * h_days * FACTORS['hotel'][t['stars']]

    # D. WRITE TO EXCEL
    try:
        wb = openpyxl.load_workbook('arbitration_tool.xlsx')
        sheet = wb.active

        # Scope 3 Digital
        sheet['C30'] = email_emissions
        sheet['C31'] = comp_emissions
        sheet['C32'] = data_emissions

        # Claimant Side Site Travels
        # Set 1 (C40-C42)
        sheet['C40'] = claimant_site_trips[0]['travel']
        sheet['C41'] = claimant_site_trips[0]['hotel']
        sheet['C42'] = claimant_site_trips[0]['misc']

        # Set 2 (C44-C46)
        sheet['C44'] = claimant_site_trips[1]['travel']
        sheet['C45'] = claimant_site_trips[1]['hotel']
        sheet['C46'] = claimant_site_trips[1]['misc']

        # Set 3 (C48-C50)
        sheet['C48'] = claimant_site_trips[2]['travel']
        sheet['C49'] = claimant_site_trips[2]['hotel']
        sheet['C50'] = claimant_site_trips[2]['misc']

        # Hearing Location (C52-C55)
        sheet['C52'] = h_travel
        sheet['C53'] = h_hotel
        sheet['C54'] = 10.0 # Local Transport Placeholder
        sheet['C55'] = 25.0 # Meals/Misc Placeholder

        wb.save('Arbitration_Model_Results.xlsx')
        st.success("Excel updated and saved as 'Arbitration_Model_Results.xlsx'")
    except FileNotFoundError:
        st.error("Template 'arbitration_tool.xlsx' not found.")

if st.button("Update Excel Report"):
    run_calculations()
