import streamlit as st
import pandas as pd
import os

# --- 1. DATA LOADING & STRING CLEANING ---
@st.cache_data
def load_excel_data():
    file_path = "carbon_model.xlsx"
    if not os.path.exists(file_path): return None, None
    try:
        # Load Matrix (C7 down / D6 across)
        df = pd.read_excel(file_path, sheet_name="Travel Matrix", header=5, index_col=2)
        df = df.dropna(axis=0, how='all').dropna(axis=1, how='all')
        
        # CLEANING: Force all index and column names to be clean strings for matching
        df.index = df.index.astype(str).str.strip().str.title()
        df.columns = df.columns.astype(str).str.strip().str.title()
        
        hotel_df = pd.read_excel(file_path, sheet_name="List Selections", usecols="B:H")
        return df, hotel_df
    except Exception as e:
        st.error(f"Excel Error: {e}")
        return None, None

dist_matrix, hotel_lookup = load_excel_data()
ALL_CITIES = sorted(dist_matrix.index.unique().tolist()) if dist_matrix is not None else ["London"]

# --- 2. LOOKUP HELPERS ---
def get_matrix_dist(origin, destination):
    if dist_matrix is None: return 0.0
    try:
        o, d = str(origin).strip().title(), str(destination).strip().title()
        return float(dist_matrix.loc[o, d])
    except:
        return 0.0

def get_hotel_factor(city, stars):
    try:
        c = str(city).strip().title()
        # Col 1 is City (Column C in original B:H range)
        row = hotel_lookup[hotel_lookup.iloc[:, 1].astype(str).str.strip().str.title() == c]
        star_col_map = {5: 3, 4: 4, 3: 5, 2: 6} 
        return float(row.iloc[0, star_col_map[stars]])
    except:
        return 21.7

# --- 3. UPDATED CALCULATION ENGINE ---
TRANSPORT = {"Plane (Business)": 0.274, "Plane (Economy)": 0.182, "Rail": 0.035, "Car": 0.151}

def calculate_impact(party_name, teams, meetings, data_share, is_v, h_ct, h_d, c_months):
    # Initialize session state for audit within the function to ensure it's captured
    if "audit_logs" not in st.session_state: st.session_state.audit_logs = []
    
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
    
    # HEARING
    if not is_v and h_ct != "Virtual":
        for t in teams:
            if t['size'] > 0:
                dist = get_matrix_dist(t['city'], h_ct)
                # Correct Multiplier: (Distance * 2) * People * Factor
                travel_val = (dist * 2.0) * float(t['size']) * TRANSPORT[t['mode']]
                res["Scope 3: Travel (Hearing)"] += travel_val
                
                st.session_state.audit_logs.append({
                    "Party": party_name, "Type": "Hearing", "From": t['city'], "To": h_ct, 
                    "Dist": dist, "Qty": t['size'], "Result": round(travel_val, 2)
                })
                res["Scope 3: Hotel Stays"] += t['size'] * h_d * get_hotel_factor(h_ct, t['stars'])
            
    # PREP MEETINGS
    if meetings:
        for m in meetings:
            for trip in m['trips']:
                t = teams[trip['idx']]
                dist = get_matrix_dist(t['city'], m['loc'])
                
                # Logic Gate Resolved: Even if travel_val is 0, we process the log and hotel stay
                travel_val = (dist * 2.0) * float(trip['count']) * float(m['occ']) * TRANSPORT[t['mode']]
                res["Scope 3: Travel (Prep)"] += travel_val
                
                st.session_state.audit_logs.append({
                    "Party": party_name, "Type": f"Prep @ {m['label']}", "From": t['city'], "To": m['loc'], 
                    "Dist": dist, "Qty": trip['count'], "Result": round(travel_val, 2)
                })
                # Hotel factor based on meeting location city
                h_fact = get_hotel_factor(m['loc'], t['stars'])
                res["Scope 3: Hotel Stays"] += trip['count'] * trip['days'] * m['occ'] * h_fact
    return res

# --- 4. UI SECTIONS ---
def subteam_ui(label, prefix, default_size=2):
    st.markdown(f"**{label}**")
    c1, c2, c3, c4 = st.columns([1, 1.5, 1.5, 1])
    size = c1.number_input("Size", value=default_size, key=f"{prefix}s")
    city = c2.selectbox("Base City", ALL_CITIES, key=f"{prefix}c")
    mode = c3.selectbox("Mode", list(TRANSPORT.keys()), key=f"{prefix}m")
    star = c4.selectbox("Stars", [5, 4, 3, 2], index=1, key=f"{prefix}h")
    return {"size": size, "city": city, "mode": mode, "stars": star}

def meet_ui(label, prefix, teams, loc_city):
    with st.expander(f"📅 Prep Trips to {label} ({loc_city})"):
        m_trips = []
        for i, name in enumerate(["Client", "Counsel", "Expert"]):
            col1, col2, col3 = st.columns([2, 1, 1])
            if col1.checkbox(f"{name} travels", key=f"{prefix}a{i}"):
                m_trips.append({"idx": i, "count": col2.number_input("Qty", 1, 20, 1, key=f"{prefix}q{i}"), 
                                "days": col3.number_input("Nights", 1, 30, 2, key=f"{prefix}n{i}")})
        occ = st.number_input("Meetings", 1, 20, 1, key=f"{prefix}o")
        return {"trips": m_trips, "occ": occ, "loc": loc_city, "label": label}

# --- 5. MAIN RENDER ---
st.session_state.audit_logs = [] 
with st.sidebar:
    case_months = st.number_input("Duration (Months)", value=24)
    total_data = st.number_input("Total Data (GB)", value=10)
    is_v = st.toggle("Virtual Hearing", value=False)
    h_ct = st.selectbox("Hearing City", ALL_CITIES) if not is_v else "Virtual"
    h_d = st.slider("Hearing Days", 1, 21, 5) if not is_v else 0
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

st.title("⚖️ Professional Arbitration Carbon Model")
t_cl, t_res, t_tr, t_sum = st.tabs(["🔴 Claimant", "🔵 Respondent", "⚖️ Tribunal", "📊 Summary"])

with t_cl:
    c_t = [subteam_ui("Client Team", "cc"), subteam_ui("Counsel", "cl"), subteam_ui("Expert", "ce")]
    c_m = [
        meet_ui("Client Office", "cm1", c_t, c_t[0]['city']), 
        meet_ui("Counsel Chambers", "cm2", c_t, c_t[1]['city']), 
        meet_ui("Expert Office", "cm3", c_t, c_t[2]['city'])
    ]
    c_res = calculate_impact("Claimant", c_t, c_m, total_data*0.4, is_v, h_ct, h_d, case_months)
    st.dataframe(pd.DataFrame.from_dict(c_res, orient='index'))

# Respondent and Tribunal logic should follow the same pattern...

with t_sum:
    st.header("🔍 Detailed Calculation Audit")
    if st.session_state.audit_logs:
        st.table(pd.DataFrame(st.session_state.audit_logs))
