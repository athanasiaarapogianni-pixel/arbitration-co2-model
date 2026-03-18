import streamlit as st
import pandas as pd
import openpyxl
import plotly.express as px

# --- 1. DATA LOADING ---
@st.cache_data
def load_excel_data():
    file_path = "carbon_model.xlsx"
    # Travel Matrix: City names in Row 1 and Column A
    dist_df = pd.read_excel(file_path, sheet_name="Travel Matrix", index_col=0)
    # List Selections: Columns B through H
    hotel_df = pd.read_excel(file_path, sheet_name="List Selections", usecols="B:H")
    return dist_df, hotel_df

# Sidebar - Refresh Logic
if st.sidebar.button("🔄 Refresh Excel Data"):
    st.cache_data.clear()
    st.sidebar.success("Data Refreshed!")

try:
    dist_matrix, hotel_lookup = load_excel_data()
    ALL_CITIES = sorted(dist_matrix.index.dropna().unique().tolist())
except Exception as e:
    st.error(f"Error loading Excel: {e}")
    ALL_CITIES = ["London", "Paris", "New York", "Munich"]

# --- 2. LOOKUP FUNCTIONS ---
def get_matrix_dist(origin, destination):
    try:
        return float(dist_matrix.loc[origin, destination])
    except:
        return 850.0 # Fallback average

def get_hotel_factor(city, stars):
    try:
        # hotel_lookup loaded with usecols="B:H"
        # Index 0 = B (Country)
        # Index 1 = C (City)
        # Index 2 = D (Empty/Misc)
        # Index 3 = E (5-star)
        # Index 4 = F (4-star)
        # Index 5 = G (3-star)
        # Index 6 = H (2-star)
        
        row = hotel_lookup[hotel_lookup.iloc[:, 1] == city]
        
        # Updated mapping based on your new Excel structure
        star_col_map = {5: 3, 4: 4, 3: 5, 2: 6} 
        
        factor = row.iloc[0, star_col_map[stars]]
        return float(factor)
    except:
        return 21.7 # Fallback average

# --- 3. SIDEBAR PARAMETERS ---
with st.sidebar:
    st.header("🌍 Global Case Parameters")
    case_months = st.number_input("Arbitration Duration (Months)", value=24)
    total_data = st.number_input("Total Data Generated (GB)", value=10)
    
    st.divider()
    is_virtual = st.toggle("Virtual Hearing", value=False)
    if not is_virtual:
        h_city = st.selectbox("Hearing City", ALL_CITIES, index=0)
        h_days = st.slider("Hearing Duration (Days)", 1, 21, 5)
    else:
        h_city, h_days = "Virtual", 0

# --- 4. UI TABS ---
st.title("⚖️ Professional Arbitration Carbon Model")
tab_cl, tab_res, tab_trib, tab_sum = st.tabs(["🔴 Claimant", "🔵 Respondent", "⚖️ Tribunal", "📊 Case Summary"])

def subteam_inputs(label, prefix):
    st.markdown(f"**{label}**")
    c1, c2, c3, c4 = st.columns([1, 1.5, 1.5, 1])
    size = c1.number_input("Size", value=2, key=f"{prefix}_sz", min_value=0)
    city = c2.selectbox("Base City", ALL_CITIES, key=f"{prefix}_ct")
    mode = c3.selectbox("Travel", ["Plane (Business)", "Plane (Economy)", "Rail", "Car"], key=f"{prefix}_md")
    # Added 2-star option to dropdown
    stars = c4.selectbox("Hotel", [5, 4, 3, 2], index=1, key=f"{prefix}_st")
    return {"size": size, "city": city, "mode": mode, "stars": stars}

def meeting_matrix(label, prefix, teams):
    with st.expander(f"📅 Prep Meetings at {label}", expanded=False):
        m_trips = []
        for i, team_name in enumerate(["Client Team", "Legal Counsel", "Experts"]):
            col1, col2, col3 = st.columns([2, 1, 1])
            if col1.checkbox(f"{team_name} travels", key=f"{prefix}_att_{i}"):
                count = col2.number_input("Qty", 1, 20, value=1, key=f"{prefix}_cnt_{i}")
                days = col3.number_input("Nights", 1, 30, value=2, key=f"{prefix}_dur_{i}")
                m_trips.append({"idx": i, "count": count, "days": days})
        occ = st.number_input("Total Meetings", 1, 20, value=1, key=f"{prefix}_occ")
        loc_city = teams[0]['city'] if "Client" in label else (teams[1]['city'] if "Counsel" in label else teams[2]['city'])
        return {"trips": m_trips, "occ": occ, "loc": loc_city}

# --- 5. CALCULATION ENGINE ---
TRANSPORT_FACTORS = {"Plane (Business)": 0.274, "Plane (Economy)": 0.182, "Rail": 0.035, "Car": 0.151}

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
    
    if not virtual_override and not is_virtual:
        for t in teams:
            d = get_matrix_dist(t['city'], h_city)
            h_fact = get_hotel_factor(h_city, t['stars'])
            res["Scope 3: Business Travel (Hearing)"] += d * 2 * t['size'] * TRANSPORT_FACTORS[t['mode']]
            res["Scope 3: Hotel Stays"] += t['size'] * h_days * h_fact
            
    if meetings:
        for m in meetings:
            for trip in m['trips']:
                t = teams[trip['idx']]
                d = get_matrix_dist(t['city'], m['loc'])
                h_fact = get_hotel_factor(m['loc'], t['stars'])
                if d > 0:
                    res["Scope 3: Business Travel (Prep)"] += d * 2 * trip['count'] * m['occ'] * TRANSPORT_FACTORS[t['mode']]
                    res["Scope 3: Hotel Stays"] += trip['count'] * trip['days'] * m['occ'] * h_fact
    return res

# --- 6. EXECUTION ---
with tab_cl:
    c_t = [subteam_inputs("Client Team", "c_cli"), subteam_inputs("Legal Counsel", "c_cou"), subteam_inputs("Experts", "c_exp")]
    st.divider()
    c_m = [meeting_matrix("Client Office", "c1", c_t), meeting_matrix("Counsel Chambers", "c2", c_t), meeting_matrix("Expert Office", "c3", c_t)]

with tab_res:
    r_t = [subteam_inputs("Client Team", "r_cli"), subteam_inputs("Legal Counsel", "r_cou"), subteam_inputs("Experts", "r_exp")]
    st.divider()
    r_m = [meeting_matrix("Respondent Office", "r1", r_t), meeting_matrix("Counsel Chambers", "r2", r_t), meeting_matrix("Expert Office", "r3", r_t)]

with tab_trib:
    tr_t = [subteam_inputs(f"Arbitrator {i+1}", f"t_a{i}") for i in range(3)]

c_res = calculate_impact(c_t, c_m, total_data * 0.4)
r_res = calculate_impact(r_t, r_m, total_data * 0.4)
tr_res = calculate_impact(tr_t, None, total_data * 0.2)

# --- 7. SUMMARY TAB ---
with tab_sum:
    c_total, r_total, t_total = sum(c_res.values()), sum(r_res.values()), sum(tr_res.values())
    grand_total = c_total + r_total + t_total
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Grand Total (kgCO2e)", f"{grand_total:,.1f}")
    col2.metric("Equiv. Cars (Year)", f"{(grand_total/1.324287002):,.1f}")
    col3.metric("Trees Required", f"{(grand_total/25):,.1f}")
    
    if is_virtual:
        c_phys = calculate_impact(c_t, c_m, total_data * 0.4, virtual_override=False)
        r_phys = calculate_impact(r_t, r_m, total_data * 0.4, virtual_override=False)
        tr_phys = calculate_impact(tr_t, None, total_data * 0.2, virtual_override=False)
        savings = (sum(c_phys.values()) + sum(r_phys.values()) + sum(tr_phys.values())) - grand_total
        st.success(f"🌱 Conducted virtually: **{savings:,.1f} kgCO2e** avoided.")

    st.divider()
    
    df_plot = []
    for p, d in [("Claimant", c_res), ("Respondent", r_res), ("Tribunal", tr_res)]:
        for cat, val in d.items():
            df_plot.append({"Party": p, "Category": cat, "kgCO2e": val})
    
    fig = px.bar(pd.DataFrame(df_plot), x="Party", y="kgCO2e", color="Category", 
                 barmode="stack", title="Impact by Category & Party",
                 color_discrete_sequence=px.colors.qualitative.Pastel)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📋 Case Summary Report")
    st.code(f"""
ARBITRATION CARBON IMPACT SUMMARY
----------------------------------
Duration: {case_months} Months
Hearing: {'VIRTUAL' if is_virtual else 'PHYSICAL - ' + h_city}

TOTAL CASE FOOTPRINT: {grand_total:,.1f} kgCO2e

EQUIVALENCIES:
- Number of cars (1 year): {(grand_total/1.324287002):,.1f}
- Trees to offset: {(grand_total/25):,.1f}
    """)

# Expanders for raw data
with st.expander("Claimant Detailed Table"): st.dataframe(pd.DataFrame.from_dict(c_res, orient='index'))
with st.expander("Respondent Detailed Table"): st.dataframe(pd.DataFrame.from_dict(r_res, orient='index'))
with st.expander("Tribunal Detailed Table"): st.dataframe(pd.DataFrame.from_dict(tr_res, orient='index'))
