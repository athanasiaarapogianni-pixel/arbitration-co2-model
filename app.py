import streamlit as st
import pandas as pd

# --- 1. SETUP & DATA ---
st.set_page_config(page_title="Arbitration CO2 Model", layout="wide")

# We define the "Logic Brain" here so we don't need the Excel file anymore
ASSUMPTIONS = {
    "computer_monthly": 6.4444, # kgCO2e per person
    "email_unit": 0.004,        # kgCO2e per email
    "printing_kwh_page": 0.00000667,
    "scope2_pc": 0.15,          # 15% is Scope 2
    "scope3_pc": 0.85,          # 85% is Scope 3
    "data_gb_factor": 0.021     # kgCO2e per GB
}

# --- 2. CALCULATOR ENGINE ---
def run_model(inputs):
    # Total Team Size
    total_people = (inputs['c_team'] + inputs['c_counsel'] + inputs['c_expert'] + 
                    inputs['r_team'] + inputs['r_counsel'] + inputs['r_expert'] + 3) # +3 Arbitrators
    
    # 1. Computer Use
    total_comp_co2 = total_people * inputs['months'] * ASSUMPTIONS["computer_monthly"]
    
    # 2. Emails
    total_email_co2 = inputs['emails'] * ASSUMPTIONS["email_unit"]
    
    # 3. Printing (Simplified logic from your sheet)
    total_print_co2 = inputs['submissions'] * total_people * 100 * ASSUMPTIONS["printing_kwh_page"]
    
    # 4. Data Storage
    total_data_co2 = inputs['data_gb'] * ASSUMPTIONS["data_gb_factor"]

    # Totals
    scope2 = (total_comp_co2 + total_email_co2 + total_print_co2) * ASSUMPTIONS["scope2_pc"]
    scope3 = (total_comp_co2 + total_email_co2 + total_print_co2) * ASSUMPTIONS["scope3_pc"] + total_data_co2
    
    return {
        "Scope 2": scope2,
        "Scope 3": scope3,
        "Total": scope2 + scope3
    }

# --- 3. USER INTERFACE ---
st.title("⚖️ Arbitration Carbon Impact Model")
st.markdown("Enter your case details below to see the estimated environmental impact.")

with st.expander("📁 Global Case Settings", expanded=True):
    col1, col2, col3 = st.columns(3)
    months = col1.number_input("Duration (Months)", value=24)
    emails = col2.number_input("Total Emails", value=1000)
    data_gb = col3.number_input("Data Generated (GB)", value=10)
    submissions = col1.number_input("Number of Submissions", value=4)
    virtual = col2.radio("Was the hearing virtual?", ["No", "Yes"])

st.subheader("👥 Team Sizes")
c1, c2 = st.columns(2)
with c1:
    st.info("Claimant Side")
    c_team = st.number_input("Claimant Team", value=3)
    c_counsel = st.number_input("Claimant Counsel", value=4)
    c_expert = st.number_input("Claimant Expert", value=2)
with c2:
    st.info("Respondent Side")
    r_team = st.number_input("Respondent Team", value=2)
    r_counsel = st.number_input("Respondent Counsel", value=5)
    r_expert = st.number_input("Respondent Expert", value=3)

# Run Calculation
results = run_model({
    "months": months, "emails": emails, "data_gb": data_gb, 
    "submissions": submissions, "c_team": c_team, "c_counsel": c_counsel,
    "c_expert": c_expert, "r_team": r_team, "r_counsel": r_counsel, "r_expert": r_expert
})

# --- 4. RESULTS DASHBOARD ---
st.divider()
kpi1, kpi2, kpi3 = st.columns(3)

kpi1.metric("Total Impact", f"{results['Total']:,.2f} kgCO2e")
kpi2.metric("Scope 2", f"{results['Scope 2']:,.2f} kgCO2e")
kpi3.metric("Scope 3", f"{results['Scope 3']:,.2f} kgCO2e")

# Visualize the breakdown
st.bar_chart(pd.DataFrame({
    "Category": ["Scope 2 (Direct)", "Scope 3 (Indirect)"],
    "kgCO2e": [results["Scope 2"], results["Scope 3"]]
}).set_index("Category"))