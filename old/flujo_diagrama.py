# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 19:19:20 2025

@author: flipe
"""

import streamlit as st
import pandas as pd


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

if "tramites_texts" not in st.session_state:
    st.error("Tramites texts not found. Please load the main page first.")
    st.stop()

# Get required session state values
selected_procedure = st.session_state.selected_procedure
selected_dates = st.session_state.get('selected_dates', (None, None))
state_names = get_state_names(st.session_state.estados, selected_procedure)
selected_states = [int(s) for s in st.session_state.selected_final_states]
tramites_texts = st.session_state.tramites_texts

# Process data with date range awareness
filtered_processed = process_tramites_final(
    st.session_state.filtered_data['tramites'],
    selected_states,
    selected_dates,  # Critical cache key element
    selected_procedure
)

base_processed = process_tramites_final(
    st.session_state.base_data['tramites'],
    selected_states,
    ("base_data",),  # Static identifier for base data
    selected_procedure
)


    


# Create a four-tab layout
tab1, tab2, tab3, tab4 = st.tabs(["Datos generales", "Flujos principales", "Diagrama", "Tab 4"])

with tab1:
    # Use the cached texts for the title and description
    st.subheader(f"{tramites_texts['descripcion']}")
    st.markdown(
        f"**Consejería:** {tramites_texts['consejeria']}  \n"
        f"**Organismo Instructor:** {tramites_texts['org_instructor']}"
    )
    
    if "filtered_data" in st.session_state and "base_data" in st.session_state:
        base_expedientes = st.session_state.base_data['expedientes']
        base_processed = process_tramites_final(
            st.session_state.base_data['tramites'],
            selected_states,
            ("base_data",),
            selected_procedure
        )
        filtered_processed = process_tramites_final(
            st.session_state.filtered_data['tramites'],
            selected_states,
            selected_dates,
            selected_procedure
        )

        # --- General Metrics ---
        total_processes = len(base_processed)
        finalized_count = base_processed['contains_selected'].sum()
        finalized_percent = (finalized_count / total_processes * 100) if total_processes > 0 else 0
        mean_duration = base_processed[base_processed['contains_selected']]['duration_days'].mean()

        col_gen1, col_gen2, col_gen3 = st.columns(3)
        with col_gen1:
            st.metric("Total Expedientes iniciados", f"{total_processes:,}", border = True)
        with col_gen2:
            st.metric("Finalizados", f"{finalized_percent:.1f}%", border = True)
        with col_gen3:
            value = f"{mean_duration:.0f} días" if not pd.isna(mean_duration) else "N/A"
            st.metric("Tiempo medio", value, border = True)

        #se muestra info por esado final si hay más de uno seleccionado
        if (len(selected_states)>1):
            #st.divider()

            st.caption("Volumen y tiempos de expedientes que pasan por los estados seleccionados como finales. Si el estado seleccionado no es el último, los datos representan el tiempo hasta finalizar por completo esos expedientes")
            # --- State-wise Metrics ---
            state_names = get_state_names(st.session_state.estados, selected_procedure)
            for state_num in selected_states:
                state_name = state_names.get(state_num, f"State {state_num}")
                
                # Base metrics
                mask = base_processed['all_states'].apply(lambda x: state_num in x)
                state_count_base = mask.sum()
                state_percent_base = (state_count_base / total_processes * 100) if total_processes > 0 else 0
                state_mean_base = base_processed[mask]['duration_days'].mean()
    
                # Create columns
                cols = st.columns([1,1, 1, 1, 2], vertical_alignment="bottom")
                #cols[0].markdown("Expedientes que pasan por")
                cols[0].success(f"**{state_name}**")
                cols[2].metric("Expedientes", state_count_base)
                cols[3].metric("Sobre Total", f"{state_percent_base:.1f}%")
                value = f"{state_mean_base:.0f} días" if not pd.isna(state_mean_base) else "N/A"
                cols[4].metric("Tiempo Medio", value)

        st.divider()
        
        # --- Comparison Section ---
        compare = st.checkbox("Comparar datos para el rango de fechas seleccionado")
        if compare:
            
            selected_min_date, selected_max_date = selected_dates
            st.markdown(f":red[Datos para expedientes iniciados entre **{selected_min_date}** y  **{selected_max_date}**]")
            # Filtered metrics
            filtered_total = len(filtered_processed)
            filtered_finalized = filtered_processed['contains_selected'].sum()
            filtered_percent = (filtered_finalized / filtered_total * 100) if filtered_total > 0 else 0
            filtered_duration = filtered_processed[filtered_processed['contains_selected']]['duration_days'].mean()
        
            cols = st.columns(3)
            cols[0].metric("Expedientes en rango", filtered_total, border = True)
            cols[1].metric("Finalizados", f"{filtered_percent:.1f}%", border = True)
            value = f"{filtered_duration:.0f} días" if not pd.isna(filtered_duration) else "N/A"
            cols[2].metric("Tiempo medio", value, border = True)
        
            for state_num in selected_states:
                state_name = state_names.get(state_num, f"State {state_num}")
                
                # Filtered metrics
                mask = filtered_processed['all_states'].apply(lambda x: state_num in x)
                state_count_filtered = int(mask.sum())
                state_percent_filtered = int((state_count_filtered / filtered_total * 100)) if filtered_total > 0 else 0
                state_mean_filtered = int(filtered_processed[mask]['duration_days'].mean())
        
                # Base metrics for comparison
                mask_base = base_processed['all_states'].apply(lambda x: state_num in x)
                state_count_base = int(mask_base.sum())
                state_percent_base = int((state_count_base / total_processes * 100)) if total_processes > 0 else 0
                state_mean_base = int(base_processed[mask_base]['duration_days'].mean())
        
                # Create columns with deltas
                cols = st.columns([1,1, 1, 1, 2], vertical_alignment="bottom")
                cols[0].success(f"**{state_name}**")
                
                # Delta for "Número"
                delta_num = state_count_filtered - state_count_base
                delta_num_param = delta_num if delta_num != 0 else None
                cols[2].metric("Número", state_count_filtered, delta=delta_num_param)
                
                # Delta for "% Total"
                delta_percent = state_percent_filtered - state_percent_base
                delta_percent_param = f"{delta_percent:.1f}%" if delta_percent != 0 else None
                cols[3].metric("% Total", f"{state_percent_filtered:.1f}%", delta=delta_percent_param)
                
                # Delta for "Tiempo Medio"
                value = f"{state_mean_filtered:.0f} días" if not pd.isna(state_mean_filtered) else "N/A"
                delta_mean = int(state_mean_filtered - state_mean_base) if not pd.isna(state_mean_filtered) else None
                delta_mean_param = f"{delta_mean:.0f} días" if delta_mean not in (0, None) else None
                cols[4].metric("Tiempo Medio", value, delta=delta_mean_param, delta_color="inverse")
                     

# You can later fill in tab2, tab3, and tab4 with additional content.
with tab2:
    st.info("Content for Tab 2 goes here.")
    # Option 1: Display the first few rows of the DataFrame
    st.dataframe(tramites_df.head(), use_container_width=True)
with tab3:
    st.info("Content for Tab 3 goes here.")

with tab4:
    st.info("Content for Tab 4 goes here.")
