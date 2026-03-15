import streamlit as st
import pandas as pd

# --- 1. DATA & CONSTANTS (Translated from your "Assumptions" & "List Selections" sheets) ---
EMISSION_FACTORS = {
    "Computer_Monthly_per_person": 6.44,  # kgCO2e
    "Email_per_unit": 0.004,             # kgCO2e
    "Data_Storage_per_GB": 0.021,        # kgCO2e (estimated from your sheets)
    "Printing_kWh_per_page": 0.00000667,
    "WTT_UK_Factor": 0.459,
}

TRAVEL_FACTORS = {
    "Plane (Business)": 0.274, # kgCO2e/km
    "Plane (Economy)": 0.182,
    "Rail": 0.035,
    "Car (non-electric)": 0.171,
    "Car (electric)": 0.054
}

# Simplified Hotel Factors (kgCO2e per night) - You can expand this list
HOTEL_FACTORS = {
    "Germany": {3: 15.5, 4: 21.7, 5: 35.2},
    "UK": {3: 12.4, 4: 18.2, 5: 28.5},
    "France": {3: 10.1, 4: 14.5, 5: 22.0},
    "Italy": {3: 14.2, 4: 20.1, 5: 31.4},
    "Spain": {3: 13.8, 4: 19.5, 5: 30.1},
    "Poland": {3: 25.0, 4: 35.0, 5: 55.0}, # Higher due to grid
}

# --- 2. THE CALCULATION ENGINE ---
def calculate_emissions(inputs):
    results = {"Scope 2": 0, "Scope 3": 0}
    
    # A. Computer Use (Months * Team Size * Factor)
    comp_total = inputs['duration_months'] * inputs['total_team_size'] * EMISSION_FACTORS["Computer_Monthly_per_person"]
    results["Scope 2"] += comp_total * 0.15
    results["Scope 3"] += comp_total * 0.85
    
    # B. Emails
    email_impact = inputs['num_emails'] * EMISSION_FACTORS["Email_per_unit"]
    results["Scope 2"] += email_impact
    
    # C. Travel (Very simplified distance lookup for demo)
    # In a full app, we would use your distance matrix
    dist_estimate = 800 # Default km per trip
    for person in inputs['travelers']:
        km = dist_estimate * 2 # Round trip
        factor = TRAVEL_FACTORS.get(person['mode'], 0.182)
        results["Scope 3"] += km * factor * person['count']

    # D. Hotel Stays
    for stay in inputs['stays']:
        country_data = HOTEL_FACTORS.get(stay['country'], HOTEL_FACTORS["UK"])
        factor = country_data.get(stay['stars'], 20.0)
        results["Scope 3"] += factor * stay['nights'] * stay['people']

    results["Total"] = results["Scope 2"] + results["Scope 3"]
    return results

# --- 3. STREAMLIT INTERFACE ---
st.set_page_config(page_title="Arbitration Carbon Impact Tool", layout="wide")
st.title("🌱 Arbitration CO2 Impact Calculator")
st.markdown("This tool calculates the carbon footprint of legal proceedings based on your model.")

with st.sidebar:
    st.header("Global Case Inputs")
    duration = st.slider("Duration of Arbitration (Months)", 1, 48, 24)
    submissions = st.number_input("Number of Submissions", value=4)
    emails = st.number_input("Estimated Emails", value=1000)
    hearing_days = st.slider("Hearing Duration (Days)", 1, 20, 5)
    is_virtual = st.checkbox("Is the Hearing Virtual?", value=False)

# Main Dashboard
col1, col2 = st.columns(2)

with col1:
    st.subheader("Team Sizes")
    claimant_team = st.number_input("Claimant Team Size", 1, 50, 3)
    respondent_team = st.number_input("Respondent Team Size", 1, 50, 3)
    experts = st.number_input("Experts Total", 0, 20, 4)
    
with col2:
    st.subheader("Travel & Lodging")
    travel_mode = st.selectbox("Primary Travel Mode", list(TRAVEL_FACTORS.keys()))
    hotel_stars = st.select_slider("Hotel Star Rating", options=[3, 4, 5], value=4)

# Run Calculation
input_data = {
    "duration_months": duration,
    "total_team_size": claimant_team + respondent_team + experts + 3, # +3 for Arbitrators
    "num_emails": emails,
    "travelers": [
        {"mode": travel_mode, "count": claimant_team + respondent_team + experts}
    ],
    "stays": [
        {"country": "UK", "stars": hotel_stars, "nights": hearing_days, "people": claimant_team + respondent_team + experts}
    ]
}

final_results = calculate_emissions(input_data)

# --- 4. DISPLAY RESULTS ---
st.divider()
c1, c2, c3 = st.columns(3)
c1.metric("Total Emissions", f"{final_results['Total']:,.1f} kgCO2e")
c2.metric("Scope 2 (Electricity)", f"{final_results['Scope 2']:,.1f} kgCO2e")
c3.metric("Scope 3 (Travel/Value Chain)", f"{final_results['Scope 3']:,.1f} kgCO2e")

st.info("The calculations above are based on the methodology and emission factors defined in your original Excel model.")