# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 19:19:20 2025

@author: flipe
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

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

# General Metrics for filtered data in bordered container
with st.container(border=True):
    
    
    total_processes = len(filtered_processed)
    finalized_count = filtered_processed['contains_selected'].sum()
    finalized_percent = (finalized_count / total_processes * 100) if total_processes > 0 else 0
    mean_duration = filtered_processed[filtered_processed['contains_selected']]['duration_days'].mean()

    col_gen1, col_gen2, col_gen3, col_gen4 = st.columns(4)
    with col_gen1:
        st.subheader("Datos generales")
    with col_gen2:
        st.metric("Total Expedientes iniciados", f"{total_processes:,}")
    with col_gen3:
        st.metric("Finalizados", f"{finalized_percent:.1f}%")
    with col_gen4:
        value = f"{mean_duration:.0f} días" if not pd.isna(mean_duration) else "N/A"
        st.metric("Tiempo medio", value)

    # State-wise metrics in bordered container
    if len(selected_states) > 0 and st.checkbox("Mostrar estadísticas por estado final", value= False):
        #st.subheader("Datos para cada estado final")
        st.caption("Volumen y tiempos de expedientes que pasan por los estados seleccionados como finales. Si el estado seleccionado no es el último, los datos representan el tiempo hasta finalizar por completo esos expedientes")
    
        for state_num in selected_states:
            state_name = state_names.get(state_num, f"State {state_num}")
            
            mask = filtered_processed['all_states'].apply(lambda x: state_num in x)
            state_count = mask.sum()
            state_percent = (state_count / total_processes * 100) if total_processes > 0 else 0
            state_mean = filtered_processed[mask]['duration_days'].mean()

            cols = st.columns([2, 1, 1, 1])
            cols[0].info(f"**{state_name}**")
            cols[1].metric("Expedientes finalizados en este estado", state_count)
            cols[2].metric("% del Total", f"{state_percent:.1f}%")
            value = f"{state_mean:.0f} días" if not pd.isna(state_mean) else "N/A"
            cols[3].metric("Tiempo Medio", value)

# Unidad Tramitadora comparison
if 'unidad_tramitadora' in filtered_processed.columns:
    # Create code mapping for long unidad names
    unidades_series = filtered_processed['unidad_tramitadora'].fillna('No especificada')
    unique_unidades = unidades_series.unique()
    unidad_codes = {unidad: f'UT{i+1}' for i, unidad in enumerate(sorted(unique_unidades))}
    color_sequence = px.colors.qualitative.Plotly  # Use plotly's default color sequence
    
    unidades_series_coded = unidades_series.map(unidad_codes)
    filtered_processed['unidad_code'] = unidades_series_coded

    # Filter out unidades with 0 expedientes
    unidades_validas = unidades_series[unidades_series.isin(unidades_series.value_counts()[unidades_series.value_counts() > 0].index)]
    n_unidades = len(unidades_validas.unique())
    
    if n_unidades > 1:
        with st.container(border=True):
            st.subheader("Comparación por Unidad Tramitadora")
            
            # Create color mapping dictionary
            color_mapping = {code: color_sequence[i % len(color_sequence)] 
                            for i, code in enumerate(sorted(unidad_codes.values()))}
            
            # Create two columns for charts
            col1, col2 = st.columns(2)
            
            with col1:
                # Pie chart with coded names and consistent colors
                fig_pie = px.pie(filtered_processed, 
                                names='unidad_code',
                                color='unidad_code',
                                color_discrete_map=color_mapping,
                                title="Distribución de Expedientes",
                                height=400)
                fig_pie.update_layout(showlegend=False)
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                # Bar chart with matching colors
                duration_df = filtered_processed[filtered_processed['contains_selected']].groupby('unidad_code')['duration_days'].mean().reset_index()
                fig_bar = px.bar(duration_df, 
                                x='unidad_code',
                                y='duration_days',
                                color='unidad_code',
                                color_discrete_map=color_mapping,
                                title="Tiempo Medio de Finalización",
                                labels={'duration_days': 'Días', 'unidad_code': 'Unidad'},
                                height=400)
                fig_bar.update_layout(yaxis_title="Días", showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)
            
            # Add unified legend
            legend_df = pd.DataFrame([
                {'Código': code, 'Nombre': name, 'Color': color_mapping[code]}
                for name, code in unidad_codes.items()
                if name in unidades_validas.unique()
            ])
            

            st.markdown("**Códigos de Unidades Tramitadoras:**")
            for _, row in legend_df.iterrows():
                st.markdown(f"<span style='color:{row['Color']}'>■</span> **{row['Código']}**: {row['Nombre']}", 
                          unsafe_allow_html=True)

            # Process each unidad with correct delta colors
            for unidad in unidades_validas.unique():
                mask = unidades_series == unidad
                unidad_data = filtered_processed[mask]
                code = unidad_codes[unidad]
                
                total_unidad = len(unidad_data)
                finalized_unidad = unidad_data['contains_selected'].sum()
                finalized_percent_unidad = (finalized_unidad / total_unidad * 100) if total_unidad > 0 else 0
                mean_duration_unidad = unidad_data[unidad_data['contains_selected']]['duration_days'].mean()
                
                # Calculate deltas
                delta_percent = finalized_percent_unidad - finalized_percent
                delta_mean = mean_duration_unidad - mean_duration if not pd.isna(mean_duration_unidad) else np.nan

               
                # Display metrics with proper delta coloring
                with st.container(border=True):
                    cols = st.columns([2, 1, 1, 1, 1])
                    cols[0].markdown(f"**{code}** - {unidad}")
                    cols[1].metric("Expedientes iniciados", total_unidad)
                    cols[2].metric("Expedientes finalizados", finalized_unidad)
                    
                    # Percent finalized delta
                    cols[3].metric(
                        "% Finalizados",
                        f"{finalized_percent_unidad:.1f}%",
                        delta=f"{delta_percent:.1f}%" if not np.isnan(delta_percent) else None,
                        delta_color="normal" if delta_percent >= 0 else "inverse"
                    )
                    
                    # Mean duration delta
                    cols[4].metric(
                        "Tiempo Medio", 
                        f"{mean_duration_unidad:.0f} días" if not pd.isna(mean_duration_unidad) else "N/A",
                        delta=f"{delta_mean:.0f} días" if not np.isnan(delta_mean) else None,
                        delta_color="inverse" if delta_mean > 0 else "normal"  # Red if longer than average
                    )