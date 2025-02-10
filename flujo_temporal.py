# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 19:19:18 2025

@author: flipe
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


@st.cache_data
def get_state_names(estados_df, selected_procedure):
    return estados_df.set_index('NUMTRAM')['DENOMINACION_SIMPLE'].astype('category').to_dict()

@st.cache_data
def process_tramites_final(_tramites, selected_states, date_range, selected_procedure):
    _tramites = _tramites.copy()
    _tramites['num_tramite'] = _tramites['num_tramite'].astype('int16')
    
    _tramites_sorted = _tramites.sort_values(['id_exp', 'fecha_tramite'])
    
    process_states = _tramites_sorted.groupby('id_exp').agg(
        first_date=('fecha_tramite', 'min'),
        last_date=('fecha_tramite', 'max'),
        all_states=('num_tramite', lambda x: x.astype('int16').tolist())
    ).reset_index()
    
    process_states['duration_days'] = (
        process_states['last_date'] - process_states['first_date']
    ).dt.total_seconds() / (3600 * 24)
    
    process_states['contains_selected'] = process_states['all_states'].apply(
        lambda states: any(s in selected_states for s in states)
    )
    
    return process_states


# Page initialization
if "filtered_data" not in st.session_state:
    st.error("Filtered data not found. Please load the main page first.")
    st.stop()

tramites_df = st.session_state.filtered_data.get("tramites")
if tramites_df is None:
    st.error("Trámites data is not available in the filtered data.")
    st.stop()
    
    
# Get required session state values
selected_procedure = st.session_state.selected_procedure
selected_dates = st.session_state.get('selected_dates', (None, None))
state_names = get_state_names(st.session_state.estados, selected_procedure)
selected_states = [int(s) for s in st.session_state.selected_final_states]
#tramites_texts = st.session_state.tramites_texts

# Process data with date range awareness
filtered_processed = process_tramites_final(
    st.session_state.filtered_data['tramites'],
    selected_states,
    selected_dates,  # Critical cache key element
    selected_procedure
)    
    
# Create a four-tab layout
tab1, tab2, tab3 = st.tabs(["Flujos principales", "Diagrama", "Tab"])

with tab1:
    st.subheader("Principales Flujos y Tiempos de Ejecución")
    
    
    # Preprocess tramites data for durations
    tramites_sorted = tramites_df.sort_values(['id_exp', 'fecha_tramite']).copy()
    tramites_sorted['next_fecha'] = tramites_sorted.groupby('id_exp')['fecha_tramite'].shift(-1)
    tramites_sorted['duration'] = (tramites_sorted['next_fecha'] - tramites_sorted['fecha_tramite']).dt.total_seconds() / (3600 * 24)
    tramites_sorted['duration'] = tramites_sorted['duration'].fillna(0)

    # Create mapping of sequences and durations
    id_exp_data = {}
    for id_exp, group in tramites_sorted.groupby('id_exp'):
        id_exp_data[id_exp] = {
            'sequence': tuple(group['num_tramite'].astype(int).tolist()),
            'durations': group['duration'].tolist()
        }

    # Process data for visualizations
    state_groups = []
    for state in selected_states:
        state_name = state_names.get(state, f"Estado {state}")
        
        # Filter processes that contain this final state in their sequen
        mask = filtered_processed['all_states'].apply(lambda x: state in x)
        group = filtered_processed[mask]
        
        # Count occurrences of each unique sequence
        sequence_counts = {}
        for seq in group['all_states']:
            # Convert list to tuple (hashable for dictionary keys)
            seq_tuple = tuple(seq)
            sequence_counts[seq_tuple] = sequence_counts.get(seq_tuple, 0) + 1
        
        # Get all sequences sorted by frequency (descending)
        # The sorted() function takes an iterable and returns a new list of its items sorted in a specified order
        # For each tuple x in the list (where x is (key, value)), x[1] refers to the frequency (or count) of the sequence.
        # The lambda returns the negative of this frequency.
        all_sequences = sorted(sequence_counts.items(), key=lambda x: -x[1])
        
        # Process sequence data
        sequence_data = []
        for seq, count in all_sequences:
            # Get IDs of processes with this exact sequence
            ids = group[group['all_states'].apply(tuple) == seq]['id_exp']
            
            # Calculate average duration for each step in the sequence
            state_durations = []
            if len(seq) > 1:
                # Initialize list to accumulate durations for each step
                state_durations = [0.0] * (len(seq)-1)
                valid_ids = 0
                for id_exp in ids:
                    data = id_exp_data.get(id_exp)
                    # Check if we have duration data for this process
                    if data and data['sequence'] == seq and len(data['durations']) >= len(seq)-1:
                        valid_ids += 1
                        # Sum durations for each step
                        for i in range(len(seq)-1):
                            state_durations[i] += data['durations'][i]
                # Calculate averages if we found valid processes
                if valid_ids > 0:
                    state_durations = [d/valid_ids for d in state_durations]
            
            # Store sequence information
            sequence_data.append({
                'sequence': seq,
                'count': count,
                'state_durations': state_durations,
                'state_names': [str(state_names.get(s, f"Estado {s}")) for s in seq]  # Convert to string
            })
        
        # Add final state group information
        state_groups.append({
            'state_name': state_name,      # Name of the final state
            'total_count': len(group),      # Total processes with this final state
            'mean_duration': group['duration_days'].mean(),  # Average total duration
            'sequences': sequence_data      # All sequences leading to this final state
        })

    st.session_state.state_groups = state_groups
    # Prepare data for visualizations
    left_chart_data = []
    right_chart_data = []
    
    for group in state_groups:
        # Add total group
        left_chart_data.append({
            'label': f"{group['state_name']} (Total)",
            'count': group['total_count'],
            'type': 'total',
            'color': group['state_name']
        })
        
        # Add individual sequences
        for seq in group['sequences']:
            # Create sequence label
            seq_label = " → ".join(seq['state_names'])
            
            # Add to left chart data
            left_chart_data.append({
                'label': f"  → {seq_label}",
                'count': seq['count'],
                'type': 'sequence',
                'color': group['state_name']
            })
            
            if len(seq['state_durations']) > 0:
                # Maintain original order for chronological stacking
                for i, (dur, state) in enumerate(zip(seq['state_durations'], seq['state_names'][:-1])):
                    right_chart_data.append({
                        'sequence_label': f"  → {seq_label}",
                        'state': f"{state} → {seq['state_names'][i+1]}",  # Show transition
                        'duration': dur,
                        'order': i,  # Chronological order
                        'color': group['state_name']
                    })
        
    # Create charts
    if left_chart_data and right_chart_data:


        # Left Chart (Counts)
        df_left = pd.DataFrame(left_chart_data)
        fig_left = px.bar(
            df_left,
            x='count',
            y='label',
            color='color',
            orientation='h',
            title='<b>Flujos Más Comunes</b>',
            labels={'count': 'Número de Expedientes', 'label': ''}
        )
        fig_left.update_layout(showlegend=False, height=600)
        fig_left.update_traces(marker_line_width=0)

        # Right Chart (Stacked Durations)
        df_right = pd.DataFrame(right_chart_data)
        fig_right = px.bar(
            df_right,
            x='duration',
            y='sequence_label',
            color='state',
            orientation='h',
            title='<b>Tiempo Promedio por Estado</b>',
            labels={'duration': 'Días Promedio', 'sequence_label': ''},
            category_orders={'order': sorted(df_right['order'].unique())}
        )
        fig_right.update_layout(height=600, barmode='stack')

        # Display charts side by side
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(fig_left, use_container_width=True)
        with col2:
            st.plotly_chart(fig_right, use_container_width=True)
    else:
        st.warning("No hay datos suficientes para mostrar los gráficos.")
        