import streamlit as st
import pandas as pd
import bcrypt
from sqlalchemy import create_engine
import urllib.parse

# --- DATABASE CONNECTION ---
# This looks for the secret you just pasted in Step 1
try:
    if "database" in st.secrets:
        db_url = st.secrets["database"]["url"]
        # Use 'postgresql+psycopg2' to explicitly tell SQLAlchemy which driver to use
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+psycopg2://")
        
        engine = create_engine(db_url)
    else:
        st.error("Missing Database Secrets! Go to Settings > Secrets in Streamlit Cloud.")
        st.stop()
except Exception as e:
    st.error(f"Configuration Error: {e}")
    st.stop()

# Now the rest of your app (Login, Analytics, etc.) will use this engine
# --- AUTHENTICATION LOGIC ---
def check_login(username, password):
    query = f"SELECT password_hash, role FROM users WHERE username = '{username}'"
    user_data = pd.read_sql(query, engine)
    
    if not user_data.empty:
        stored_hash = user_data.iloc[0]['password_hash']
        if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
            return user_data.iloc[0]['role']
    return None

# --- SESSION STATE INITIALIZATION ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['role'] = None

# --- LOGIN SCREEN ---
if not st.session_state['logged_in']:
    st.title("🇿🇼 ZIMRA Secure Portal Login")
    with st.form("login_form"):
        user = st.text_input("Username")
        pw = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            role = check_login(user, pw)
            if role:
                st.session_state['logged_in'] = True
                st.session_state['role'] = role
                st.rerun()
            else:
                st.error("Invalid username or password")
    st.stop() # Stops the script here if not logged in

# --- PROTECTED APP CONTENT STARTS HERE ---
st.sidebar.success(f"Logged in as: {st.session_state['role']}")
if st.sidebar.button("Logout"):
    st.session_state['logged_in'] = False
    st.rerun()

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- PAGE SETUP ---
st.set_page_config(page_title="ZIMRA Audit Command Center", layout="wide", page_icon="🇿🇼")

st.markdown("""
    <style>
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #006400; }
    .dossier-box { background-color: #ffffff; padding: 20px; border-radius: 8px; border: 1px solid #ff4b4b; margin-top: 10px;}
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    df = pd.read_csv("zimra_data.csv")
    
    rev_threshold = df['annual_revenue_usd'].quantile(0.75)
    def define_quadrant(row):
        is_high_risk = row['prediction_score'] >= 70
        is_high_impact = row['annual_revenue_usd'] >= rev_threshold
        if is_high_risk and is_high_impact: return "High Risk / High Impact"
        elif is_high_risk: return "High Risk / Low Impact"
        elif is_high_impact: return "Low Risk / High Impact"
        return "Low Risk / Low Impact"
        
    if 'risk_quadrant' not in df.columns:
        df['risk_quadrant'] = df.apply(define_quadrant, axis=1)
    return df

df = load_data()

# --- SIDEBAR FILTERS ---
st.sidebar.title("🔍 Global Filters")

st.sidebar.subheader("📂 Categories")
sel_sectors = st.sidebar.multiselect("Sectors", df['sector'].unique(), df['sector'].unique())
sel_regions = st.sidebar.multiselect("Regions", df['region'].unique(), df['region'].unique())
sel_quadrants = st.sidebar.multiselect("Risk Quadrants", df['risk_quadrant'].unique(), df['risk_quadrant'].unique())

st.sidebar.subheader("🔢 Metrics & Risk")
min_score, max_score = st.sidebar.slider("Prediction Score (%)", 0, 100, (0, 100))
max_rev = float(df['annual_revenue_usd'].max())
min_rev, max_rev_sel = st.sidebar.slider("Revenue (USD)", 0.0, max_rev, (0.0, max_rev))
max_debt = float(df['outstanding_debt_zig'].max())
min_debt, max_debt_sel = st.sidebar.slider("Debt (ZiG)", 0.0, max_debt, (0.0, max_debt))

# --- APPLY FILTERS ---
filtered_df = df[
    (df['sector'].isin(sel_sectors)) & (df['region'].isin(sel_regions)) &
    (df['risk_quadrant'].isin(sel_quadrants)) & (df['prediction_score'].between(min_score, max_score)) &
    (df['annual_revenue_usd'].between(min_rev, max_rev_sel)) & (df['outstanding_debt_zig'].between(min_debt, max_debt_sel))
]

# --- MAIN DASHBOARD ---
st.title("🛡️ ZIMRA Risk Intelligence Portal")

# Dynamic Alerts
if filtered_df['prediction_score'].mean() > 75:
    st.error("⚠️ ALERT: Current filter selection shows a critically high average risk profile. Immediate task force deployment recommended.")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Taxpayers Found", f"{len(filtered_df):,}")
col2.metric("Avg Prediction Score", f"{filtered_df['prediction_score'].mean():.1f}%" if not filtered_df.empty else "0%")
col3.metric("Revenue at Risk", f"${filtered_df['annual_revenue_usd'].sum():,.0f}")
col4.metric("Total Debt (ZiG)", f"{filtered_df['outstanding_debt_zig'].sum():,.0f}")

st.divider()

# --- 3-TAB INTERFACE ---
tab1, tab2, tab3 = st.tabs(["📋 Master Audit List", "📈 Strategic Analytics", "🔎 Single Taxpayer Deep-Dive"])

# TAB 1: DATA TABLE
with tab1:
    if not filtered_df.empty:
        display_cols = ['taxpayer_name', 'taxpayer_id', 'risk_quadrant', 'region', 'annual_revenue_usd', 'prediction_score']
        st.dataframe(
            filtered_df[display_cols].sort_values("prediction_score", ascending=False),
            column_config={
                "prediction_score": st.column_config.ProgressColumn("Risk Score", format="%d%%", min_value=0, max_value=100),
                "annual_revenue_usd": st.column_config.NumberColumn("Revenue (USD)", format="$%d"),
            },
            use_container_width=True
        )
    else:
        st.warning("No data matches your filters.")

# TAB 2: ANALYTICS
with tab2:
    if not filtered_df.empty:
        st.subheader("Executive Resource Allocation")
        
        # 1. NEW: The Treemap (Hierarchical View)
        fig_tree = px.treemap(
            filtered_df, path=[px.Constant("ZIMRA Total"), 'region', 'sector', 'risk_quadrant'],
            values='outstanding_debt_zig', color='prediction_score',
            color_continuous_scale='RdYlGn_r',
            title="Debt Distribution Hierarchy (Size = Debt, Color = Risk Score)"
        )
        st.plotly_chart(fig_tree, use_container_width=True)
        
        st.divider()
        
        # 2. Scatter & Heatmap
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            fig_scatter = px.scatter(
                filtered_df, x="annual_revenue_usd", y="outstanding_debt_zig", 
                color="prediction_score", size="prediction_score", hover_name="taxpayer_name",
                color_continuous_scale="RdYlGn_r", title="Financial Impact vs. Debt Profile"
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
            
        with chart_col2:
            heatmap_data = filtered_df.groupby(['region', 'sector'])['prediction_score'].mean().reset_index()
            fig_heat = px.density_heatmap(
                heatmap_data, x="region", y="sector", z="prediction_score", 
                title="Risk Heatmap: Avg Score by Region & Sector", color_continuous_scale="RdYlGn_r"
            )
            st.plotly_chart(fig_heat, use_container_width=True)

# TAB 3: TAXPAYER DEEP DIVE (THE DOSSIER)
with tab3:
    st.subheader("Generate Audit Dossier")
    
    # Let user pick a specific taxpayer from the filtered list
    selected_id = st.selectbox("Search Taxpayer by ID / Name:", filtered_df['taxpayer_name'] + " (" + filtered_df['taxpayer_id'] + ")")
    
    if selected_id:
        # Extract ID from the string
        tp_id = selected_id.split("(")[1].replace(")", "")
        tp_data = filtered_df[filtered_df['taxpayer_id'] == tp_id].iloc[0]
        
        col_prof1, col_prof2 = st.columns([1, 2])
        
        with col_prof1:
            st.markdown(f"### {tp_data['taxpayer_name']}")
            st.caption(f"ID: {tp_data['taxpayer_id']} | Sector: {tp_data['sector']} | Region: {tp_data['region']}")
            
            # Big risk score metric
            st.metric("AI Risk Prediction", f"{tp_data['prediction_score']}%")
            st.markdown(f"**Quadrant:** {tp_data['risk_quadrant']}")
            
            # Automated text summary
            st.markdown("""<div class="dossier-box">
                <b>🤖 Automated Audit Brief:</b><br>
                This taxpayer requires attention due to a combination of high revenue footprint and behavioral risk indicators. 
                Prioritize checking their fiscal device logs and recent VAT declarations.
                </div>""", unsafe_allow_html=True)
            
        with col_prof2:
            # Radar / Bar chart showing their specific risk factors vs expected norms
            risk_factors = pd.DataFrame({
                "Factor": ["Late Filings", "Previous Violations", "Device Downtime (%)", "VAT to Sales Ratio"],
                "Value": [
                    tp_data['late_filings_last_12m'], 
                    tp_data['previous_audit_violations'], 
                    100 - tp_data['fiscal_device_uptime_pct'], # Invert uptime to make it a "risk" metric
                    tp_data['vat_to_sales_ratio'] * 100 # scale for readability
                ]
            })
            
            fig_bar = px.bar(risk_factors, x="Value", y="Factor", orientation='h', 
                             title="Key Risk Drivers for this Taxpayer", color="Value", color_continuous_scale="Reds")
            st.plotly_chart(fig_bar, use_container_width=True)
            

        st.button("📄 Generate PDF Audit Notice (Simulated)", type="primary")

