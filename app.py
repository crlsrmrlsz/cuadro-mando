# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 19:06:10 2025

@author: flipe
"""
import streamlit as st
from datetime import date

# Initialize session state for filters
if 'fecha_inicio' not in st.session_state:
    st.session_state.fecha_inicio = date(2023, 1, 1)
if 'fecha_fin' not in st.session_state:
    st.session_state.fecha_fin = date.today()

# Configure page settings
st.set_page_config(
    page_title="Análisis de proceso",
    page_icon="📊",
    layout="wide"
)

# Common sidebar with persistent filters
with st.sidebar:
    st.title("Filtros Globales")
    st.session_state.fecha_inicio = st.date_input(
        "Fecha inicio",
        value=st.session_state.fecha_inicio
    )
    st.session_state.fecha_fin = st.date_input(
        "Fecha fin",
        value=st.session_state.fecha_fin
    )

# Define navigation with explicit pages
nav = st.navigation([
    st.Page("input.py", title="Demanda", icon="📋"),
    st.Page("bottleneck.py", title="Cuellos de botella", icon="🎯"),
    st.Page("flows.py", title="Flujos de proceso", icon="🔀"),
    st.Page("geo.py", title="Comparativa geográfica", icon="🌍")
])

nav.run()