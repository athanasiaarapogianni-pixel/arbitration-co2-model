import streamlit as st
import pandas as pd
import plotly.express as px
import os

# --- 1. SESSION STATE INITIALIZATION ---
if "audit_logs" not in st.session_state:
    st.session_state.audit_logs = []

# --- 2. DATA LOADING ---
@st.cache_data
def load_excel_data():
    file_path = "carbon_model.xlsx"
    if not os.path.exists(file_path):
        return None, None
    try:
        # Matches C7 (down) and D6 (across)
        dist_df = pd.read_excel(file_path, sheet_name="Travel Matrix", header=5, index_col=2)
        dist_df = dist_df.dropna(axis=0, how='all').dropna(axis=1, how='all')
        hotel_df = pd.read_excel(file_path, sheet_name="List Selections", usecols="B:H")
        return dist_df, hotel_df
    except Exception as e:
        st.error(f"Excel Loading Error: {e}")
        return None, None

# Sidebar Refresh
if st.sidebar.button("🔄 Refresh Excel Data"):
    st.cache_data.clear()
    st.rerun()

dist_matrix, hotel_lookup = load_excel_data()
ALL_CITIES = sorted([c for c in dist_matrix.index.dropna().unique() if "Unnamed" not in str(c)]) if dist_matrix is not None else ["London"]

# --- 3. LOOKUP HELPERS ---
def get_matrix_dist(origin, destination):
    try:
        o, d = str(origin).strip(), str(destination).strip()
        val = dist_matrix.loc[o, d]
        return float(val)
    except:
        return 0.0 

def get_hotel_factor(city, stars):
    try:
        row = hotel_lookup[hotel_lookup.iloc[:, 1].str.strip() == str(city).strip()]
        star_col_map = {5: 3, 4: 4, 3: 5, 2: 6} 
        return float(row.iloc[0, star_col_map[stars]])
    except:
        return 21.7 

# --- 4. CALCULATION ENGINE ---
TRANSPORT = {"Plane (Business)": 0.274, "Plane (Economy)": 0.182, "Rail": 0.035, "Car": 0.151}

def calculate_impact(party_name, teams, meetings, data_share, is_v, h_ct, h_d, c_months):
    num_ppl = sum(t['size'] for t in teams)
    comp_total = num_ppl * c_months * 6.4444
    
    res = {
        "Scope 2: Computer Use": comp_total * 0.15,
        "Scope 2: Printing & Office": num_ppl * 4.5,
        "Scope 3: Travel (Prep)": 0.0,
        "Scope 3: Travel (Hearing)": 0.0,
        "Scope 3: Hotel Stays": 0.0,
        "Scope 3: Digital Storage & Mfg": (data_share * 0.021) + (comp_total * 0.85),
        "Scope 3: Materials": num_ppl * 0.42
    }
    
    if not is_v and h_ct != "Virtual":
        for t in teams:
            if t['size'] > 0:
                dist = get_matrix_dist(t['city'], h_ct)
                travel_calc = (dist * 2) * t['size'] * TRANSPORT[t['mode']]
                res["Scope 3: Travel (Hearing)"] += travel_calc
                
                st.session_state.audit_logs.append({
                    "Party": party_name, "Category": "Hearing", "From": t['city'], "To": h_ct,
                    "Dist (1-way)": dist, "Qty": t['size'], "Result (kg)": round(travel_calc, 2)
                })
                res["Scope 3: Hotel Stays"] += t['size'] * h_d * get_hotel_factor(h_ct, t['stars'])
            
    if meetings:
        for m in meetings:
            for trip in m['trips']:
                t = teams[trip['idx']]
                dist = get_matrix_dist(t['city'], m['loc'])
                if dist > 0:
                    prep_travel = (dist * 2) * trip['count'] * m['occ'] * TRANSPORT[t['mode']]
                    res["Scope 3: Travel (Prep)"] += prep_travel
                    
                    st.session_state.audit_logs.append({
                        "Party": party_name, "Category": f"Prep @ {m['loc']}", "From": t['city'], "To": m['loc'],
                        "Dist (1-way)": dist, "Qty": trip['count'], "Result (kg)": round(prep_travel, 2)
                    })
                    res["Scope 3: Hotel Stays"] += trip['count'] * trip['days'] * m['occ'] * get_hotel_factor(m['loc'], t['stars'])
    return res

# --- 5. SIDEBAR & TABS ---
with st.sidebar:
    st.header("⚙️ Global Inputs")
    case_months = st.number_input("Duration (Months)", value=24)
    total_data = st.number_input("Total Data (GB)", value=10)
    st.divider()
    is_v = st.toggle("Virtual Hearing", value=False)
    h_ct = st.selectbox("Hearing City", ALL_CITIES) if not is_v else "Virtual"
    h_d = st.slider("Hearing Days", 1, 21, 5) if not is_v else 0

st.title("⚖️ Professional Arbitration Carbon Model")

# DEFINE TABS HERE TO PREVENT NAMEERROR
t_cl, t_res, t_trib, t_sum = st.tabs(["🔴 Claimant", "🔵 Respondent", "⚖️ Tribunal", "📊 Summary"])

def subteam_ui(label, prefix, default_size=2):
    st.markdown(f"**{label}**")
    c1, c2, c3, c4 = st.columns([1, 1.5, 1.5, 1])
    size = c1.number_input("Size", value=default_size, key=f"{prefix}s", min_value=0)
    city = c2.selectbox("Base City", ALL_CITIES, key=f"{prefix}c")
    mode = c3.selectbox("Travel Mode", list(TRANSPORT.keys()), key=f"{prefix}m")
    star = c4.selectbox("Hotel Stars", [5, 4, 3, 2], index=1, key=f"{prefix}h")
    return {"size": size, "city": city, "mode": mode, "stars": star}

def meet_ui(label, prefix, teams):
    with st.expander(f"📅 Prep Trips to {label}"):
        m_trips = []
        for i, name in enumerate(["Client", "Counsel", "Experts"]):
            col1, col2, col3 = st.columns([2, 1, 1])
            if col1.checkbox(f"{name} travels", key=f"{prefix}a{i}"):
                m_trips.append({"idx": i, "count": col2.number_input("Qty", 1, 20, 1, key=f"{prefix}q{i}"), 
                                "days": col3.number_input("Nights", 1, 30, 2, key=f"{prefix}n{i}")})
        occ = st.number_input("Meetings", 1, 20, 1, key=f"{prefix}o")
        loc = teams[0]['city'] if "Client" in label else (teams[1]['city'] if "Counsel" in label else teams[2]['city'])
        return {"trips": m_trips, "occ": occ, "loc": loc}

# --- 6. RENDER LOGIC ---
st.session_state.audit_logs = [] 

with t_cl:
    c_teams = [subteam_ui("Client Team", "cc"), subteam_ui("Legal Counsel", "cl"), subteam_ui("Experts", "ce")]
    c_meets = [meet_ui("Claimant Office", "cm1", c_teams), meet_ui("Counsel Chambers", "cm2", c_teams), meet_ui("Expert Office", "cm3", c_teams)]
    c_res = calculate_impact("Claimant", c_teams, c_meets, total_data*0.4, is_v, h_ct, h_d, case_months)

with t_res:
    r_teams = [subteam_ui("Client Team", "rc"), subteam_ui("Legal Counsel", "rl"), subteam_ui("Experts", "re")]
    r_meets = [meet_ui("Respondent Office", "rm1", r_teams), meet_ui("Counsel Chambers", "rm2", r_teams), meet_ui("Expert Office", "rm3", r_teams)]
    r_res = calculate_impact("Respondent", r_teams, r_meets, total_data*0.4, is_v, h_ct, h_d, case_months)

with t_trib:
    tr_teams = [subteam_ui(f"Arbitrator {i+1}", f"tr{i}", 1) for i in range(3)]
    tr_res = calculate_impact("Tribunal", tr_teams, None, total_data*0.2, is_v, h_ct, h_d, case_months)

with t_sum:
    grand = sum(c_res.values()) + sum(r_res.values()) + sum(tr_res.values())
    c1, c2, c3 = st.columns(3)
    c1.metric("Grand Total Impact", f"{grand:,.1f} kg")
    c2.metric("Equiv. Cars (Year)", f"{(grand/1.324287002):,.1f}")
    c3.metric("Trees Required", f"{(grand/25):,.1f}")
    
    st.divider()
    st.header("🔍 Calculation Audit Log")
    if st.session_state.audit_logs:
        st.table(pd.DataFrame(st.session_state.audit_logs))
