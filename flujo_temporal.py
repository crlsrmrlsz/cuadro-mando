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


# Helper function to build a DOT string for a given office's processes
def build_dot_for_office(office_df, state_names):
    """
    Given a DataFrame (office_df) containing filtered expedients for one office,
    build a DOT string that aggregates transitions (count and average duration).
    """
    nodes_set = set()
    link_counts = {}
    link_durations = {}
    
    # Loop over each process (expediente) for the office
    for _, row in office_df.iterrows():
        seq = row['all_states']
        durations = row['durations']
        for i in range(len(seq) - 1):
            source = seq[i]
            target = seq[i + 1]
            d = durations[i] if i < len(durations) else 0
            nodes_set.update([source, target])
            key = (source, target)
            link_counts[key] = link_counts.get(key, 0) + 1
            link_durations[key] = link_durations.get(key, 0) + d
    
    # Build DOT lines
    dot_lines = []
    dot_lines.append("digraph ProcessFlow {")
    dot_lines.append("  rankdir=TB;")
    
    # Create node IDs
    sorted_nodes = sorted(nodes_set)
    node_ids = {node: f"node{idx}" for idx, node in enumerate(sorted_nodes)}
    
    # Define nodes with their labels (using state_names mapping)
    for node in sorted_nodes:
        node_label = state_names.get(node, f"S-{node}")
        dot_lines.append(f'  {node_ids[node]} [label="{node_label}"];')
    
    # Define edges with aggregated counts and average durations
    for (source, target), count in link_counts.items():
        avg_duration = link_durations[(source, target)] / count if count else 0
        edge_label = f"Exp: {count}\\nDur: {avg_duration:.1f} días"
        dot_lines.append(f'  {node_ids[source]} -> {node_ids[target]} [label="{edge_label}"];')
    
    dot_lines.append("}")
    return "\n".join(dot_lines)


# Helper function to draw an office-level legend table.
def plot_office_legend_table(legend_df, unique_key):
    """
    Render a Plotly table with the office-level legend information.
    Expected columns: Código, Unidad Tramitadora, % Procesos, Total, Duración total.
    """
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=list(legend_df.columns),
            fill_color='aliceblue',
            font=dict(color='black', size=14),
            align='center'
        ),
        cells=dict(
            values=[legend_df[col] for col in legend_df.columns],
            fill_color='whitesmoke',
            font=dict(color='black', size=12),
            align='center',
            height=30
        ),
        columnwidth=[30, 400, 50, 30, 60]
    )])
    custom_height = legend_df.shape[0] * 30 + 60
    fig.update_layout(
        height=custom_height,
        margin=dict(l=20, r=20, t=0, b=20)
        )
    st.plotly_chart(fig, use_container_width=False, key=unique_key)

def plot_legend_table(legend_df, unique_key):
    """
    Render a Plotly table with the legend information.
    """
    # Prepare the DataFrame for the table
    table_df = legend_df[['Code', 'Sequence', 'Percentage', 'Total', 'Avg Duration']].rename(
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
            values=list(table_df.columns),
            fill_color='aliceblue',
            font=dict(color='black', size=14),
            align='center'
        ),
        cells=dict(
            values=[table_df[col] for col in table_df.columns],
            fill_color='whitesmoke',
            font=dict(color='black', size=12),
            align='center',
            height=30
        ),
        columnwidth=[30, 400, 50, 30, 60]
    )])
    custom_height = table_df.shape[0] * 30 + 40
    fig.update_layout(
        height=custom_height,
        margin=dict(l=20, r=20, t=0, b=10)
    )
    st.plotly_chart(fig, use_container_width=False, key=unique_key)

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
    """
    Process the tramites data (which has already been filtered by selected_procedure,
    selected_dates, and selected_final_states) and compute flows.
    
    This version also carries the 'unidad_tramitadora' column (the office that processes
    each expediente) so that later we can group office-level metrics.
    """
    # Sort by expedition and date
    tramites_sorted = _tramites.sort_values(['id_exp', 'fecha_tramite'])
    
    # Calculate duration between steps (in days)
    tramites_sorted['next_fecha'] = tramites_sorted.groupby('id_exp')['fecha_tramite'].shift(-1)
    tramites_sorted['duration'] = (
        (tramites_sorted['next_fecha'] - tramites_sorted['fecha_tramite'])
        .dt.total_seconds() / 86400
    ).fillna(0)
    
    # Group by expedition. Because all rows for an id_exp share the same office,
    # we take the first value of 'unidad_tramitadora'.
    process_states = tramites_sorted.groupby('id_exp').agg(
        all_states=('num_tramite', lambda x: list(x.astype(int))),
        durations=('duration', list),
        unidad_tramitadora=('unidad_tramitadora', 'first')
    ).reset_index()
    
    # Filter processes that include at least one of the selected states
    filtered_processes = process_states[process_states['all_states'].apply(
        lambda x: any(s in selected_states for s in x)
    )]
    
    total_processes = len(filtered_processes)
    
    # Count the frequency of each sequence (convert lists to tuples to hash them)
    seq_counts = filtered_processes['all_states'].apply(tuple).value_counts().reset_index()
    seq_counts.columns = ['sequence', 'count']
    seq_counts['percentage'] = (seq_counts['count'] / total_processes * 100).round(1)
    
    # Keep only flows that pass the minimum percentage threshold
    major_seqs = seq_counts[seq_counts['percentage'] >= MIN_PERCENTAGE_SHOW].sort_values('count', ascending=False)
    
    # Calculate per-transition average durations for each major flow
    flow_data = []
    for seq_tuple in major_seqs['sequence']:
        seq = list(seq_tuple)
        seq_len = len(seq)
        seq_durations = filtered_processes[filtered_processes['all_states'].apply(tuple) == seq_tuple]['durations']
        aligned_durations = [d[:seq_len - 1] for d in seq_durations]
        avg_durations = np.nanmean(aligned_durations, axis=0).tolist() if aligned_durations else []
        matching_row = major_seqs[major_seqs['sequence'] == seq_tuple].iloc[0]
        flow_data.append({
            'sequence': seq,
            'count': matching_row['count'],
            'percentage': matching_row['percentage'],
            'durations': avg_durations
        })
    
    return flow_data, total_processes, filtered_processes

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

def create_office_visualizations(filtered_processes, flow_data, state_names):
    """
    Build DataFrames for office-level visualizations.
    For each major flow (from flow_data) and for each unidad_tramitadora,
    compute:
      - The count and percentage (with respect to that office’s total)
      - The average durations per transition.
    We also assign an abbreviated office code (e.g. U1, U2) and create a y_label
    in the form "Flow (OfficeCode)" so that the order is consistent with the overall chart.
    """
    # Work with the already filtered processes (which include 'unidad_tramitadora')
    df = filtered_processes.copy()
    df['seq_tuple'] = df['all_states'].apply(tuple)
    # Only keep the major flows (those present in flow_data)
    major_flow_tuples = {tuple(flow['sequence']) for flow in flow_data}
    df = df[df['seq_tuple'].isin(major_flow_tuples)]
    
    # Build a mapping from flow tuple to flow code (to match the global charts)
    flow_code_mapping = {}
    global_flow_order = []
    for idx, flow in enumerate(flow_data, 1):
        ft = tuple(flow['sequence'])
        flow_code = f"F{idx:02d}"
        flow_code_mapping[ft] = flow_code
        global_flow_order.append(flow_code)
    
    # For each (unidad_tramitadora, flow) group, compute counts and percentages
    totals_by_office = df.groupby('unidad_tramitadora').size().to_dict()
    perc_list = []
    dur_list = []
    for (office, seq_tuple), group in df.groupby(['unidad_tramitadora', 'seq_tuple']):
        count = len(group)
        percentage = round(count / totals_by_office[office] * 100, 1)
        flow_code = flow_code_mapping.get(seq_tuple, "N/A")
        perc_list.append({
            'Flow': flow_code,
            'Office': office,
            'percentage': percentage,
            'count': count
        })
        # Compute average durations per transition:
        seq_len = len(seq_tuple)
        durations_lists = group['durations'].tolist()
        aligned = [d[:seq_len - 1] for d in durations_lists] if seq_len > 1 else []
        avg_durs = np.nanmean(aligned, axis=0).tolist() if aligned and len(aligned[0]) > 0 else []
        # Get transitions labels from state names
        states = [str(state_names.get(s, f"S-{s}")) for s in seq_tuple]
        transitions = [f"{states[i]} → {states[i+1]}" for i in range(len(states)-1)]
        # Also record the transition index for ordering
        for i, d in enumerate(avg_durs):
            dur_list.append({
                'Flow': flow_code,
                'Office': office,
                'Transition': transitions[i],
                'Duration': d,
                'transition_index': i
            })
    perc_df = pd.DataFrame(perc_list)
    dur_df = pd.DataFrame(dur_list)
    
    # Create abbreviated office codes (so full names don’t clutter the chart)
    offices_sorted = sorted(df['unidad_tramitadora'].unique())
    office_code_mapping = {name: f"U{i+1}" for i, name in enumerate(offices_sorted)}
    perc_df['OfficeCode'] = perc_df['Office'].map(office_code_mapping)
    dur_df['OfficeCode'] = dur_df['Office'].map(office_code_mapping)
    
    # Create a y_label for plotting: "Flow (OfficeCode)"
    perc_df['y_label'] = perc_df.apply(lambda r: f"{r['Flow']} ({r['OfficeCode']})", axis=1)
    dur_df['y_label'] = dur_df.apply(lambda r: f"{r['Flow']} ({r['OfficeCode']})", axis=1)
    
    # Order the rows by the global flow order and then by OfficeCode
    perc_df['Flow_order'] = pd.Categorical(perc_df['Flow'], categories=global_flow_order, ordered=True)
    perc_df = perc_df.sort_values(['Flow_order', 'OfficeCode'])
    dur_df['Flow_order'] = pd.Categorical(dur_df['Flow'], categories=global_flow_order, ordered=True)
    dur_df = dur_df.sort_values(['Flow_order', 'OfficeCode', 'transition_index'])
    
    return perc_df, dur_df, office_code_mapping



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

# Process data with caching (MODIFIED to capture filtered_processes)
flow_data, total, filtered_processes = process_flows(  # Changed to receive 3 values
    st.session_state.filtered_data['tramites'],
    selected_states,
    st.session_state.selected_procedure,
    st.session_state.selected_dates
)

#st.dataframe(st.session_state.filtered_data['tramites'])

if not flow_data:
    st.warning(f"No hay flujos que cumplan el criterio del {MIN_PERCENTAGE_SHOW}%")

# -------------------------------
# TAB 1: Flow Analysis & Charts
# -------------------------------
with tab1:
    st.subheader("Análisis de principales flujos de tramitación para toda la Comunidad")
    st.info(f"""Identifica los **flujos más comunes** y el **tiempo medio** que se dedica a **cada transición** de estados.
                   Sólo se muestran los flujos que representan más del **{MIN_PERCENTAGE_SHOW}%** del total""",  icon="🕵️‍♂️")
    # Create visualizations
    legend_df, viz_df = create_visualizations(flow_data, state_names)
    
    # Parameter: desired bar thickness in pixels (for horizontal bars)
    BAR_PIXEL_HEIGHT = 50

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
    
    # Compute height: one row per bar plus top and bottom margins (20 each)
    height_perc = int(len(df_perc) * BAR_PIXEL_HEIGHT + 20 + 20)
    
    fig_perc.update_layout(
        height=height_perc,
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
        height=height_perc,
        template='plotly_white',
        xaxis_title="Días Promedio",
        margin=dict(l=10, r=20, t=20, b=20),
        barmode='overlay',
        yaxis=dict(categoryorder="array", visible=False, autorange="reversed"),
        showlegend=False
    )
    with st.container(border=True):
        # Display the two charts side-by-side
        col1, col2 = st.columns([1, 3])
        with col1:
            st.plotly_chart(fig_perc, use_container_width=True, key="percent-global" )
        with col2:
            st.plotly_chart(fig_dur, use_container_width=True, key="time-global")
        
        # Display the legend table
        #st.divider()
    
        # Now show the legend table below the bubble plot.
        st.markdown("**Leyenda de Flujos:**")
        plot_legend_table(legend_df , unique_key="legend_table_tab1")

    # --------------------------------------------------------------------
    # NEW SECTION: Office-level (Unidad Tramitadora) Grouped Charts
    # --------------------------------------------------------------------
    if filtered_processes['unidad_tramitadora'].nunique() > 1:
        #st.divider()
        st.subheader("Análisis diferenciado por Unidad Tramitadora")
        st.info("Identifica **para cada flujo de tramitación**, qué porcentaje de los expedientes tramitados en cada unidad siguen ese flujo, cuánto se tarda de media y posibles diferencias en los tiempo de tramitación",  icon="🕵️‍♂️")
        
        # Compute office-level data using our helper (see previous code)
        # This returns:
        #   perc_df: one row per (Flow, Office) with percentage and count
        #   dur_df: one row per (Flow, Office, Transition) with average durations
        #   office_code_mapping: mapping of full office names to abbreviated codes (e.g. U1, U2)
        perc_df, dur_df, office_code_mapping = create_office_visualizations(filtered_processes, flow_data, state_names)
        
        # Also compute a mapping from flow code to its title (code + full sequence text)
        flow_title_mapping = {}
        for idx, flow in enumerate(flow_data, 1):
            code, states, full_sequence, _ = generate_flow_info(flow, idx, state_names)
            #flow_title_mapping[code] = f"{code}: {full_sequence}"
            flow_title_mapping[code] = f":orange[{full_sequence}]"
            
        # Pre-calculate a color mapping for transitions (reuse Set3 palette)
        color_palette = px.colors.qualitative.Set3
        transition_colors_office = {}
        for i, transition in enumerate(dur_df['Transition'].unique()):
            transition_colors_office[transition] = color_palette[i % len(color_palette)]
            
        # Define a bar height (in pixels) for these per-flow charts.
        BAR_PIXEL_HEIGHT_OFFICE = 40
        
        # Use the global flow order (F01, F02, …) to iterate in a consistent order.
        global_flow_order = [f"F{idx:02d}" for idx in range(1, len(flow_data)+1)]
        
        for flow_code in global_flow_order:
            
            with st.container(border=True):
                
                # Filter the office-level data for this flow.
                perc_flow = perc_df[perc_df['Flow'] == flow_code].copy()
                dur_flow = dur_df[dur_df['Flow'] == flow_code].copy()
                if perc_flow.empty:
                    continue  # Skip flows without office-level info
                
                # LEFT CHART: Horizontal bar chart for % of processes per office
                max_perc_ud = perc_flow['percentage'].max()
                fig_left = go.Figure(go.Bar(
                    x=perc_flow['percentage'],
                    y=perc_flow['OfficeCode'],
                    orientation='h',
                    text=perc_flow['percentage'].apply(lambda x: f"{x:.1f}%"),
                    textposition='outside',
                    customdata=perc_flow[['count']].values,
                    hovertemplate="<b>Total expedientes:</b> %{customdata[0]}<extra></extra>",
                    marker_color='#1f77b4'
                    
                ))
                height_left = int(len(perc_flow) * BAR_PIXEL_HEIGHT_OFFICE + 80)
                fig_left.update_layout(
                    height=height_left,
                    template='plotly_white',
                    margin=dict(l=20, r=10, t=30, b=40),
                    xaxis_title="% de Procesos",
                    yaxis=dict(autorange="reversed"),
                    xaxis_range=[0, max_perc_ud * 1.2]
                )
                
                # RIGHT CHART: Horizontal stacked bar chart for average durations per office.
                fig_right = go.Figure()
                # Group by OfficeCode – each office gets one horizontal bar.
                for office_code, group in dur_flow.groupby('OfficeCode', sort=False):
                    group = group.sort_values('transition_index')
                    cumulative = 0  
                    for _, row in group.iterrows():
                        fig_right.add_trace(go.Bar(
                            x=[row['Duration']],
                            y=[office_code],
                            base=cumulative,
                            orientation='h',
                            hovertemplate=f"{row['Transition']}: %{{x:.0f}} días<extra></extra>",
                            marker=dict(color=transition_colors_office[row['Transition']])
                        ))
                        cumulative += row['Duration']
                fig_right.update_layout(
                    height=height_left,
                    template='plotly_white',
                    xaxis_title="Días Promedio",
                    margin=dict(l=10, r=20, t=30, b=40),
                    barmode='overlay',
                    yaxis=dict(autorange="reversed", visible=False),
                    showlegend=False
                )
                
                # Display the title for this flow.
                st.markdown(f"#### {flow_title_mapping[flow_code]}")
                col_left, col_right = st.columns([1,3])
                with col_left:
                    st.plotly_chart(fig_left, use_container_width=True, key=f"{flow_code}-1")
                with col_right:
                    st.plotly_chart(fig_right, use_container_width=True, key= f"{flow_code}-2")
                
                # Build an office-level legend table for this flow.
                # First, aggregate the durations (sum the durations across transitions) by office.
                agg_dur = dur_flow.groupby('OfficeCode', as_index=False)['Duration'].sum()
                # Merge with the percentage info.
                office_legend_df = perc_flow.merge(agg_dur, on='OfficeCode', how='left')
                # Rename and reformat columns.
                office_legend_df = office_legend_df.rename(columns={
                    'OfficeCode': 'Código',
                    'Office': 'Unidad Tramitadora',
                    'percentage': '% Procesos',
                    'count': 'Total',
                    'Duration': 'Duración total'
                })
                office_legend_df['% Procesos'] = office_legend_df['% Procesos'].apply(lambda x: f"{x:.1f}%")
                office_legend_df['Duración total'] = office_legend_df['Duración total'].apply(lambda x: f"{x:.0f} días")
                office_legend_df = office_legend_df[['Código', 'Unidad Tramitadora', '% Procesos', 'Total', 'Duración total']]
                
                st.markdown("**Leyenda de Unidades Tramitadoras para este flujo:**")
                plot_office_legend_table(office_legend_df, unique_key=f"office_legend_{flow_code}")
    else:
        st.info("Solo se encontró una Unidad Tramitadora, por lo que no se muestra el análisis por unidad.")

# -------------------------------
# TAB 2: Diagrama de flujo
# -------------------------------
with tab2:
    st.subheader("Diagrama del flujo de tramitación")
    st.markdown(f"Selecciona uno o varios flujos de tramitación para visualizarlos en el diagrama. Solo se representan los flujos que representan más del {MIN_PERCENTAGE_SHOW}%) del total de los expedientes finalizados")
    
    # Generate checkboxes for flow selection (reuse the helper function)
    selected_flows_gv = []
    with st.container(border=True):
        for idx, flow in enumerate(flow_data, 1):
            code, _, _, label = generate_flow_info(flow, idx, state_names)
            # Only the first checkbox is True by default, similar to tab2.
            if st.checkbox(label, value=(idx == 1), key=f"gv_flow_{code}"):
                selected_flows_gv.append(flow)
        
        if not selected_flows_gv:
            st.warning("Seleccione al menos un flujo para visualizar")
            st.stop()
    
    
    st.markdown("")
    st.markdown("")
    
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
    col_graphviz_1, col_graphviz_2, col_graphviz_3 = st.columns([1,1,1])
    with col_graphviz_2:
        st.graphviz_chart(dot_str)

    # New checkbox and dataframe display
    if st.checkbox("Mostrar trámites de los flujos seleccionados", key="show_tramites_df"):
        # Get selected sequences
        selected_sequences = [tuple(flow['sequence']) for flow in selected_flows_gv]
        
        # Find matching expeditions
        mask = filtered_processes['all_states'].apply(tuple).isin(selected_sequences)
        matching_ids = filtered_processes[mask]['id_exp'].unique()
        
        # Filter and display tramites
        tramites_df = st.session_state.filtered_data['tramites']
        filtered_tramites = tramites_df[tramites_df['id_exp'].isin(matching_ids)]
        
        # Add state names using the dictionary mapping
        filtered_tramites['Estado'] = filtered_tramites['num_tramite'].apply(
            lambda x: state_names.get(x, f"S-{x}")  # Handle missing states
        )
        
        # Select specific columns to show
        filtered_tramites = filtered_tramites[[
            'id_exp',
            'Estado',          # Our new column with state names
            'fecha_tramite',   # Keep original date
            'unidad_tramitadora' 
        ]]
        
        st.write(f"**Trámites para {len(matching_ids)} expedientes seleccionados:**")
        st.dataframe(
            filtered_tramites,
            column_config={
                "id_exp": "Expediente",
                "Estado": "Estado del trámite",
                "fecha_tramite": "Fecha del trámite",
                "unidad_tramitadora":  "Unidad Tramitadora"                
            },
            hide_index=True,
            use_container_width=False
        )

    #########################
    # Comparador de flujos de unidades tramitadoras
    ##############################################
    if filtered_processes['unidad_tramitadora'].nunique() > 1:
        
        
        st.subheader("Comparación de flujos de proceso de dos Unidades Tramitadoras")
        st.info("Visualiza en los diagramas cuántos expedientes se tramitan en cada unidad y el tiempo que se tarda en cada trámite", icon="👀")
        # Get the selected flows as tuples (as used earlier)
        selected_sequences = [tuple(flow['sequence']) for flow in selected_flows_gv]
        
        # Create two equal-width columns for the comparator
        col1, col2 = st.columns(2)
        
        with col1:
            with st.container(border=True):
                st.subheader("Unidad Tramitadora 1")
                # Combo selector showing the office labels (sorted alphabetically)
                offices = sorted(filtered_processes['unidad_tramitadora'].unique())
                selected_office_1 = st.selectbox("Seleccione la primera Unidad Tramitadora", options=offices, key="comp_office_1")
                
                # Filter the data for the selected office and then by selected flows
                office_df1 = filtered_processes[filtered_processes['unidad_tramitadora'] == selected_office_1]
                office_df1 = office_df1[office_df1['all_states'].apply(tuple).isin(selected_sequences)]
                
                if office_df1.empty:
                    st.info("No hay procesos para esta combinación en esta unidad.")
                else:
                    dot_str_office_1 = build_dot_for_office(office_df1, state_names)
                    col_order_1_1, col_order_1_2, col_order_1_3 = st.columns(3)
                    with col_order_1_2:
                        st.graphviz_chart(dot_str_office_1)
            
        with col2:
            with st.container(border=True):
                
                st.subheader("Unidad Tramitadora 2")
                selected_office_2 = st.selectbox("Seleccione la segunda Unidad Tramitadora", options=offices, key="comp_office_2")
                
                office_df2 = filtered_processes[filtered_processes['unidad_tramitadora'] == selected_office_2]
                office_df2 = office_df2[office_df2['all_states'].apply(tuple).isin(selected_sequences)]
                
                if office_df2.empty:
                    st.info("No hay procesos para esta combinación en esta unidad.")
                else:
                    dot_str_office_2 = build_dot_for_office(office_df2, state_names)
                    col_order_2_1, col_order_2_2, col_order_2_3 = st.columns(3)
                    with col_order_2_2:
                        st.graphviz_chart(dot_str_office_2)



with tab3:
    st.subheader("Análisis de complejidad")
    st.info(f"""Mayor númeo de pasos suele implicar mayor tiempo. Visualiza el volumen de procesos que tiene más pasos y tardan más.
                   Sólo se muestran los flujos que representan más del {MIN_PERCENTAGE_SHOW}% del total""",  icon="🕵️‍♂️")
    
    # Prepare data for the bubble scatter plot using generate_flow_info for consistency.
    bubble_data = []
    for idx, flow in enumerate(flow_data, 1):
        # Use the helper function to obtain coherent information.
        code, states, full_sequence, label = generate_flow_info(flow, idx, state_names)
        # Define complexity as the number of states (or pasos) in the flow.
        complexity = len(states)
        # Calculate total duration (in days) as an integer (rounding if necessary).
        total_duration = int(round(sum(flow['durations'])))
        # Number of processes following this flow.
        count = flow['count']
        # Percentage of total processes for this flow (optional information).
        percentage = flow['percentage']
        
        bubble_data.append({
            'Flow': code,
            'Complejidad': complexity,
            'Duración Total (días)': total_duration,
            'Procesos': count,
            '% Procesos': percentage,
            'Secuencia': full_sequence
        })
    
    df_bubble = pd.DataFrame(bubble_data)
    
    # Create the bubble scatter plot using Plotly Express.
    #   - x-axis: Complejidad (número de pasos), shown as integer ticks.
    #   - y-axis: Duración Total (días) as an integer.
    #   - size: Procesos (number of processes following the flow).
    #   - color: Flow (to distinguish between different flows).
    #   - hover_name: Flow (this will appear as the title in the hover popup).
    #   - hover_data: Additional details, excluding Flow (since it’s already shown).
    fig_bubble = px.scatter(
        df_bubble,
        x='Complejidad',
        y='Duración Total (días)',
        size='Procesos',
        color='Flow',
        hover_name='Flow',
        hover_data={
            'Flow': False,  # Remove redundant flow code from hover data.
            'Complejidad': True, 
            'Duración Total (días)': True, 
            'Procesos': True, 
            '% Procesos': True,
            'Secuencia': True
        },
        size_max=60,
        title="Relación entre Complejidad y Duración"
    )
    
    # Update layout for a cleaner presentation.
    fig_bubble.update_layout(
        template='plotly_white',
        xaxis_title="Complejidad (número de pasos)",
        yaxis_title="Duración Total (días)",
        xaxis=dict(tickmode='linear', dtick=1),  # Ensure x-axis ticks are integers.
        margin=dict(l=40, r=40, t=60, b=40),
    )
    
    # Display the bubble chart in the Streamlit app.
    st.plotly_chart(fig_bubble, use_container_width=True, key="complexity")
    
    # Now show the legend table below the bubble plot.
    st.markdown("**Leyenda de Flujos:**")
    plot_legend_table(legend_df, unique_key="legend_table_tab3")

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
