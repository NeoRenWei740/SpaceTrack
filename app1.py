import streamlit as st
from spacetrack import SpaceTrackClient
import spacetrack.operators as op
from skyfield.api import EarthSatellite, load
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import math

# --- Website Page Config ---
st.set_page_config(page_title="Orbital Tracker", layout="wide")

st.title("🛰️ Satellite TLE Data Explorer")
st.markdown("Extract and visualize orbital elements directly from Space-Track.org")

# --- Sidebar Inputs ---
st.sidebar.header("Settings")
st.sidebar.info("Enter your Space-Track.org credentials below.")
ST_USER = st.sidebar.text_input("Username (Email)")
ST_PASS = st.sidebar.text_input("Password", type="password")

st.sidebar.markdown("---")
st.sidebar.header("Tracking Parameters")

# Default value shows 3 satellites
sat_input = st.sidebar.text_input("NORAD IDs (comma separated)", value="25544, 43013, 48274")

# Set the absolute minimum date to Jan 1, 2003, and the maximum to today
min_allowed_date = datetime(2003, 1, 1).date()
max_allowed_date = datetime.now().date()

start_date = st.sidebar.date_input(
    "Start Date", 
    value=max_allowed_date - timedelta(days=7), # Default to 7 days ago
    min_value=min_allowed_date,
    max_value=max_allowed_date
)

end_date = st.sidebar.date_input(
    "End Date", 
    value=max_allowed_date,                     # Default to today
    min_value=min_allowed_date,
    max_value=max_allowed_date
)

run_button = st.sidebar.button("Generate Graphs")

# --- Backend Logic ---
if run_button:
    if not ST_USER or not ST_PASS:
        st.error("Please enter your Space-Track credentials in the sidebar.")
    else:
        try:
            with st.spinner("Fetching data from Space-Track..."):
                st_client = SpaceTrackClient(identity=ST_USER, password=ST_PASS)
                
                # Clean and parse IDs
                sat_list = [s.strip() for s in sat_input.split(",") if s.strip()]
                
                # Fetch TLEs
                drange = op.inclusive_range(start_date, end_date)
                tle_data = st_client.gp_history(norad_cat_id=sat_list, epoch=drange, format='tle')

            if not tle_data:
                st.warning("No data found for these satellites in the selected range.")
            else:
                # Calculate Orbits (Skyfield)
                ts = load.timescale()
                lines = tle_data.strip().split('\n')
                plot_data = {sat: {'epoch': [], 'inc': [], 'raan': [], 'ecc': [], 'arg_pe': [], 'mean_anom': [], 'mean_mo': [], 'lon': []} for sat in sat_list}

                for i in range(0, len(lines), 2):
                    if i+1 >= len(lines): break
                    l1, l2 = lines[i].strip(), lines[i+1].strip()
                    nid = str(int(l1[2:7]))
                    if nid not in plot_data: continue

                    sat_obj = EarthSatellite(l1, l2, nid, ts)
                    t = sat_obj.epoch
                    
                    # Calculate elements
                    plot_data[nid]['epoch'].append(t.utc_datetime())
                    plot_data[nid]['inc'].append(math.degrees(sat_obj.model.inclo))
                    plot_data[nid]['raan'].append(math.degrees(sat_obj.model.nodeo))
                    plot_data[nid]['ecc'].append(sat_obj.model.ecco)
                    plot_data[nid]['arg_pe'].append(math.degrees(sat_obj.model.argpo))
                    plot_data[nid]['mean_anom'].append(math.degrees(sat_obj.model.mo))
                    plot_data[nid]['mean_mo'].append(sat_obj.model.no_kozai * 1440 / (2 * math.pi))
                    plot_data[nid]['lon'].append(sat_obj.at(t).subpoint().longitude.degrees)

                # --- Create Plotly Visuals ---
                fig = make_subplots(
                    rows=7, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                    subplot_titles=("Inclination (°)", "RAAN (°)", "Eccentricity", "Arg of Perigee (°)", "Mean Anomaly (°)", "Mean Motion", "Longitude (°)")
                )

                # --- UPDATED: Red, Blue, Green as the first three colors ---
                sat_colors = [
                    '#D62728', # Red
                    '#1F77B4', # Blue
                    '#2CA02C', # Green
                    '#FF7F0E', # Orange
                    '#9467BD', # Purple
                    '#17BECF', # Cyan
                    '#E377C2', # Pink
                    '#BCBD22', # Olive/Yellow
                    '#8C564B', # Brown
                    '#FF9896'  # Light Red
                ]

                for idx, sat in enumerate(sat_list):
                    if not plot_data[sat]['epoch']: continue
                    
                    # Pick a color based on the satellite's position in the list
                    current_color = sat_colors[idx % len(sat_colors)]
                    
                    params = [('inc', 1), ('raan', 2), ('ecc', 3), ('arg_pe', 4), ('mean_anom', 5), ('mean_mo', 6), ('lon', 7)]
                    for p_key, row in params:
                        fig.add_trace(go.Scatter(
                            x=plot_data[sat]['epoch'], y=plot_data[sat][p_key],
                            name=f"Sat {sat}", legendgroup=f"group_{sat}",
                            showlegend=(True if row == 1 else False),
                            mode='lines+markers',
                            line=dict(color=current_color),     
                            marker=dict(color=current_color)    
                        ), row=row, col=1)

                fig.update_layout(
                    height=1500, 
                    hovermode="x unified", 
                    template="plotly_dark", 
                    margin=dict(t=80, b=50, l=50, r=50)
                )
                
                # Add borders around all subplots
                fig.update_xaxes(showline=True, linewidth=1, linecolor='gray', mirror=True)
                fig.update_yaxes(showline=True, linewidth=1, linecolor='gray', mirror=True)
                
                # Push the subplot titles up away from the border
                fig.update_annotations(yshift=15) 
                
                # Output to Website
                st.plotly_chart(fig, use_container_width=True)
                st.success("Graphs generated! You can click satellite names in the legend to hide/show them.")

        except Exception as e:
            st.error(f"Error: {e}")