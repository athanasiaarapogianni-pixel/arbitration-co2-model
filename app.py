import streamlit as st
import pandas as pd
import os

# --- DATA LOADING ---
@st.cache_data
def load_excel_data():
    file_path = "carbon_model.xlsx"
    if not os.path.exists(file_path): return None, None
    try:
        # header=5 (Row 6) / index_col=2 (Col C)
        dist_df = pd.read_excel(file_path, sheet_name="Travel Matrix", header=5, index_col=2)
        dist_df = dist_df.dropna(axis=0, how='all').dropna(axis=1, how='all')
        hotel_df = pd.read_excel(file_path, sheet_name="List Selections", usecols="B:H")
        return dist_df, hotel_df
    except Exception as e:
        st.error(f"Excel Loading Error: {e}")
        return None, None

dist_matrix, hotel_lookup = load_excel_data()
ALL_CITIES = sorted([c for c in dist_matrix.index.dropna().unique() if "Unnamed" not in str(c)]) if dist_matrix is not None else []

# --- GLOBAL AUDIT LIST ---
# This will catch every travel calculation for debugging
if "audit_logs" not in st.session_state:
    st.session_state.audit_logs = []

def get_matrix_dist(origin, destination):
    try:
        # Clean the strings to ensure a match
        o, d = str(origin).strip(), str(destination).strip()
        val = dist_matrix.loc[o, d]
        return float(val)
    except Exception:
        return 0.0 # If this returns 0, the Audit Log will catch it

# --- UPDATED CALCULATION ENGINE ---
TRANSPORT = {"Plane (Business)": 0.274, "Plane (Economy)": 0.182, "Rail": 0.035, "Car": 0.151}

def calculate_impact(party_name, teams, meetings, data_share, is_v, h_ct, h_d, case_months):
    num_ppl = sum(t['size'] for t in teams)
    comp_total = num_ppl * case_months * 6.4444
    
    res = {
        "Scope 2: Computer Use": comp_total * 0.15,
        "Scope 2: Printing & Office": num_ppl * 4.5,
        "Scope 3: Travel (Prep)": 0.0,
        "Scope 3: Travel (Hearing)": 0.0,
        "Scope 3: Hotel Stays": 0.0,
        "Scope 3: Digital Storage & Mfg": (data_share * 0.021) + (comp_total * 0.85),
        "Scope 3: Materials": num_ppl * 0.42
    }
    
    # HEARING
    if not is_v and h_ct != "Virtual":
        for t in teams:
            if t['size'] > 0:
                dist = get_matrix_dist(t['city'], h_ct)
                # FORMULA: (Dist * 2) * People * Factor
                travel_calc = (dist * 2) * t['size'] * TRANSPORT[t['mode']]
                res["Scope 3: Travel (Hearing)"] += travel_calc
                
                # Log for debugging
                st.session_state.audit_logs.append({
                    "Party": party_name, "Type": "Hearing", "From": t['city'], "To": h_ct,
                    "Dist": dist, "People": t['size'], "Result": travel_calc
                })

    # PREP MEETINGS
    if meetings:
        for m in meetings:
            for trip in m['trips']:
                t = teams[trip['idx']]
                dist = get_matrix_dist(t['city'], m['loc'])
                if dist > 0:
                    # FORMULA: (Dist * 2) * Qty * Occurrences * Factor
                    prep_travel = (dist * 2) * trip['count'] * m['occ'] * TRANSPORT[t['mode']]
                    res["Scope 3: Travel (Prep)"] += prep_travel
                    
                    st.session_state.audit_logs.append({
                        "Party": party_name, "Type": f"Prep ({m['loc']})", "From": t['city'], "To": m['loc'],
                        "Dist": dist, "People": trip['count'], "Result": prep_travel
                    })
    return res

# --- MAIN APP (Abbreviated for clarity) ---
st.session_state.audit_logs = [] # Clear logs on every run

# ... [Include your Sidebar and Tab Rendering here] ...

# IN THE SUMMARY TAB:
with t_sum:
    st.header("🔍 Debugging: Calculation Audit Log")
    if st.session_state.audit_logs:
        audit_df = pd.DataFrame(st.session_state.audit_logs)
        st.table(audit_df)
    else:
        st.write("No travel calculated yet.")
