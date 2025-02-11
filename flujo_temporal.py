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

max_percetage_show = 2

# Cache critical data processing with relevant parameters
@st.cache_data
def process_flows(_tramites, selected_states, selected_procedure, selected_dates):
    # Process tramites data
    tramites_sorted = _tramites.sort_values(['id_exp', 'fecha_tramite'])
    
    # Calculate step durations
    tramites_sorted['next_fecha'] = tramites_sorted.groupby('id_exp')['fecha_tramite'].shift(-1)
    tramites_sorted['duration'] = (
        (tramites_sorted['next_fecha'] - tramites_sorted['fecha_tramite']).dt.total_seconds() / 86400
    ).fillna(0)  # Explicitly handle last step duration
    
    # Group by expedition
    process_states = tramites_sorted.groupby('id_exp').agg(
        all_states=('num_tramite', lambda x: list(x.astype(int))),
        durations=('duration', list)
    ).reset_index()
    
    # Filter processes containing selected states
    contains_mask = process_states['all_states'].apply(
        lambda x: any(s in selected_states for s in x)
    )
    filtered_processes = process_states[contains_mask]
    
    # Calculate total processes for percentage calculation
    total_processes = len(filtered_processes)
    

    # Lists in Python are mutable and cannot be used as keys in dictionaries or elements in a value_counts() operation 
    # because they are unhashable. Tuples, being immutable and hashable, can be used for counting unique occurrences.
    # .value_counts() After converting each sequence to a tuple, .value_counts() counts how many times each unique tuple appears in the column.
    # reset_index() : This converts the Series into a DataFrame by turning the index (the sequences) into a normal column and the counts into another column.
    # Count sequence frequencies with length validation
    seq_counts = filtered_processes['all_states'].apply(tuple).value_counts().reset_index()
    seq_counts.columns = ['sequence', 'count']
    seq_counts['percentage'] = (seq_counts['count'] / total_processes * 100).round(1)
    major_seqs = seq_counts[seq_counts['percentage'] >= max_percetage_show].sort_values('count', ascending=False)
    

    # Calculate accurate per-transition averages
    flow_data = []
    for seq_tuple in major_seqs['sequence']:
        # Although the sequence is originally a tuple (which is hashable and convenient for comparisons), 
        # converting it to a list (seq_str) makes it easier to work with later—especially if you want to display or format it
        # tuple ('A', 'B', 'C', 'D')
        # 
        seq = list(seq_tuple)
        seq_len = len(seq)
        
        # Get matching processes
        seq_mask = filtered_processes['all_states'].apply(tuple) == seq_tuple
        seq_durations = filtered_processes[seq_mask]['durations']
        
        # Validate and align durations
        aligned_durations = []
        # For a sequence with n states, there should be n-1 transition durations (the time taken from one state to the next).
        # So, for our example with 4 states ('A', 'B', 'C', 'D'), we want only 3 durations.
        for dur_list in seq_durations:
            # Trim durations to match sequence transitions (n-1 durations for n states)
            aligned_durations.append(dur_list[:seq_len-1])
        
        # Calculate averages for each transition position
        if aligned_durations:
            avg_durations = np.nanmean(aligned_durations, axis=0).tolist()
            # np.nanmean calculates the mean (average) along the specified axis while ignoring any NaN (Not a Number) values.
            # axis=0 means it computes the mean for each column
        else:
            avg_durations = []
        
        flow_data.append({
            'sequence': seq,
            'count': major_seqs[major_seqs['sequence'] == seq_tuple]['count'].iloc[0],
            'percentage': major_seqs[major_seqs['sequence'] == seq_tuple]['percentage'].iloc[0],
            'durations': avg_durations
        })
    
    return flow_data, total_processes    



def create_visualizations(flow_data, state_names):
    # Generate flow codes and legend
    legend_data = []
    viz_data = []
    
    for idx, flow in enumerate(flow_data, 1):
        code = f"F{idx:02d}"
        states = [str(state_names.get(s, f"S-{s}")) for s in flow['sequence']]
        transitions = [f"{states[i]} → {states[i+1]}" for i in range(len(states)-1)]
        
        # Add legend entry
        legend_data.append({
            'Code': code,
            'Sequence': " → ".join(states),
            'Percentage': f"{flow['percentage']}%",
            'Total': flow['count'],
            'Avg Duration': f"{sum(flow['durations']):.0f} días"
        })
        
        # Add visualization data for each transition
        for step_idx, (transition, duration) in enumerate(zip(transitions, flow['durations'])):
            viz_data.append({
                'Flow': code,
                'Transition': transition,
                'Duration': duration,
                'Percentage': flow['percentage']
            })
    
    return pd.DataFrame(legend_data), pd.DataFrame(viz_data)


##########################
# INTERFAZ DE USUARIO
##########################
tab1, tab2, tab3 = st.tabs([
    "Flujos principales", 
    "Diagrama de flujo", 
    "Complejidad"
])


with tab1:
    st.subheader("Análisis de Flujos Principales")
    st.markdown(f"Se muestran los flujos que representan más del {max_percetage_show}% de los procesos finalizados, de acuerdo a los estados finales seleccionados y en el rango de fechas seleccionado")
    
    # Validate session state
    if "filtered_data" not in st.session_state:
        st.error("Cargue los datos desde la página principal primero.")
    
    
    # Get required data
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
        st.warning("No hay flujos que cumplan el criterio del 3%")
    
    
    # Create visualizations
    legend_df, viz_df = create_visualizations(flow_data, state_names)
    
    
    # ------------------------------------------------------
    # Build the left chart: Percentage chart (using Graph Objects)
    # We use drop_duplicates('Flow') to have one bar per flow.
    df_perc = viz_df.drop_duplicates('Flow')
    
    fig_perc = go.Figure()
    fig_perc.add_trace(go.Bar(
        x=df_perc['Percentage'],
        y=df_perc['Flow'],
        orientation='h',
        text=df_perc['Percentage'].apply(lambda x: f"{x:.1f}%"),
        textposition='outside',
        hovertemplate="%{x:.1f}%<extra></extra>",  # Custom hover text
        marker_color='#1f77b4'  # Change the color as desired
    ))
    
    max_perc = df_perc['Percentage'].max()  # assuming df_perc holds your per-flow percentage values
    # Hide the x-axis (only show the y-axis and its label) to save space.
    fig_perc.update_layout(
        height=400,
        template='plotly_white',
        margin=dict(l=20, r=10, t=20, b=20),
        xaxis_title="% de Procesos",
        yaxis=dict(title='% de Procesos', autorange="reversed"),
        xaxis_range=[0, max_perc * 1.2]
    )
    
    # ------------------------------------------------------
    # Build the right chart: Duration chart with manual stacking
    
    # Generate a fixed color map for transitions
    transition_colors = {}  
    color_palette = px.colors.qualitative.Set3  
    color_index = 0
    
    # Assign colors to each unique transition
    for transition in viz_df['Transition'].unique():
        transition_colors[transition] = color_palette[color_index % len(color_palette)]
        color_index += 1
    
    fig_dur = go.Figure()
    
    # Group by 'Flow' while maintaining order
    for flow, group in viz_df.groupby('Flow', sort=False):
        cumulative = 0  
    
        for _, row in group.iterrows():
            fig_dur.add_trace(go.Bar(
                x=[row['Duration']],
                y=[flow],
                base=cumulative,
                orientation='h',
                hovertemplate=f"{row['Transition']}: {row['Duration']:.0f} días<extra></extra>",
                marker=dict(color=transition_colors[row['Transition']])  # Assign consistent color
            ))
            cumulative += row['Duration']
    
    fig_dur.update_layout(
        height=400,
        template='plotly_white',
        xaxis_title="Días Promedio",
        margin=dict(l=10, r=20, t=20, b=20),
        barmode='overlay',  
        yaxis=dict(categoryorder="array", 
                   visible=False, 
                   autorange="reversed"),  
        showlegend=False  # Completely remove the legend
    )
    
    # ------------------------------------------------------
    # Display the charts side-by-side using Streamlit columns.
    col1, col2 = st.columns([1, 3])
    with col1:
        st.plotly_chart(fig_perc, use_container_width=True)
    with col2:
        st.plotly_chart(fig_dur, use_container_width=True)
    
    # Show legend
    st.divider()
    st.write("**Leyenda de Flujos:**")
    st.dataframe(
        legend_df[['Code', 'Sequence', 'Percentage', 'Total', 'Avg Duration']],
        column_config={
            'Code': 'Código',
            'Sequence': 'Secuencia completa',
            'Percentage': '% Procesos',
            'Total': 'Total',
            'Avg Duration': 'Duración total'
        },
        hide_index=True,
        use_container_width=True
    )
