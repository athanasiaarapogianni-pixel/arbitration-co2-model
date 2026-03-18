import streamlit as st
import pandas as pd
import openpyxl
import plotly.express as px
import os

# --- 1. DATA LOADING (Updated for C7 / D6 Mapping) ---
@st.cache_data
def load_excel_data():
    file_path = "carbon_model.xlsx"
    
    if not os.path.exists(file_path):
        return None, None

    try:
        # header=5 tells Python that Row 6 (D6) contains the column names
        # index_col=2 tells Python that Column C (index 2) contains the row names
        dist_df = pd.read_excel(file_path, sheet_name="Travel Matrix", header=5, index_col=2)
        
        # We drop any completely empty rows or columns that might be in the margins
        dist_df = dist_df.dropna(axis=0, how='all').dropna(axis=1, how='all')
        
        # Load Hotel Factors from 'List Selections' (B:H)
        hotel_df = pd.read_excel(file_path, sheet_name="List Selections", usecols="B:H")
        
        return dist_df, hotel_df
    except Exception as e:
        st.error(f"Excel Loading Error: {e}")
        return None, None

# Sidebar - Controls
st.sidebar.header("🛠️ Data Controls")
if st.sidebar.button("🔄 Refresh Excel Data"):
    st.cache_data.clear()
    st.rerun()

dist_matrix, hotel_lookup = load_excel_data()

if dist_matrix is not None:
    # We filter out any 'Unnamed' artifacts from the Excel headers
    ALL_CITIES = sorted([c for c in dist_matrix.index.dropna().unique() if "Unnamed" not in str(c)])
    st.sidebar.success(f"✅ Loaded {len(ALL_CITIES)} cities")
    
    if st.sidebar.checkbox("👀 Preview Matrix Data"):
        st.sidebar.write(dist_matrix.iloc[:5, :5]) # Show top-left 5x5 corner
else:
    ALL_CITIES = ["London", "Paris", "New York"]
    st.sidebar.warning("⚠️ Using Fallback Cities")

# --- 2. LOOKUP FUNCTIONS ---
def get_matrix_dist(origin, destination):
    try:
        # We ensure names are strings and stripped of whitespace
        val = dist_matrix.loc[str(origin).strip(), str(destination).strip()]
        return float(val)
    except:
        return 850.0 

def get_hotel_factor(city, stars):
    try:
        # Col C (Index 1) is City. Col E,F,G,H (Index 3,4,5,6) are star ratings.
        row = hotel_lookup[hotel_lookup.iloc[:, 1].str.strip() == str(city).strip()]
        star_col_map = {5: 3, 4: 4, 3: 5, 2: 6} 
        return float(row.iloc[0, star_col_map[stars]])
    except:
        return 21.7 

# --- 3. SIDEBAR PARAMETERS ---
with st.sidebar:
    st.header("🌍 Global Parameters")
    case_months = st.number_input("Case Duration (Months)", value=24)
    total_data = st.number_input("Total Data (GB)", value=10)
    st.divider()
    is_virtual = st.toggle("Virtual Hearing", value=False)
    if not is_virtual and ALL_CITIES:
        h_city = st.selectbox("Hearing City", ALL_CITIES, index=0)
        h_days = st.slider("Hearing Duration (Days)", 1, 21, 5)
    else:
        h_city, h_days = "Virtual", 0

# --- 4. UI TABS ---
st.title("⚖️ Professional Arbitration Carbon Model")
t_cl, t_res, t_trib, t_sum = st.tabs(["🔴 Claimant", "🔵 Respondent", "⚖️ Tribunal", "📊 Case Summary"])

def subteam_inputs(label, prefix):
    st.markdown(f"**{label}**")
    c1, c2, c3, c4 = st.columns([1, 1.5, 1.5, 1])
    size = c1.number_input("Size", value=2, key=f"{prefix}_sz", min_value=0)
    city = c2.selectbox("Base City", ALL_CITIES, key=f"{prefix}_ct")
    mode = c3.selectbox("Travel", ["Plane (Business)", "Plane (Economy)", "Rail", "Car"], key=f"{prefix}_md")
    stars = c4.selectbox("Hotel", [5, 4, 3, 2], index=1, key=f"{prefix}_st")
    return {"size": size, "city": city, "mode": mode, "stars": stars}

def meeting_matrix(label, prefix, teams):
    with st.expander(f"📅 Prep Meetings at {label}"):
        m_trips = []
        for i, team in enumerate(["Client", "Counsel", "Experts"]):
            col1, col2, col3 = st.columns([2, 1, 1])
            if col1.checkbox(f"{team} travels", key=f"{prefix}_att_{i}"):
                count = col2.number_input("Qty", 1, 20, 1, key=f"{prefix}_cnt_{i}")
                days = col3.number_input("Nights", 1, 30, 2, key=f"{prefix}_dur_{i}")
                m_trips.append({"idx": i, "count": count, "days": days})
        occ = st.number_input("Total Meetings", 1, 20, 1, key=f"{prefix}_occ")
        loc_city = teams[0]['city'] if "Client" in label else (teams[1]['city'] if "Counsel" in label else teams[2]['city'])
        return {"trips": m_trips, "occ": occ, "loc": loc_city}

# --- 5. CALCULATION ENGINE ---
TRANSPORT = {"Plane (Business)": 0.274, "Plane (Economy)": 0.182, "Rail": 0.035, "Car": 0.151}

def calculate_impact(teams, meetings, data_share, virtual_override=False):
    num_ppl = sum(t['size'] for t in teams)
    comp_total = num_ppl * case_months * 6.4444
    res = {
        "Scope 2: Computer Use": comp_total * 0.15,
        "Scope 2: Printing & Office": num_ppl * 4.5,
        "Scope 3: Business Travel (Prep)": 0.0,
        "Scope 3: Business Travel (Hearing)": 0.0,
        "Scope 3: Hotel Stays": 0.0,
        "Scope 3: Digital Storage & Mfg": (data_share * 0.021) + (comp_total * 0.85),
        "Scope 3: Materials": num_ppl * 0.42
    }
    if not virtual_override and not is_virtual and h_city != "Virtual":
        for t in teams:
            d = get_matrix_dist(t['city'], h_city)
            res["Scope 3: Business Travel (Hearing)"] += d * 2 * t['size'] * TRANSPORT[t['mode']]
            res["Scope 3: Hotel Stays"] += t['size'] * h_days * get_hotel_factor(h_city, t['stars'])
    if meetings:
        for m in meetings:
            for trip in m['trips']:
                t = teams[trip['idx']]
                d = get_matrix_dist(t['city'], m['loc'])
                if d > 0:
                    res["Scope 3: Travel (Prep)"] += d * 2 * trip['count'] * m['occ'] * TRANSPORT[t['mode']]
                    res["Scope 3: Hotel Stays"] += trip['count'] * trip['days'] * m['occ'] * get_hotel_factor(m['loc'], t['stars'])
    return res

# --- 6. RUN CALCULATIONS ---
with t_cl:
    c_t = [subteam_inputs("Client Team", "c_cli"), subteam_inputs("Legal Counsel", "c_cou"), subteam_inputs("Experts", "c_exp")]
    c_m = [meeting_matrix("Client Office", "c1", c_t), meeting_matrix("Counsel Chambers", "c2", c_t), meeting_matrix("Expert Office", "c3", c_t)]
with t_res:
    r_t = [subteam_inputs("Client Team", "r_cli"), subteam_inputs("Legal Counsel", "r_cou"), subteam_inputs("Experts", "r_exp")]
    r_m = [meeting_matrix("Respondent Office", "r1", r_t), meeting_matrix("Counsel Chambers", "r2", r_t), meeting_matrix("Expert Office", "r3", r_t)]
with t_trib:
    tr_t = [subteam_inputs(f"Arbitrator {i+1}", f"t_a{i}") for i in range(3)]

c_res, r_res, tr_res = calculate_impact(c_t, c_m, total_data*0.4), calculate_impact(r_t, r_m, total_data*0.4), calculate_impact(tr_t, None, total_data*0.2)

# --- 7. SUMMARY ---
with t_sum:
    grand = sum(c_res.values()) + sum(r_res.values()) + sum(tr_res.values())
    c1, c2, c3 = st.columns(3)
    c1.metric("Grand Total Impact", f"{grand:,.1f} kgCO2e")
    c2.metric("Equiv. Cars (Year)", f"{(grand/1.324287002):,.1f}")
    c3.metric("Trees Required", f"{(grand/25):,.1f}")
    
    st.divider()
    
    df_plot = []
    for party, data in [("Claimant", c_res), ("Respondent", r_res), ("Tribunal", tr_res)]:
        for cat, val in data.items():
            df_plot.append({"Party": party, "Category": cat, "kgCO2e": val})
    
    st.plotly_chart(px.bar(pd.DataFrame(df_plot), x="Party", y="kgCO2e", color="Category", barmode="stack", title="Impact by Category"), use_container_width=True)

    h_display = "VIRTUAL" if is_virtual else (f"PHYSICAL - {h_city}" if h_city else "NOT SELECTED")
    st.code(f"TOTAL FOOTPRINT: {grand:,.2f} kgCO2e\nHearing: {h_display}\nCars/Year: {(grand/1.324287002):,.2f}\nTrees: {(grand/25):,.2f}")
