# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 19:19:20 2025

@author: flipe
"""

import streamlit as st
import pandas as pd

# Ensure that the main page has already set the filtered data in session state
if "filtered_data" not in st.session_state:
    st.error("Filtered data not found. Please load the main page first.")
    st.stop()

# Retrieve the 'tramites' DataFrame from session state
tramites_df = st.session_state.filtered_data.get("tramites")
if tramites_df is None:
    st.error("Trámites data is not available in the filtered data.")
    st.stop()

# Retrieve the cached common text columns from session state
if "tramites_texts" not in st.session_state:
    st.error("Tramites texts not found. Please load the main page first.")
    st.stop()

tramites_texts = st.session_state.tramites_texts

if 'estados' in st.session_state:
    estados_df = st.session_state.estados
    
    
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
    
    # Option 1: Display the first few rows of the DataFrame
    st.dataframe(tramites_df.head(), use_container_width=True)


# You can later fill in tab2, tab3, and tab4 with additional content.
with tab2:
    st.info("Content for Tab 2 goes here.")

with tab3:
    st.info("Content for Tab 3 goes here.")

with tab4:
    st.info("Content for Tab 4 goes here.")
