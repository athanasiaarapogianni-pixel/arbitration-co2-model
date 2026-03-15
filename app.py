import streamlit as st
import pandas as pd

# Basic Page Setup
st.set_page_config(page_title="Arbitration CO2 Estimator", layout="wide")

st.title("⚖️ Arbitration Carbon Impact Model")

# Load the Excel Model
@st.cache_data
def load_excel():
    # This reads your specific Excel file
    return pd.ExcelFile("Carbon_model.xlsx")

excel = load_excel()

# SIDEBAR INPUTS
with st.sidebar:
    st.header("User Inputs")
    # We can recreate your exact "User Inputs" tab here
    hearing_city = st.selectbox("Hearing Location", ["Paris", "London", "New York", "Singapore"])
    c_team = st.number_input("Claimant Team Size", value=3)
    r_team = st.number_input("Respondent Team Size", value=3)
    duration = st.number_input("Duration (Months)", value=24)

# CALCULATIONS (Pulling from your 'Assumptions' tab)
# Note: In a full version, we'd use 'pd.read_excel(excel, "Assumptions")' 
# to pull the exact math. Here is a simplified example:
scope2_factor = 6.44  # This matches your 'Computer Use' monthly assumption
total_scope2 = (c_team + r_team) * duration * scope2_factor

# DISPLAY RESULTS
st.header("Estimated Emissions")
col1, col2 = st.columns(2)
col1.metric("Total Scope 2", f"{round(total_scope2, 2)} kgCO2e")
col2.metric("Equivalent Trees", f"{round(total_scope2 / 25, 1)} Trees")

st.write("---")
st.info("This tool is powered by the data in your 'Carbon Impact Model' Excel file.")
