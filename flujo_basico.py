# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 19:19:20 2025

@author: flipe
"""

import streamlit as st
import pandas as pd
import numpy as np

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
        all_states=('num_tramite', lambda x: x.astype('int16').tolist()),
        unidad_tramitadora=('unidad_tramitadora', 'first')
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

if "tramites_texts" not in st.session_state:
    st.error("Tramites texts not found. Please load the main page first.")
    st.stop()

# Get required session state values
selected_procedure = st.session_state.selected_procedure
selected_dates = st.session_state.get('selected_dates', (None, None))
state_names = get_state_names(st.session_state.estados, selected_procedure)
selected_states = [int(s) for s in st.session_state.selected_final_states]
tramites_texts = st.session_state.tramites_texts

# Process filtered data
filtered_processed = process_tramites_final(
    st.session_state.filtered_data['tramites'],
    selected_states,
    selected_dates,
    selected_procedure
)

# Header section
st.header(f"{tramites_texts['descripcion']}")
st.markdown(
    f"**Consejería:** {tramites_texts['consejeria']}  \n"
    f"**Organismo Instructor:** {tramites_texts['org_instructor']}"
)

# General Metrics for filtered data
st.subheader("Datos generales")

total_processes = len(filtered_processed)
finalized_count = filtered_processed['contains_selected'].sum()
finalized_percent = (finalized_count / total_processes * 100) if total_processes > 0 else 0
mean_duration = filtered_processed[filtered_processed['contains_selected']]['duration_days'].mean()

col_gen1, col_gen2, col_gen3 = st.columns(3)
with col_gen1:
    st.metric("Total Expedientes iniciados", f"{total_processes:,}", border=True)
with col_gen2:
    st.metric("Finalizados", f"{finalized_percent:.1f}%", border=True)
with col_gen3:
    value = f"{mean_duration:.0f} días" if not pd.isna(mean_duration) else "N/A"
    st.metric("Tiempo medio", value, border=True)

# State-wise metrics for filtered data
st.subheader("Datos para cada estado final")
st.caption("Volumen y tiempos de expedientes que pasan por los estados seleccionados como finales. Si el estado seleccionado no es el último, los datos representan el tiempo hasta finalizar por completo esos expedientes")

for state_num in selected_states:
    state_name = state_names.get(state_num, f"State {state_num}")
    
    mask = filtered_processed['all_states'].apply(lambda x: state_num in x)
    state_count = mask.sum()
    state_percent = (state_count / total_processes * 100) if total_processes > 0 else 0
    state_mean = filtered_processed[mask]['duration_days'].mean()
    
    cols = st.columns([1, 1, 1, 2])
    cols[0].success(f"**{state_name}**")
    cols[1].metric("Expedientes", state_count)
    cols[2].metric("% del Total", f"{state_percent:.1f}%")
    value = f"{state_mean:.0f} días" if not pd.isna(state_mean) else "N/A"
    cols[3].metric("Tiempo Medio", value)

# Unidad Tramitadora comparison
if 'unidad_tramitadora' in filtered_processed.columns:
    n_unidades = filtered_processed['unidad_tramitadora'].nunique(dropna=False)
    if n_unidades > 1:
        st.subheader("Comparación por Unidad Tramitadora")
        st.caption("Métricas comparativas de cada unidad respecto al total general")
        
        # Calculate overall metrics
        total_filtered = len(filtered_processed)
        finalized_filtered = filtered_processed['contains_selected'].sum()
        finalized_percent_filtered = (finalized_filtered / total_filtered * 100) if total_filtered > 0 else 0
        mean_duration_filtered = filtered_processed[filtered_processed['contains_selected']]['duration_days'].mean()
        
        # Process each unidad
        unidades = filtered_processed['unidad_tramitadora'].unique()
        for unidad in unidades:
            unidad_name = unidad if pd.notna(unidad) else "No especificada"
            mask = filtered_processed['unidad_tramitadora'] == unidad
            unidad_data = filtered_processed[mask]
            
            total_unidad = len(unidad_data)
            finalized_unidad = unidad_data['contains_selected'].sum()
            finalized_percent_unidad = (finalized_unidad / total_unidad * 100) if total_unidad > 0 else 0
            mean_duration_unidad = unidad_data[unidad_data['contains_selected']]['duration_days'].mean()
            
            # Calculate deltas
            delta_percent = finalized_percent_unidad - finalized_percent_filtered
            delta_mean = mean_duration_unidad - mean_duration_filtered if not pd.isna(mean_duration_unidad) else np.nan
            
            # Display metrics
            cols = st.columns([2, 1, 1, 1])
            cols[0].markdown(f"**{unidad_name}**")
            cols[1].metric("Expedientes", total_unidad)
            
            # Percent finalized with delta
            delta_percent_str = f"{delta_percent:.1f}%" if not np.isnan(delta_percent) and delta_percent != 0 else None
            cols[2].metric(
                "% Finalizados",
                f"{finalized_percent_unidad:.1f}%",
                delta=delta_percent_str,
                delta_color="inverse" if delta_percent < 0 else "normal"
            )
            
            # Mean duration with delta
            mean_display = f"{mean_duration_unidad:.0f} días" if not pd.isna(mean_duration_unidad) else "N/A"
            delta_mean_str = f"{delta_mean:.0f} días" if not np.isnan(delta_mean) else None
            cols[3].metric(
                "Tiempo Medio", 
                mean_display,
                delta=delta_mean_str,
                delta_color="inverse" if delta_mean > 0 else "normal"
            )

st.divider()