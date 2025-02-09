# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 19:19:20 2025

@author: flipe
"""

import streamlit as st
import pandas as pd


@st.cache_data
def get_state_names(estados_df):
    return estados_df.set_index('NUMTRAM')['DENOMINACION_SIMPLE'].astype('category').to_dict()

@st.cache_data
def process_tramites_final(_tramites, selected_states, date_range):
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
selected_dates = st.session_state.get('selected_dates', (None, None))
state_names = get_state_names(st.session_state.estados)
selected_states = [int(s) for s in st.session_state.selected_final_states]
tramites_texts = st.session_state.tramites_texts

# Process data with date range awareness
filtered_processed = process_tramites_final(
    st.session_state.filtered_data['tramites'],
    selected_states,
    selected_dates  # Critical cache key element
)

base_processed = process_tramites_final(
    st.session_state.base_data['tramites'],
    selected_states,
    ("base_data",)  # Static identifier for base data
)

# # Ensure that the main page has already set the filtered data in session state
# if "filtered_data" not in st.session_state:
#     st.error("Filtered data not found. Please load the main page first.")
#     st.stop()

# # Retrieve the 'tramites' DataFrame from session state
# tramites_df = st.session_state.filtered_data.get("tramites")

# if tramites_df is None:
#     st.error("Trámites data is not available in the filtered data.")
#     st.stop()

# # Retrieve the cached common text columns from session state
# if "tramites_texts" not in st.session_state:
#     st.error("Tramites texts not found. Please load the main page first.")
#     st.stop()

# tramites_texts = st.session_state.tramites_texts

# if 'estados' in st.session_state:
#     estados_df = st.session_state.estados
    
    
# Use the cached texts for the title and description
st.subheader(f"{tramites_texts['descripcion']}")
#st.subheader(f"{tramites_texts['denominacion']}")
st.markdown(
    f"**Consejería:** {tramites_texts['consejeria']}  \n"
    f"**Organismo Instructor:** {tramites_texts['org_instructor']}"
)

# Create a four-tab layout
tab1, tab2, tab3, tab4 = st.tabs(["Datos generales", "Tab 2", "Tab 3", "Tab 4"])

with tab1:

    # Filter and display metrics
    filtered_final = filtered_processed[filtered_processed['contains_selected']]
    base_final = base_processed[base_processed['contains_selected']]
    
    for state_num in selected_states:
        state_name = state_names.get(state_num, f"State {state_num}")
        
        state_count = filtered_final['all_states'].apply(lambda x: state_num in x).sum()
        state_durations = filtered_final[filtered_final['all_states'].apply(lambda x: state_num in x)]['duration_days']
        filtered_mean = state_durations.mean()
        
        base_durations = base_final[base_final['all_states'].apply(lambda x: state_num in x)]['duration_days']
        base_mean = base_durations.mean()
    
        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                label=f"Processes through {state_name}",
                value=state_count,
                help=f"Processes passing through {state_name} in date range"
            )
            
        with col2:
            st.metric(
                label=f"Mean Duration ({state_name})",
                value=f"{filtered_mean:.1f} days" if not pd.isna(filtered_mean) else "N/A",
                delta=f"{(filtered_mean - base_mean):.1f} vs global" if not pd.isna(filtered_mean) else None,
                delta_color="inverse"
            )
    


# You can later fill in tab2, tab3, and tab4 with additional content.
with tab2:
    st.info("Content for Tab 2 goes here.")
    # Option 1: Display the first few rows of the DataFrame
    st.dataframe(tramites_df.head(), use_container_width=True)
with tab3:
    st.info("Content for Tab 3 goes here.")

with tab4:
    st.info("Content for Tab 4 goes here.")
