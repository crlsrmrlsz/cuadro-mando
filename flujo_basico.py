# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 19:19:20 2025

@author: flipe
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

@st.cache_data
def get_state_names(estados_df, selected_procedure):
    return estados_df.set_index('NUMTRAM')['DENOMINACION_SIMPLE'].astype('category').to_dict()

@st.cache_data
def process_tramites_final(_tramites, selected_states, date_range, selected_procedure):
    _tramites = _tramites.copy()
    _tramites['num_tramite'] = _tramites['num_tramite'].astype('int16')
    
    _tramites_sorted = _tramites.sort_values(['id_exp', 'fecha_tramite'])
    _tramites_sorted['unidad_tramitadora'] = _tramites_sorted['unidad_tramitadora'].fillna('No especificada')

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

# General Metrics for filtered data in bordered container
with st.container(border=True):
    total_processes = len(filtered_processed)
    finalized_count = filtered_processed['contains_selected'].sum()
    finalized_percent = (finalized_count / total_processes * 100) if total_processes > 0 else 0
    mean_duration = filtered_processed[filtered_processed['contains_selected']]['duration_days'].mean()

    col_gen1, col_gen2, col_gen3, col_gen4 = st.columns(4)
    with col_gen1:
        st.subheader("Datos globales Comunidad")
    with col_gen2:
        st.metric("Total Expedientes iniciados", f"{total_processes:,}")
    with col_gen3:
        st.metric("Finalizados (alcanza cualquiera de los estados finales)", f"{finalized_percent:.1f}%")
    with col_gen4:
        value = f"{mean_duration:.0f} días" if not pd.isna(mean_duration) else "N/A"
        st.metric("Tiempo medio finalización", value)

    # State-wise metrics in bordered container
    if len(selected_states) > 0 and st.checkbox("Mostrar estadísticas por estado final", value=False):
        st.caption("Volumen y tiempos de expedientes que pasan por los estados seleccionados como finales. Si el estado seleccionado no es el último, los datos representan el tiempo hasta finalizar por completo esos expedientes")
    
        for state_num in selected_states:
            state_name = state_names.get(state_num, f"State {state_num}")
            
            mask = filtered_processed['all_states'].apply(lambda x: state_num in x)
            state_count = mask.sum()
            state_percent = (state_count / total_processes * 100) if total_processes > 0 else 0
            state_mean = filtered_processed[mask]['duration_days'].mean()

            cols = st.columns([2, 1, 1, 1])
            cols[0].info(f"**{state_name}**")
            cols[1].metric("Expedientes que llegan a este estado", state_count)
            cols[2].metric("% del Total que pasan por este estado", f"{state_percent:.1f}%")
            value = f"{state_mean:.0f} días" if not pd.isna(state_mean) else "N/A"
            cols[3].metric("Tiempo Medio hasta un estado final", value)

# Unidad Tramitadora comparison
if 'unidad_tramitadora' in filtered_processed.columns:
    unidades_series = filtered_processed['unidad_tramitadora']
    unique_unidades = unidades_series.unique()
    
    # Create color mapping based on original names
    color_sequence = px.colors.qualitative.Plotly
    color_mapping = {unidad: color_sequence[i % len(color_sequence)] 
                     for i, unidad in enumerate(sorted(unique_unidades))}
    
    # Create code mapping for display
    unidad_codes = {unidad: f'UT{i+1}' for i, unidad in enumerate(sorted(unique_unidades))}
    filtered_processed['unidad_code'] = unidades_series.map(unidad_codes)

    unidades_validas = unidades_series[unidades_series.isin(unidades_series.value_counts()[unidades_series.value_counts() > 0].index)]
    
    if len(unidades_validas.unique()) > 1:
        st.markdown("")
        with st.container(border=True):
            st.subheader("Datos por Unidad Tramitadora")
            st.info("Reparto de expedientes por Unidades y tiempos medios de finalización",icon='ℹ️')
            # Ensure units are sorted as desired
            unidades_sorted = sorted(unidades_validas.unique(), key=lambda x: (x == 'No especificada', x))
            
            col1, col2, col3, col4 = st.columns([1,4,2,1])
            
            # Pie Chart: Distribution of Expedientes
            with col2:
                # Aggregate data by unit code and unit name
                agg_data = (
                    filtered_processed
                    .groupby(['unidad_code', 'unidad_tramitadora'], as_index=False)
                    .size()
                    .rename(columns={'size': 'count'})
                )
                
                # Create a legend label that combines the unit code and the unit name
                agg_data['legend_label'] = agg_data['unidad_code'] + " - " + agg_data['unidad_tramitadora']
                
                fig_pie = go.Figure(data=[go.Pie(
                    labels=agg_data['legend_label'],      # Legend shows combined code and name
                    values=agg_data['count'],
                    customdata=agg_data['unidad_tramitadora'],  # For hover: show only the unit name
                    textinfo='percent',
                    texttemplate='%{percent}',
                    textposition='outside',
                    marker=dict(colors=[color_mapping[ut] for ut in agg_data['unidad_tramitadora']]),
                    hovertemplate="%{customdata}<br>Expedientes: %{value}<br>Porcentaje: %{percent}<extra></extra>"
                )])
                fig_pie.update_layout(
                    title="Expedientes recibidos por Unidad",
                    height=450,
                    showlegend=True,
                    legend=dict(
                        orientation="h",  # Horizontal legend
                        y=-0.15,           # Positioned under the chart
                        x=0.5,
                        xanchor="center"
                    )
                )
                #fig_pie.update_traces(traceorder='normal')
                st.plotly_chart(fig_pie, use_container_width=True, key="global-number")
            
            # Bar Chart: Average Duration of Finalization
            with col3:
                # Compute the average duration for finalized processes
                duration_df = (
                    filtered_processed[filtered_processed['contains_selected']]
                    .groupby('unidad_tramitadora', as_index=False)['duration_days']
                    .mean()
                )
                duration_df['unidad_code'] = duration_df['unidad_tramitadora'].map(unidad_codes)
              
                # Create a combined label for hover information
                duration_df['legend_label'] = duration_df['unidad_code'] + " - " + duration_df['unidad_tramitadora']
                
                fig_bar = go.Figure()
                for _, row in duration_df.iterrows():
                    fig_bar.add_trace(go.Bar(
                        x=[row['unidad_code']],
                        y=[row['duration_days']],
                        customdata=[row['legend_label']],  # Use combined label in hover data
                        marker_color=color_mapping[row['unidad_tramitadora']],
                        text=f"{row['duration_days']:.1f}",
                        textposition='outside',
                        hovertemplate="%{customdata}<br>Duración: %{y:.1f} días<extra></extra>"
                    ))
                fig_bar.update_layout(
                    title="Tiempo Medio de Finalización",
                    xaxis_title="Unidad",
                    yaxis_title="Días",
                    height=450,
                    showlegend=False  # No legend on bar chart
                )
                st.plotly_chart(fig_bar, use_container_width=True, key="global-time")
            
            st.markdown("")    
            st.subheader("Número y tiempos por Unidad")
            st.info("Compara % de expedientes finalizados, tiempos medios y diferencia respecto a la media",icon='ℹ️')
            for unidad in unidades_sorted:
                mask = unidades_series == unidad
                unidad_data = filtered_processed[mask]
                code = unidad_codes[unidad]
                
                total_unidad = len(unidad_data)
                finalized_unidad = unidad_data['contains_selected'].sum()
                finalized_percent_unidad = (finalized_unidad / total_unidad * 100) if total_unidad > 0 else 0
                mean_duration_unidad = unidad_data[unidad_data['contains_selected']]['duration_days'].mean()
                
                delta_percent = finalized_percent_unidad - finalized_percent
                delta_mean = mean_duration_unidad - mean_duration if not pd.isna(mean_duration_unidad) else np.nan

                with st.container(border=True):
                    cols = st.columns([2, 1, 1, 1, 1])
                    with cols[0]:
                        st.info(f"**{code}** - {unidad}")
                    
                    cols[1].metric("Expedientes iniciados", total_unidad)
                    cols[2].metric("Expedientes finalizados", finalized_unidad)
                    
                    cols[3].metric(
                        "% Finalizados",
                        f"{finalized_percent_unidad:.1f}%",
                        delta=f"{delta_percent:.1f}%" if not np.isnan(delta_percent) else None,
                        delta_color="normal" 
                    )
                    
                    cols[4].metric(
                        "Tiempo Medio", 
                        f"{mean_duration_unidad:.0f} días" if not pd.isna(mean_duration_unidad) else "N/A",
                        delta=f"{delta_mean:.0f} días" if not np.isnan(delta_mean) else None,
                        delta_color="inverse" 
                    )
