import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import os
from datetime import datetime
st.set_page_config(
    page_title="Delivery Bot Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)
CSV_FILE = os.path.join(os.path.dirname(__file__), "delivery_log.csv")
REFRESH_RATE = 5  
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    h1 {
        color: #ff4b4b;
    }
    .stMetric {
        background-color: #262730;
        padding: 10px;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)
st.sidebar.header("Filters")
base_dir = os.path.dirname(__file__)
hti_logo_path = os.path.join(base_dir, "hti_logo.jpg")
if os.path.exists(hti_logo_path):
    st.sidebar.image(hti_logo_path, width=150)
st.sidebar.markdown("**Higher Technological Institute**")
st.sidebar.markdown("*10th of Ramadan City*")
st.sidebar.markdown("---")
col_logo, col_title = st.columns([1, 4])
with col_logo:
    robot_logo_path = None
    for name in ["robot_logo_dashboard.png", "robot_logo_inverted.png",  "robot_logo_white.png", "robot_logo_black.png"]:
        p = os.path.join(base_dir, name)
        if os.path.exists(p):
            robot_logo_path = p
            break
    if robot_logo_path:
        st.image(robot_logo_path, width=180)
    else:
        st.write("🤖")
with col_title:
    st.title("Autonomous Delivery Dashboard")
    st.markdown("Real-time monitoring of delivery missions.")
today = datetime.now().date()
@st.cache_data(ttl=5)
def load_data():
    if not os.path.exists(CSV_FILE):
        return pd.DataFrame()
    try:
        df = pd.read_csv(CSV_FILE)
        df['Date_Full'] = pd.to_datetime(df['Date_Full'], errors='coerce')
        df = df.dropna(subset=['Date_Full'])
        df['Date_Full'] = df['Date_Full'].dt.date
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()
df = load_data()
if df.empty:
    st.warning("⚠️ No data found. Waiting for first delivery...")
    st.stop()
st.sidebar.subheader("📅 Time Period")
filter_option = st.sidebar.radio(
    "Select Range:",
    ["All Time", "Today", "Last 7 Days", "Last 30 Days", "Last Year", "Custom Range"]
)
filtered_df = df.copy()
today_date = datetime.now().date()
filtered_df['Date_Full'] = pd.to_datetime(filtered_df['Date_Full'], errors='coerce').dt.date
filtered_df = filtered_df.dropna(subset=['Date_Full'])
if filter_option == "Today":
    filtered_df = filtered_df[filtered_df['Date_Full'] == today_date]
elif filter_option == "Last 7 Days":
    start_date = today_date - pd.Timedelta(days=7)
    filtered_df = filtered_df[filtered_df['Date_Full'] >= start_date]
elif filter_option == "Last 30 Days":
    start_date = today_date - pd.Timedelta(days=30)
    filtered_df = filtered_df[filtered_df['Date_Full'] >= start_date]
elif filter_option == "Last Year":
    start_date = today_date - pd.Timedelta(days=365)
    filtered_df = filtered_df[filtered_df['Date_Full'] >= start_date]
elif filter_option == "Custom Range":
    min_date = filtered_df['Date_Full'].min()
    max_date = filtered_df['Date_Full'].max()
    date_range = st.sidebar.date_input("Select Date Range", [min_date, max_date])
    if len(date_range) == 2:
        start_d, end_d = date_range
        filtered_df = filtered_df[
            (filtered_df['Date_Full'] >= start_d) & 
            (filtered_df['Date_Full'] <= end_d)
        ]
status_options = ["All"] + list(df['Order_Final_Status'].unique())
selected_status = st.sidebar.selectbox("Filter Status", status_options)
if selected_status != "All":
    filtered_df = filtered_df[filtered_df['Order_Final_Status'] == selected_status]
kp1, kp2, kp3, kp4 = st.columns(4)
total_orders = len(filtered_df)
delivered_count = len(filtered_df[filtered_df['Order_Final_Status'] == 'Delivered'])
success_rate = (delivered_count / total_orders * 100) if total_orders > 0 else 0
if not filtered_df.empty:
    top_loc = filtered_df['Target_Location'].value_counts().idxmax()
else:
    top_loc = "N/A"
avg_duration = 0.0
if not filtered_df.empty and 'Trip_Duration_Min' in filtered_df.columns:
    durs = pd.to_numeric(filtered_df['Trip_Duration_Min'], errors='coerce')
    avg_duration = durs.mean()
    if pd.isna(avg_duration): avg_duration = 0.0
kp1.metric("📦 Total Orders", total_orders)
kp2.metric("✅ Success Rate", f"{success_rate:.1f}%")
kp3.metric("📍 Top Destination", top_loc)
kp4.metric("🕒 Avg Trip Duration", f"{avg_duration:.1f} min")
st.divider()
col1, col2 = st.columns([2, 1])
with col1:
    st.subheader("📊 Orders Over Time")
    if not filtered_df.empty:
        loc_counts = filtered_df['Target_Location'].value_counts().reset_index()
        loc_counts.columns = ['Location', 'Count']
        fig_bar = px.bar(loc_counts, x='Location', y='Count', color='Location', 
                         title="Orders by Destination", template="plotly_dark")
        st.plotly_chart(fig_bar, key="bar_chart")
with col2:
    st.subheader("📉 Order Status")
    if not filtered_df.empty:
        status_counts = filtered_df['Order_Final_Status'].value_counts()
        fig_pie = px.pie(values=status_counts.values, names=status_counts.index, 
                         title="Delivery Outcome", hole=0.4, template="plotly_dark")
        fig_pie.update_traces(textposition='inside', textinfo='percent')
        fig_pie.update_layout(
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.2,
                xanchor="center",
                x=0.5
            )
        )
        st.plotly_chart(fig_pie, key="pie_chart")
st.subheader("🕒 Busy Hours Analysis")
if not filtered_df.empty:
    def get_hour(t_str):
        try:
            return int(str(t_str).split(':')[0])
        except:
            return 0
    hours = filtered_df['Time_Arrival'].apply(get_hour)
    hour_counts = hours.value_counts().sort_index().reset_index()
    hour_counts.columns = ['Hour', 'Orders']
    fig_line = px.area(hour_counts, x='Hour', y='Orders', 
                       title="Order Volume by Hour of Day", 
                       template="plotly_dark", markers=True)
    fig_line.update_xaxes(tickmode='linear', dtick=1)
    st.plotly_chart(fig_line, key="hourly_chart")
st.subheader("📋 Recent Activity Log")
def highlight_status(val):
    color = '#28a745' if val == 'Delivered' else '#dc3545'
    return f'color: {color}; font-weight: bold;'
try:
    st.dataframe(
        filtered_df[['Time_Arrival', 'Order_ID', 'Target_Location', 'Order_Final_Status', 'Date_Full']]
        .sort_values(by='Time_Arrival', ascending=False)
        .style.applymap(highlight_status, subset=['Order_Final_Status']),
        hide_index=True
    )
except AttributeError:
    # Fallback for systems where Jinja2 is missing or incompatible with Pandas
    st.dataframe(
        filtered_df[['Time_Arrival', 'Order_ID', 'Target_Location', 'Order_Final_Status', 'Date_Full']]
        .sort_values(by='Time_Arrival', ascending=False),
        hide_index=True
    )
st.sidebar.markdown("---")
csv_data = filtered_df.to_csv(index=False).encode('utf-8')
st.sidebar.download_button(
    label="📥 Download CSV (Excel)",
    data=csv_data,
    file_name="delivery_report.csv",
    mime="text/csv"
)
from fpdf import FPDF
import tempfile
from fpdf import FPDF
import tempfile
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg') 
class PDFReport(FPDF):
    def header(self):
        base_dir = os.path.dirname(__file__)
        hti_logo = os.path.join(base_dir, "hti_logo.jpg")
        if os.path.exists(hti_logo):
            self.image(hti_logo, 10, 5, 25) 
        robot_logo_path = None
        for name in ["robot_logo_dashboard.png", "robot_logo_orig.png", "robot_logo_black.png"]:
            p = os.path.join(base_dir, name)
            if os.path.exists(p):
                robot_logo_path = p
                break
        if robot_logo_path:
             self.image(robot_logo_path, 175, 5, 25)
        self.set_y(10) 
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Autonomous Delivery Report', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(0, 5, 'Higher Technological Institute', 0, 1, 'C')
        self.ln(15) 
        self.set_draw_color(0, 80, 180) 
        self.set_line_width(1)
        self.line(10, 35, 200, 35)
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Page {self.page_no()} - Generated by Delivery Bot Dashboard', 0, 0, 'C')
def create_pdf_charts(df):
    """Generates temporary chart images for PDF"""
    chart_paths = {}
    if not df.empty:
        status_counts = df['Order_Final_Status'].value_counts()
        fig1, ax1 = plt.subplots(figsize=(6, 6)) 
        color_map = {
            'Delivered': '#00C851',    
            'In Progress': '#dc3545',  
            'Pending': '#dc3545',      
            'Failed': '#343a40',       
            'Cancelled': '#6c757d'     
        }
        colors = [color_map.get(status, '#17a2b8') for status in status_counts.index]
        explode = [0.05] * len(status_counts)
        def make_autopct(pct):
            return ('%1.1f%%' % pct) if pct > 5 else ''
        wedges, texts, autotexts = ax1.pie(
            status_counts, 
            labels=None, 
            autopct=make_autopct, 
            startangle=90, 
            colors=colors,
            pctdistance=0.85, 
            explode=explode,
            radius=1.1
        )
        for text in autotexts:
            text.set_color('white')
            text.set_weight('bold')
        ax1.axis('equal')
        plt.title("Delivery Success Rate", fontsize=14, pad=10)
        total_count = status_counts.sum()
        legend_labels = [f"{name} ({val/total_count*100:.1f}%)" for name, val in zip(status_counts.index, status_counts.values)]
        ax1.legend(
            wedges, 
            legend_labels,
            title="Status",
            loc="upper center", 
            bbox_to_anchor=(0.5, -0.05),
            ncol=2
        )
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            plt.savefig(tmp.name, bbox_inches='tight')
            chart_paths['pie'] = tmp.name
        plt.close(fig1)
    if not df.empty:
        loc_counts = df['Target_Location'].value_counts()
        fig2, ax2 = plt.subplots(figsize=(6, 6)) 
        ax2.bar(loc_counts.index, loc_counts.values, color='#007bff')
        plt.title("Orders by Destination", fontsize=14)
        plt.xlabel("Location")
        plt.ylabel("Count")
        plt.xticks(rotation=45, ha='right')
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            plt.savefig(tmp.name, bbox_inches='tight')
            chart_paths['bar'] = tmp.name
        plt.close(fig2)
    return chart_paths
def generate_pdf(dataframe, period_name):
    pdf = PDFReport()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_y(40) 
    pass
def generate_pdf(dataframe, period_name):
    pdf = PDFReport()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_y(40) 
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(0)
    pdf.cell(0, 8, f"Period: {period_name}", 0, 1)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 0, 1)
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Executive Summary", 0, 1)
    total = len(dataframe)
    delivered = len(dataframe[dataframe['Order_Final_Status'] == 'Delivered'])
    success_pct = (delivered / total * 100) if total > 0 else 0
    avg_dur = 0.0
    if not dataframe.empty and 'Trip_Duration_Min' in dataframe.columns:
         dems = pd.to_numeric(dataframe['Trip_Duration_Min'], errors='coerce')
         avg_dur = dems.mean()
         if pd.isna(avg_dur): avg_dur = 0.0
    card_y = pdf.get_y() + 2
    card_w = 60
    card_h = 25
    gap = 5
    pdf.set_fill_color(240, 245, 255) 
    pdf.rect(10, card_y, card_w, card_h, 'F')
    pdf.set_xy(10, card_y + 5)
    pdf.set_font("Arial", '', 10)
    pdf.cell(card_w, 5, "Total Missions", 0, 2, 'C')
    pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(0, 80, 180)
    pdf.cell(card_w, 10, f"{total}", 0, 0, 'C')
    pdf.set_fill_color(240, 255, 240) 
    pdf.rect(10 + card_w + gap, card_y, card_w, card_h, 'F')
    pdf.set_xy(10 + card_w + gap, card_y + 5)
    pdf.set_font("Arial", '', 10)
    pdf.set_text_color(0)
    pdf.cell(card_w, 5, "Success Rate", 0, 2, 'C')
    pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(40, 167, 69)
    pdf.cell(card_w, 10, f"{success_pct:.1f}%", 0, 0, 'C')
    pdf.set_fill_color(255, 250, 240)
    pdf.rect(10 + 2*(card_w + gap), card_y, card_w, card_h, 'F')
    pdf.set_xy(10 + 2*(card_w + gap), card_y + 5)
    pdf.set_font("Arial", '', 10)
    pdf.set_text_color(0)
    pdf.cell(card_w, 5, "Avg Trip Duration", 0, 2, 'C')
    pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(255, 140, 0)
    pdf.cell(card_w, 10, f"{avg_dur:.1f} min", 0, 0, 'C')
    pdf.set_y(card_y + card_h + 45)
    pdf.set_font("Arial", 'B', 14)
    pdf.set_text_color(0)
    pdf.cell(0, 10, "Analytics", 0, 1)
    charts = create_pdf_charts(dataframe)
    start_y_charts = pdf.get_y()
    if 'pie' in charts:
        pdf.image(charts['pie'], x=8, y=start_y_charts, w=95) 
    if 'bar' in charts:
        pdf.image(charts['bar'], x=108, y=start_y_charts, w=95)
    pdf.add_page() 
    pdf.set_y(45) 
    pdf.set_font("Arial", 'B', 14)
    pdf.set_text_color(0, 50, 100)
    pdf.cell(0, 10, "Mission Logs (Recent 50)", 0, 1)
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 8) 
    pdf.set_fill_color(50, 50, 50) 
    pdf.set_text_color(255)
    cols = [
        ("Date", 25), ("Time", 20), ("Order ID", 30), ("Location", 30), 
        ("Journey", 20), ("Verification", 40), ("Status", 25)
    ]
    for col_name, width in cols:
        pdf.cell(width, 8, col_name, 1, 0, 'C', True)
    pdf.ln()
    pdf.set_font("Arial", '', 8)
    pdf.set_text_color(0)
    subset = dataframe.head(50)
    fill = False
    for index, row in subset.iterrows():
        pdf.set_fill_color(240, 240, 240)
        date_str = str(row.get('Date_Full', 'N/A'))
        t_arr = str(row.get('Time_Arrival', 'N/A'))
        oid = str(row.get('Order_ID', 'N/A'))[:6] + ".." 
        loc = str(row.get('Target_Location', 'N/A'))
        if len(loc) > 12: loc = loc[:10] + ".."
        dur = str(row.get('Trip_Duration_Min', '0.0')) + "m"
        qr_stat = str(row.get('QR_Scan_Status', ''))
        gest_stat = str(row.get('Client_Gesture_Status', ''))
        verify_txt = "N/A"
        if "Verified" in qr_stat:
            if "Thumb" in gest_stat or "Like" in gest_stat:
                verify_txt = "QR + Like" 
            else:
                verify_txt = "QR"
        elif "Failed" in qr_stat:
             verify_txt = "Failed"
        status = str(row.get('Order_Final_Status', 'N/A'))
        pdf.cell(cols[0][1], 7, date_str, 1, 0, 'C', fill)
        pdf.cell(cols[1][1], 7, t_arr, 1, 0, 'C', fill)
        pdf.cell(cols[2][1], 7, oid, 1, 0, 'C', fill)
        pdf.cell(cols[3][1], 7, loc, 1, 0, 'C', fill)
        pdf.cell(cols[4][1], 7, dur, 1, 0, 'C', fill)
        pdf.cell(cols[5][1], 7, verify_txt, 1, 0, 'C', fill)
        if status == 'Delivered':
            pdf.set_text_color(0, 150, 0)
            pdf.set_font("Arial", 'B', 8)
        else:
            pdf.set_text_color(200, 0, 0)
            pdf.set_font("Arial", 'B', 8)
        pdf.cell(cols[6][1], 7, status, 1, 1, 'C', fill)
        pdf.set_text_color(0)
        pdf.set_font("Arial", '', 8)
        fill = not fill
    for p in charts.values():
        if os.path.exists(p):
            os.remove(p)
    return pdf
if st.sidebar.button("📄 Generate PDF Report"):
    with st.spinner("Generating PDF..."):
        try:
            pdf = generate_pdf(filtered_df, filter_option)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                pdf.output(tmp_file.name)
                tmp_path = tmp_file.name
            with open(tmp_path, "rb") as f:
                pdf_bytes = f.read()
            st.sidebar.success("PDF Generated!")
            st.sidebar.download_button(
                label="⬇️ Download PDF",
                data=pdf_bytes,
                file_name=f"Report_{filter_option.replace(' ', '_')}.pdf",
                mime="application/pdf"
            )
            os.remove(tmp_path)
        except Exception as e:
            st.sidebar.error(f"Failed to generate PDF: {e}")
st.sidebar.markdown("---")
if st.sidebar.checkbox("✅ Auto-Refresh (5s)", value=True):
    time.sleep(5)
    st.rerun()
if st.sidebar.button("🔄 Manual Refresh"):
    st.rerun()
