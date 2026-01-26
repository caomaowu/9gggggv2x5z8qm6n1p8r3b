import streamlit as st
import pandas as pd
import os
import sys
import plotly.graph_objects as go

# 路径设置
current_dir = os.path.dirname(os.path.abspath(__file__))
# tools/meta_analyzer -> tools -> refactor_v2
project_root = os.path.dirname(os.path.dirname(current_dir))
backend_dir = os.path.join(project_root, "backend")

if project_root not in sys.path:
    sys.path.append(project_root)
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

try:
    from tools.meta_analyzer.loader import DataLoader
    from tools.meta_analyzer.diagnosis import MetaAgent
except ImportError:
    # 尝试相对导入，如果在同一包内运行
    from loader import DataLoader
    from diagnosis import MetaAgent

st.set_page_config(page_title="QuantAgent Meta-Analyzer", layout="wide", page_icon="🕵️")

# --- 初始化 ---
@st.cache_resource
def get_components():
    history_dir = os.path.join(backend_dir, "data", "history")
    loader = DataLoader(history_dir)
    agent = MetaAgent()
    return loader, agent

loader, meta_agent = get_components()

if "df" not in st.session_state:
    with st.spinner("Loading history data..."):
        st.session_state.df = loader.load_all_cases()

# --- Sidebar Filters ---
st.sidebar.title("🕵️ Meta-Analyzer")

if st.sidebar.button("🔄 Reload Data"):
    st.session_state.df = loader.load_all_cases()
    st.rerun()

df = st.session_state.df

if df.empty:
    st.warning("No history data found in backend/data/history/")
    st.stop()

# 1. Date Filter
dates = sorted(df['timestamp'].apply(lambda x: str(x).split(' ')[0]).unique(), reverse=True)
selected_date = st.sidebar.selectbox("Date", ["All"] + list(dates))

# 2. Asset Filter
assets = sorted(df['asset'].unique())
selected_asset = st.sidebar.selectbox("Asset", ["All"] + list(assets))

# 3. PnL Status Filter
pnl_statuses = sorted(df['pnl_status'].unique())
selected_pnl = st.sidebar.multiselect("PnL Status", pnl_statuses, default=pnl_statuses)

# 4. Action Filter
actions = sorted(df['action'].unique())
selected_action = st.sidebar.multiselect("Action", actions, default=["LONG", "SHORT"])

# Apply Filters
filtered_df = df.copy()
if selected_date != "All":
    filtered_df = filtered_df[filtered_df['timestamp'].astype(str).str.startswith(selected_date)]
if selected_asset != "All":
    filtered_df = filtered_df[filtered_df['asset'] == selected_asset]
if selected_pnl:
    filtered_df = filtered_df[filtered_df['pnl_status'].isin(selected_pnl)]
if selected_action:
    filtered_df = filtered_df[filtered_df['action'].isin(selected_action)]

st.sidebar.markdown(f"**Found {len(filtered_df)} cases**")

# --- Main Area ---

# Case Selector
if filtered_df.empty:
    st.info("No cases match your filters.")
    st.stop()

# Create a readable label for the selectbox
filtered_df['label'] = filtered_df.apply(
    lambda x: f"[{x['timestamp']}] {x['asset']} ({x['timeframe']}) - {x['action']} - {x['pnl_status']} (P:{x['max_profit']}%)", axis=1
)

selected_case_label = st.selectbox("Select Case to Analyze", filtered_df['label'])
selected_row = filtered_df[filtered_df['label'] == selected_case_label].iloc[0]

# Load Detail
case_detail = loader.get_case_detail(selected_row['file_path'])

st.divider()

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("🤖 Agent Decision")
    
    decision = case_detail.get("decision", {})
    st.info(f"**Action**: {decision.get('action')} | **Entry**: {decision.get('entry_point')} | **Reason**: {decision.get('reasoning')}")
    
    with st.expander("📊 Indicator Report"):
        if "analysis_results" in case_detail:
            st.markdown(case_detail["analysis_results"].get("Indicator", {}).get("indicator_report", "N/A"))
            
    with st.expander("📉 Pattern Report"):
        if "analysis_results" in case_detail:
            st.markdown(case_detail["analysis_results"].get("Pattern", {}).get("pattern_report", "N/A"))
            
    with st.expander("📈 Trend Report"):
        if "analysis_results" in case_detail:
            st.markdown(case_detail["analysis_results"].get("Trend", {}).get("trend_report", "N/A"))

with col2:
    st.subheader("🔮 Market Reality (Future)")
    
    future_kline = case_detail.get("future_kline_data", [])
    if future_kline:
        # Plotly Chart
        k_df = pd.DataFrame(future_kline)
        fig = go.Figure(data=[go.Candlestick(x=k_df['datetime'],
                        open=k_df['open'],
                        high=k_df['high'],
                        low=k_df['low'],
                        close=k_df['close'])])
        fig.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)
        
        # Metrics
        m_col1, m_col2 = st.columns(2)
        m_col1.metric("Max Profit", f"{selected_row['max_profit']}%")
        m_col2.metric("Max Drawdown", f"{selected_row['max_drawdown']}%", delta_color="inverse")
    else:
        st.warning("No Future Kline Data Available")

st.divider()

# --- Diagnosis Section ---
st.header("🕵️ AI Diagnosis")

# 检查环境变量是否已加载
if "AGENT_PROVIDER" not in os.environ:
    st.warning("Environment variables not loaded. Using default settings or check console logs.")

if st.button("🚀 Start Diagnosis", type="primary"):
    if not meta_agent.llm:
        st.error("LLM Client not initialized. Please check your .env configuration.")
    else:
        with st.spinner("Analyzing..."):
            response_stream = meta_agent.diagnose_case(case_detail)
            st.write_stream(response_stream)

