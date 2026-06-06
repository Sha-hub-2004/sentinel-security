import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
from datetime import datetime
import time
import os

# Set up page configurations
st.set_page_config(
    page_title="Sentinel Security Monitor",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Connect to the database (reads from environment or defaults to local SQLite)
DB_PATH = os.environ.get("DATABASE_URL", "sqlite:///./dev.db")
# Fix Heroku/Render postgres prefix issue for SQLAlchemy 1.4+
if DB_PATH.startswith("postgres://"):
    DB_PATH = DB_PATH.replace("postgres://", "postgresql://", 1)

engine = create_engine(DB_PATH)


# Custom Glassmorphic Sleek Styles
st.markdown("""
<style>
    /* Global Styles */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=JetBrains+Mono&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .stApp {
        background-color: #0d0f14;
        color: #e2e8f0;
    }
    
    /* Title Styling */
    .dashboard-title {
        background: linear-gradient(135deg, #3b82f6 0%, #10b981 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.6rem;
        margin-bottom: 0.2rem;
    }
    .dashboard-subtitle {
        color: #94a3b8;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }

    /* Glassmorphism Cards */
    .glass-card {
        background: rgba(30, 41, 59, 0.45);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        margin-bottom: 1rem;
    }
    
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        margin: 0.5rem 0;
        background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .metric-title {
        color: #94a3b8;
        font-size: 0.95rem;
        text-transform: uppercase;
        letter-spacing: 0.1rem;
        font-weight: 600;
    }
    
    /* Custom Alerts colors */
    .alert-critical {
        border-left: 6px solid #ef4444;
        background: rgba(239, 68, 68, 0.1);
    }
    
    .alert-medium {
        border-left: 6px solid #f59e0b;
        background: rgba(245, 158, 11, 0.1);
    }
    
    .alert-low {
        border-left: 6px solid #10b981;
        background: rgba(16, 185, 129, 0.1);
    }

    /* Log line output */
    .log-box {
        font-family: 'JetBrains Mono', monospace;
        background-color: #05070a;
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 10px;
        color: #38bdf8;
        font-size: 0.85rem;
        overflow-x: auto;
        white-space: pre-wrap;
    }

</style>
""", unsafe_allow_html=True)


# Database fetching helper functions
def get_table_data(query: str) -> pd.DataFrame:
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn)
            # Standardize timestamp format
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
    except Exception:
        # Table might not exist yet
        return pd.DataFrame()


def resolve_alert_in_db(alert_id: int):
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE alert SET resolved = 1 WHERE id = :id"),
                {"id": alert_id}
            )
        return True
    except Exception as exc:
        st.error(f"Failed to update alert: {exc}")
        return False


# Title & Control Bar
st.markdown("<div class='dashboard-title'>🛡️ SENTINEL PLATFORM</div>", unsafe_allow_html=True)
st.markdown("<div class='dashboard-subtitle'>Autonomous Real-time Security Ingestion, Telemetry, and AI-Engine Anomaly Monitor</div>", unsafe_allow_html=True)

# Sidebar Options
st.sidebar.markdown("### ⚙️ SYSTEM MONITORS")
refresh_rate = st.sidebar.slider("Auto Refresh Rate (seconds)", min_value=5, max_value=60, value=10)
run_auto_refresh = st.sidebar.checkbox("Enable Auto Refresh", value=True)

# Load basic stats
df_alerts = get_table_data("SELECT * FROM alert")
df_api = get_table_data("SELECT * FROM apihealth")
df_queue = get_table_data("SELECT * FROM queuemetrics")
df_server = get_table_data("SELECT * FROM serverhealth")
df_logs = get_table_data("SELECT * FROM systemlog")

# Metric cards calculations
active_alerts_count = len(df_alerts[df_alerts['resolved'] == 0]) if not df_alerts.empty else 0
total_alerts_count = len(df_alerts) if not df_alerts.empty else 0
avg_api_latency = df_api['response_time_ms'].mean() if not df_api.empty else 0.0
total_events_ingested = len(df_alerts) + len(df_api) + len(df_queue) + len(df_server) + len(df_logs)

# 4 Column Metric Cards Layout
m1, m2, m3, m4 = st.columns(4)

with m1:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-title">🔥 Active Alerts</div>
        <div class="metric-value" style="color: {'#ef4444' if active_alerts_count > 0 else '#10b981'};">{active_alerts_count}</div>
        <div style="font-size: 0.85rem; color: #94a3b8;">Total historical alerts: {total_alerts_count}</div>
    </div>
    """, unsafe_allow_html=True)

with m2:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-title">⚡ Latency Profile</div>
        <div class="metric-value" style="color: #60a5fa;">{avg_api_latency:.1f} ms</div>
        <div style="font-size: 0.85rem; color: #94a3b8;">Avg API check response time</div>
    </div>
    """, unsafe_allow_html=True)

with m3:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-title">💾 Events Processed</div>
        <div class="metric-value" style="color: #34d399;">{total_events_ingested}</div>
        <div style="font-size: 0.85rem; color: #94a3b8;">Ingested metric logs count</div>
    </div>
    """, unsafe_allow_html=True)

with m4:
    active_queues = df_queue['queue_name'].nunique() if not df_queue.empty else 0
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-title">🔗 Active Queues</div>
        <div class="metric-value" style="color: #c084fc;">{active_queues}</div>
        <div style="font-size: 0.85rem; color: #94a3b8;">RabbitMQ monitored brokers</div>
    </div>
    """, unsafe_allow_html=True)

# Divider
st.markdown("<hr style='border: 0; border-top: 1px solid rgba(255,255,255,0.05); margin: 2rem 0;' />", unsafe_allow_html=True)

# Main Navigation Tabs
tab_overview, tab_alerts, tab_telemetry, tab_logs = st.tabs([
    "📈 System Dashboard", 
    "🚨 Security Alert Center", 
    "📊 Hardware & API Telemetry", 
    "📋 Service Logs Explorer"
])

# -----------------
# TAB 1: SYSTEM OVERVIEW
# -----------------
with tab_overview:
    st.markdown("### Real-time Platform Core Status")
    
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        # Mini overview map
        st.subheader("Hardware Utilization Heatmap (Latest)")
        if not df_server.empty:
            latest_serv = df_server.sort_values(by='timestamp').groupby('host_name').last().reset_index()
            
            # Draw charts
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name='CPU Usage %',
                x=latest_serv['host_name'], y=latest_serv['cpu_usage_pct'],
                marker_color='#ef4444'
            ))
            fig.add_trace(go.Bar(
                name='RAM Usage %',
                x=latest_serv['host_name'], y=latest_serv['memory_usage_pct'],
                marker_color='#f59e0b'
            ))
            fig.add_trace(go.Bar(
                name='Disk Usage %',
                x=latest_serv['host_name'], y=latest_serv['disk_usage_pct'],
                marker_color='#3b82f6'
            ))
            fig.update_layout(
                barmode='group',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='#e2e8f0',
                margin=dict(l=0, r=0, t=30, b=0),
                height=300,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No server hardware telemetry ingested yet. Run the mock sender to load metrics!")

    with col_right:
        st.subheader("Critical Alerts Breakdown")
        if not df_alerts.empty:
            alert_summary = df_alerts.groupby('severity').size().reset_index(name='count')
            fig_pie = px.pie(
                alert_summary, values='count', names='severity',
                color='severity',
                color_discrete_map={'CRITICAL': '#ef4444', 'MEDIUM': '#f59e0b', 'LOW': '#10b981'},
                hole=0.4
            )
            fig_pie.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='#e2e8f0',
                margin=dict(l=0, r=0, t=10, b=0),
                height=250,
                showlegend=False
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.success("No active security alerts recorded!")

# -----------------
# TAB 2: ALERTS SECURITY CENTER
# -----------------
with tab_alerts:
    st.markdown("### Security Failure Incident Response Control")
    
    # Options to filter
    alert_filter = st.selectbox("Status Filter", ["Active Alerts Only", "Resolved Alerts Only", "All Alerts"])
    
    if not df_alerts.empty:
        # Apply filter
        if alert_filter == "Active Alerts Only":
            filtered_alerts = df_alerts[df_alerts['resolved'] == 0]
        elif alert_filter == "Resolved Alerts Only":
            filtered_alerts = df_alerts[df_alerts['resolved'] == 1]
        else:
            filtered_alerts = df_alerts
            
        # Re-sort: CRITICAL first, then newest
        filtered_alerts['severity_weight'] = filtered_alerts['severity'].map({'CRITICAL': 3, 'MEDIUM': 2, 'LOW': 1})
        filtered_alerts = filtered_alerts.sort_values(by=['severity_weight', 'timestamp'], ascending=[False, False])
        
        if filtered_alerts.empty:
            st.success("No alerts found matching this filter.")
        else:
            for idx, row in filtered_alerts.iterrows():
                sev = row['severity']
                card_style = "alert-critical" if sev == "CRITICAL" else "alert-medium" if sev == "MEDIUM" else "alert-low"
                
                # Setup structure
                col_alert, col_action = st.columns([5, 1])
                with col_alert:
                    st.markdown(f"""
                    <div class="glass-card {card_style}">
                        <div style="font-size: 0.85rem; font-weight: bold; color: {'#ef4444' if sev=='CRITICAL' else '#f59e0b' if sev=='MEDIUM' else '#10b981'};">
                            [{sev.upper()}] FROM {row['source'].upper()}
                        </div>
                        <h4 style="margin: 5px 0;">{row['title']}</h4>
                        <p style="color: #94a3b8; font-size: 0.95rem; margin-bottom: 5px;">{row['description']}</p>
                        <small style="color: #64748b;">Alert Timestamp: {row['timestamp'].strftime('%Y-%m-%d %H:%M:%S UTC')}</small>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_action:
                    st.write("")
                    st.write("")
                    if row['resolved'] == 0:
                        # Interactive Resolve Button
                        btn_key = f"resolve_{row['id']}"
                        if st.button("Mark Resolved ✅", key=btn_key, use_container_width=True):
                            if resolve_alert_in_db(row['id']):
                                st.toast(f"Alert ID {row['id']} marked as resolved!", icon="✅")
                                time.sleep(1) # short sleep to give feedback before refresh
                                st.rerun()
                    else:
                        st.markdown("<div style='color: #10b981; font-weight: bold; text-align: center; margin-top: 15px;'>Resolved ✓</div>", unsafe_allow_html=True)
    else:
        st.success("Perfect. No security incidents recorded in the database.")

# -----------------
# TAB 3: TELEMETRY ANALYTICS
# -----------------
with tab_telemetry:
    st.markdown("### Deep Hardware Metrics & API Latency Telemetry")
    
    col_tele_left, col_tele_right = st.columns(2)
    
    with col_tele_left:
        st.subheader("Host Core Metrics Over Time")
        if not df_server.empty:
            hosts = df_server['host_name'].unique()
            selected_host = st.selectbox("Filter by Host IP/Name", hosts)
            host_df = df_server[df_server['host_name'] == selected_host].sort_values('timestamp')
            
            # Interactive Line Graph
            fig_host = px.line(
                host_df, x='timestamp', y=['cpu_usage_pct', 'memory_usage_pct', 'disk_usage_pct'],
                labels={'value': 'Usage Percentage (%)', 'timestamp': 'Time'},
                title=f"Hardware Usage Trend for {selected_host}"
            )
            fig_host.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='#e2e8f0',
                margin=dict(l=0, r=0, t=40, b=0)
            )
            st.plotly_chart(fig_host, use_container_width=True)
        else:
            st.info("Waiting for hardware telemetry...")
            
    with col_tele_right:
        st.subheader("API Latency (Response Time ms)")
        if not df_api.empty:
            apis = df_api['service_name'].unique()
            selected_api = st.selectbox("Filter by API Service", apis)
            api_df = df_api[df_api['service_name'] == selected_api].sort_values('timestamp')
            
            fig_api_lat = px.area(
                api_df, x='timestamp', y='response_time_ms',
                color_discrete_sequence=['#10b981'],
                title=f"Response Time Profile for '{selected_api}'"
            )
            fig_api_lat.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='#e2e8f0',
                margin=dict(l=0, r=0, t=40, b=0)
            )
            st.plotly_chart(fig_api_lat, use_container_width=True)
        else:
            st.info("Waiting for API health telemetry...")

    # Second row of charts for Queue Stats
    st.markdown("<br/>", unsafe_allow_html=True)
    st.subheader("Message Queue Load Profile")
    if not df_queue.empty:
        q_cols = st.columns(2)
        with q_cols[0]:
            queues = df_queue['queue_name'].unique()
            selected_q = st.selectbox("Filter by Queue Name", queues)
            q_df = df_queue[df_queue['queue_name'] == selected_q].sort_values('timestamp')
            
            fig_q = px.line(
                q_df, x='timestamp', y=['total_messages', 'unacked_messages'],
                title=f"Message Accumulation profile for '{selected_q}'"
            )
            fig_q.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='#e2e8f0',
                margin=dict(l=0, r=0, t=40, b=0)
            )
            st.plotly_chart(fig_q, use_container_width=True)
        with q_cols[1]:
            # Consumer distribution bar chart
            latest_q = df_queue.sort_values(by='timestamp').groupby('queue_name').last().reset_index()
            fig_c = px.bar(
                latest_q, x='queue_name', y='consumers',
                color='consumers',
                color_continuous_scale=px.colors.sequential.Viridis,
                title="Current Consumer Headcount across Queues"
            )
            fig_c.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='#e2e8f0',
                margin=dict(l=0, r=0, t=40, b=0)
            )
            st.plotly_chart(fig_c, use_container_width=True)
    else:
        st.info("Waiting for queue metrics telemetry...")

# -----------------
# TAB 4: SERVICE LOGS EXPLORER
# -----------------
with tab_logs:
    st.markdown("### Microservice Cluster Logs Diagnostic Console")
    
    # Filter logs
    log_filter_cols = st.columns(3)
    with log_filter_cols[0]:
        selected_log_lvl = st.multiselect(
            "Filter Log Level", 
            ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            default=["WARNING", "ERROR", "CRITICAL"]
        )
    with log_filter_cols[1]:
        log_srv = df_logs['service_name'].unique() if not df_logs.empty else []
        selected_log_srv = st.multiselect("Filter Service Name", log_srv, default=log_srv)
    with log_filter_cols[2]:
        search_query = st.text_input("Log Msg Keyword Search", "")

    if not df_logs.empty:
        # Filter logic
        filtered_logs = df_logs.copy()
        if selected_log_lvl:
            filtered_logs = filtered_logs[filtered_logs['log_level'].isin(selected_log_lvl)]
        if selected_log_srv:
            filtered_logs = filtered_logs[filtered_logs['service_name'].isin(selected_log_srv)]
        if search_query:
            filtered_logs = filtered_logs[filtered_logs['message'].str.contains(search_query, case=False)]
            
        filtered_logs = filtered_logs.sort_values('timestamp', ascending=False).head(200)
        
        if filtered_logs.empty:
            st.info("No logs match the criteria.")
        else:
            # Display logs in high-fidelity console log output style
            log_output = ""
            for idx, log in filtered_logs.iterrows():
                time_str = log['timestamp'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                level = log['log_level']
                color_symbol = "🔴" if level == "CRITICAL" else "❌" if level == "ERROR" else "⚠️" if level == "WARNING" else "ℹ️"
                
                log_output += f"[{time_str}] {color_symbol} {level:<8} [{log['service_name'].upper()}] - {log['message']}\n"
                
            st.markdown(f"<pre class='log-box'>{log_output}</pre>", unsafe_allow_html=True)
    else:
        st.info("No microservice system logs ingested yet.")

# Auto refresh handler
if run_auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
