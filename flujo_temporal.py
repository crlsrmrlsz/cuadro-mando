# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 19:19:18 2025

@author: flipe
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# Global constant for the minimum percentage to show a flow
MIN_PERCENTAGE_SHOW = 2

# ------------------------------------------
# Helper Functions
# ------------------------------------------
def generate_flow_info(flow, idx, state_names):
    """
    Given a flow record, its index, and the mapping of state names,
    return a tuple containing:
      - code (e.g. "F01"),
      - list of state names,
      - full sequence as a string,
      - label string for display.
    """
    code = f"F{idx:02d}"
    states = [str(state_names.get(s, f"S-{s}")) for s in flow['sequence']]
    full_sequence = " → ".join(states)
    label = f"{code}: ({flow['percentage']}%) {full_sequence} "
    return code, states, full_sequence, label


@st.cache_data
def process_flows(_tramites, selected_states, selected_procedure, selected_dates):
    # Process tramites data
    tramites_sorted = _tramites.sort_values(['id_exp', 'fecha_tramite'])
    
    # Calculate step durations
    tramites_sorted['next_fecha'] = tramites_sorted.groupby('id_exp')['fecha_tramite'].shift(-1)
    tramites_sorted['duration'] = (
        (tramites_sorted['next_fecha'] - tramites_sorted['fecha_tramite'])
        .dt.total_seconds() / 86400
    ).fillna(0)  # Explicitly handle the last step duration
    
    # Group by expedition
    process_states = tramites_sorted.groupby('id_exp').agg(
        all_states=('num_tramite', lambda x: list(x.astype(int))),
        durations=('duration', list)
    ).reset_index()
    
    # Filter processes that contain at least one of the selected states
    contains_mask = process_states['all_states'].apply(
        lambda x: any(s in selected_states for s in x)
    )
    filtered_processes = process_states[contains_mask]
    
    # Total processes (for percentage calculation)
    total_processes = len(filtered_processes)
    
    # Count sequence frequencies (convert lists to tuples to make them hashable)
    seq_counts = filtered_processes['all_states'].apply(tuple).value_counts().reset_index()
    seq_counts.columns = ['sequence', 'count']
    seq_counts['percentage'] = (seq_counts['count'] / total_processes * 100).round(1)
    
    # Select only those sequences that meet the minimum percentage threshold
    major_seqs = seq_counts[seq_counts['percentage'] >= MIN_PERCENTAGE_SHOW].sort_values('count', ascending=False)
    
    # Calculate accurate per-transition averages
    flow_data = []
    for seq_tuple in major_seqs['sequence']:
        seq = list(seq_tuple)
        seq_len = len(seq)
        
        # Get matching processes
        seq_mask = filtered_processes['all_states'].apply(tuple) == seq_tuple
        seq_durations = filtered_processes[seq_mask]['durations']
        
        # Align durations (only consider n-1 durations for a sequence of n states)
        aligned_durations = [dur_list[:seq_len - 1] for dur_list in seq_durations]
        
        # Calculate averages for each transition (ignoring NaN)
        avg_durations = np.nanmean(aligned_durations, axis=0).tolist() if aligned_durations else []
        
        # Retrieve count and percentage from major_seqs
        matching_row = major_seqs[major_seqs['sequence'] == seq_tuple].iloc[0]
        flow_data.append({
            'sequence': seq,
            'count': matching_row['count'],
            'percentage': matching_row['percentage'],
            'durations': avg_durations
        })
    
    return flow_data, total_processes    


def create_visualizations(flow_data, state_names):
    """
    Build legend and visualization data frames using the helper function.
    """
    legend_data = []
    viz_data = []
    
    for idx, flow in enumerate(flow_data, 1):
        code, states, full_sequence, _ = generate_flow_info(flow, idx, state_names)
        transitions = [f"{states[i]} → {states[i+1]}" for i in range(len(states) - 1)]
        
        legend_data.append({
            'Code': code,
            'Sequence': full_sequence,
            'Percentage': f"{flow['percentage']}%",
            'Total': flow['count'],
            'Avg Duration': f"{sum(flow['durations']):.0f} días"
        })
        
        for transition, duration in zip(transitions, flow['durations']):
            viz_data.append({
                'Flow': code,
                'Transition': transition,
                'Duration': duration,
                'Percentage': flow['percentage']
            })
    
    return pd.DataFrame(legend_data), pd.DataFrame(viz_data)

# ------------------------------------------
# INTERFACE / USER INTERFACE
# ------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "Flujos principales", 
    "Diagrama de Flujo",
    #"Diagrama Sankey",
    "Complejidad"
])

# Validate session state
if "filtered_data" not in st.session_state:
    st.error("Cargue los datos desde la página principal primero.")

# Get required data from session state
state_names = st.session_state.estados.set_index('NUMTRAM')['DENOMINACION_SIMPLE'].to_dict()
selected_states = [int(s) for s in st.session_state.selected_final_states]

# Process data with caching
flow_data, total = process_flows(
    st.session_state.filtered_data['tramites'],
    selected_states,
    st.session_state.selected_procedure,
    st.session_state.selected_dates
)

if not flow_data:
    st.warning(f"No hay flujos que cumplan el criterio del {MIN_PERCENTAGE_SHOW}%")

# -------------------------------
# TAB 1: Flow Analysis & Charts
# -------------------------------
with tab1:
    st.subheader("Análisis de Flujos Principales")
    st.markdown(
        f"Se muestran los flujos que representan más del {MIN_PERCENTAGE_SHOW}% de los procesos finalizados, "
        "de acuerdo a los estados finales seleccionados y en el rango de fechas seleccionado."
    )
    
    # Create visualizations
    legend_df, viz_df = create_visualizations(flow_data, state_names)
    
    # --- Left Chart: Percentage Bar Chart ---
    df_perc = viz_df.drop_duplicates('Flow')
    
    # Build mapping dictionaries for hover information
    total_mapping = legend_df.set_index('Code')['Total'].to_dict()
    avg_duration_mapping = legend_df.set_index('Code')['Avg Duration'].to_dict()
    
    fig_perc = go.Figure()
    fig_perc.add_trace(go.Bar(
        x=df_perc['Percentage'],
        y=df_perc['Flow'],
        orientation='h',
        text=df_perc['Percentage'].apply(lambda x: f"{x:.1f}%"),
        textposition='outside',
        customdata=df_perc['Flow'].apply(
            lambda x: [total_mapping.get(x, ''), avg_duration_mapping.get(x, '')]
        ).tolist(),
        hovertemplate="<b>Total expedientes:</b> %{customdata[0]}<br>"
                      "<b>Duración media:</b> %{customdata[1]}<extra></extra>",
        marker_color='#1f77b4'
    ))
    
    max_perc = df_perc['Percentage'].max()
    fig_perc.update_layout(
        height=400,
        template='plotly_white',
        margin=dict(l=20, r=10, t=20, b=20),
        xaxis_title="% de Procesos",
        yaxis=dict(title='% de Procesos', autorange="reversed"),
        xaxis_range=[0, max_perc * 1.2]
    )
    
    # --- Right Chart: Duration Stacked Bar Chart ---
    # Create a fixed color map for transitions
    transition_colors = {}
    color_palette = px.colors.qualitative.Set3
    for i, transition in enumerate(viz_df['Transition'].unique()):
        transition_colors[transition] = color_palette[i % len(color_palette)]
    
    fig_dur = go.Figure()
    for flow, group in viz_df.groupby('Flow', sort=False):
        cumulative = 0  
        for _, row in group.iterrows():
            fig_dur.add_trace(go.Bar(
                x=[row['Duration']],
                y=[flow],
                base=cumulative,
                orientation='h',
                hovertemplate=f"{row['Transition']}: {row['Duration']:.0f} días<extra></extra>",
                marker=dict(color=transition_colors[row['Transition']])
            ))
            cumulative += row['Duration']
    
    fig_dur.update_layout(
        height=400,
        template='plotly_white',
        xaxis_title="Días Promedio",
        margin=dict(l=10, r=20, t=20, b=20),
        barmode='overlay',
        yaxis=dict(categoryorder="array", visible=False, autorange="reversed"),
        showlegend=False
    )
    
    # Display the two charts side-by-side
    col1, col2 = st.columns([1, 3])
    with col1:
        st.plotly_chart(fig_perc, use_container_width=True)
    with col2:
        st.plotly_chart(fig_dur, use_container_width=True)
    
    # Display the legend table
    #st.divider()
    st.markdown("**Leyenda de Flujos:**")

    df = legend_df[['Code', 'Sequence', 'Percentage', 'Total', 'Avg Duration']].rename(
        columns={
            'Code': 'Código',
            'Sequence': 'Secuencia completa',
            'Percentage': '% Procesos',
            'Total': 'Total',
            'Avg Duration': 'Duración total'
        }
    ).reset_index(drop=True)
    
    # Create a Plotly table figure with custom styling
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=list(df.columns),
            fill_color='aliceblue',
            font=dict(color='black', size=14),
            align='center'
        ),
        cells=dict(
            values=[df[col] for col in df.columns],
            fill_color='whitesmoke',
            font=dict(color='black', size=12),
            align='center'
        ),
        columnwidth=[80, 400, 80, 80, 80]
    )])
    fig.update_layout(
        margin=dict(l=20, r=20, t=0, b=20)
    )
    # Display the Plotly table in Streamlit with container width
    st.plotly_chart(fig, use_container_width=True)

# -------------------------------
# TAB 2: Complejidad (Placeholder)
# -------------------------------
with tab2:
    st.subheader("Diagrama de Flujo")
    st.markdown(f"**Flujos principales (> {MIN_PERCENTAGE_SHOW}%):** Seleccione flujos para analizar transiciones")
    
    # Generate checkboxes for flow selection (reuse the helper function)
    selected_flows_gv = []
    for idx, flow in enumerate(flow_data, 1):
        code, _, _, label = generate_flow_info(flow, idx, state_names)
        # Only the first checkbox is True by default, similar to tab2.
        if st.checkbox(label, value=(idx == 1), key=f"gv_flow_{code}"):
            selected_flows_gv.append(flow)
    
    if not selected_flows_gv:
        st.warning("Seleccione al menos un flujo para visualizar")
        st.stop()
    
    # Aggregate transitions from the selected flows (similar to the Sankey tab)
    nodes_set = set()
    link_counts = {}
    link_durations = {}
    
    for flow in selected_flows_gv:
        seq = flow['sequence']
        count = flow['count']
        for i in range(len(seq) - 1):
            source = seq[i]
            target = seq[i + 1]
            duration = flow['durations'][i] if i < len(flow['durations']) else 0
            
            nodes_set.update([source, target])
            key = (source, target)
            link_counts[key] = link_counts.get(key, 0) + count
            link_durations[key] = link_durations.get(key, 0) + (count * duration)
    
    # Create a mapping of each node to a DOT-valid identifier.
    nodes_sorted = sorted(nodes_set)
    node_ids = {node: f"node{idx}" for idx, node in enumerate(nodes_sorted)}
    
    # Build the DOT string.
    dot_lines = []
    dot_lines.append("digraph ProcessFlow {")
    # Set a layout direction (TB = top-to-bottom, LR = left-to-right)
    dot_lines.append("  rankdir=TB;")
    
    # Define nodes with their labels.
    for node in nodes_sorted:
        # Use the state name mapping for a nice label.
        node_label = state_names.get(node, f"S-{node}")
        dot_lines.append(f'  {node_ids[node]} [label="{node_label}"];')
    
    # Define edges with labels that show the count and average duration.
    for (source, target), count in link_counts.items():
        avg_duration = link_durations[(source, target)] / count if count else 0
        # Using "\n" in DOT requires escaping as "\\n" in the string.
        edge_label = f"Exp: {count}\\nDur: {avg_duration:.1f} días"
        dot_lines.append(f'  {node_ids[source]} -> {node_ids[target]} [label="{edge_label}"];')
    
    dot_lines.append("}")
    dot_str = "\n".join(dot_lines)
    
    # Render the Graphviz diagram in Streamlit.
    col_graphviz_1, col_graphviz_2, col_graphviz_3 = st.columns([1,6,1])
    with col_graphviz_2:
        st.graphviz_chart(dot_str)


with tab3:
    st.subheader("Análisis de complejidad")
    st.markdown("")
# -------------------------------
# TAB X: Sankey Diagram (Vertical)
# -------------------------------
# with tabx:
#     st.subheader("Diagrama Sankey")
#     st.markdown(f"**Flujos principales (> {MIN_PERCENTAGE_SHOW}%):** Seleccione flujos para analizar transiciones")
    
#     # Generate checkboxes for flow selection using the helper function
#     selected_flows = []
#     for idx, flow in enumerate(flow_data, 1):
#         code, _, _, label = generate_flow_info(flow, idx, state_names)
#         if st.checkbox(label, value=(idx == 1), key=f"flow_{code}"):
#             selected_flows.append(flow)
    
#     if not selected_flows:
#         st.warning("Seleccione al menos un flujo para visualizar")
#         st.stop()
    
#     # Build Sankey data by aggregating transitions
#     nodes_set = set()
#     link_counts = {}
#     link_durations = {}
    
#     for flow in selected_flows:
#         seq = flow['sequence']
#         count = flow['count']
#         for i in range(len(seq) - 1):
#             source = seq[i]
#             target = seq[i + 1]
#             duration = flow['durations'][i] if i < len(flow['durations']) else 0
            
#             nodes_set.update([source, target])
#             key = (source, target)
#             link_counts[key] = link_counts.get(key, 0) + count
#             link_durations[key] = link_durations.get(key, 0) + (count * duration)
    
#     # Create node index mapping (sorted order)
#     nodes = sorted(nodes_set)
#     node_indices = {node: idx for idx, node in enumerate(nodes)}
    
#     # Prepare Sankey links
#     links = []
#     for (source, target), count in link_counts.items():
#         avg_duration = link_durations[(source, target)] / count
#         links.append({
#             'source': node_indices[source],
#             'target': node_indices[target],
#             'value': count,
#             'customdata': [avg_duration]
#         })
    
#     # Build the vertical Sankey diagram
#     fig_sankey = go.Figure(go.Sankey(
#         orientation='v',  # Attempt to set vertical orientation
#         node=dict(
#             #pad=300,         # Padding between nodes
#             thickness=25,   # Node thickness
#             label=[state_names.get(n, f"S-{n}") for n in nodes],
#             line=dict(color="black", width=0.5),
#             hovertemplate = "%{label}<extra></extra>"
#         ),
#         link=dict(
#             source=[l['source'] for l in links],
#             target=[l['target'] for l in links],
#             value=[l['value'] for l in links],
#             customdata=[l['customdata'] for l in links],
#             arrowlen=15,  # Set link arrow length
#             hovertemplate=(
#                 "%{source.label} → %{target.label}<br>"
#                 "Expedientes: %{value}<br>"
#                 "Duración media: %{customdata[0]:.1f} días"
#                 "<extra></extra>"
#             )
#         )
#     ))
    
#     fig_sankey.update_layout(
#         height=800,
#         margin=dict(l=50, r=50, b=50, t=50),
#         font_size=10
#     )
#     fig_sankey.update_layout(
#         height=1200,
#         #width=800,
#         #autosize=True,
#         margin=dict(l=300, r=300, b=200, t=20),
#         font_size=10,
        
#     )
#     # col_sankey_1, col_sankey_2, col_sankey_3 = st.columns([1, 6, 1])
#     # with col_sankey_2:
#     st.plotly_chart(fig_sankey, use_container_width=False)
