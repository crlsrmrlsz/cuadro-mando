# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 19:06:10 2025

@author: flipe
"""
import streamlit as st
from datetime import date
import pandas as pd
import os

# Configure page settings
st.set_page_config(
    page_title="Análisis de proceso",
    page_icon="📊",
    layout="wide"
)

# Load the list of procedures from the CSV file
@st.cache_data
def load_procedures():
    procedures_df = pd.read_csv("data/codigos_procedimientos.csv", encoding='utf-8')
    return procedures_df

procedures_df = load_procedures()

# Initialize session state for filters
if 'fecha_inicio' not in st.session_state:
    st.session_state.fecha_inicio = date(2023, 1, 1)
if 'fecha_fin' not in st.session_state:
    st.session_state.fecha_fin = date.today()
if 'selected_procedure' not in st.session_state:
    st.session_state.selected_procedure = None
if 'dataframe' not in st.session_state:
    st.session_state.dataframe = None

# Common sidebar with persistent filters
with st.sidebar:
    st.title("Filtros Globales")
    
    # Dropdown to select a procedure
    selected_procedure_name = st.selectbox(
        "Seleccione un procedimiento",
        options=procedures_df['nombre_procedimiento'].tolist(),
        index=0 if st.session_state.selected_procedure is None else procedures_df['nombre_procedimiento'].tolist().index(st.session_state.selected_procedure)
    )
    
    # Get the corresponding codigo_procedimiento
    selected_procedure = procedures_df[procedures_df['nombre_procedimiento'] == selected_procedure_name]['codigo_procedimiento'].iloc[0]
    
    # Load the corresponding Parquet file if a new procedure is selected
    if st.session_state.selected_procedure != selected_procedure:
        st.session_state.selected_procedure = selected_procedure
        parquet_path = f"data/{selected_procedure}/expedientes.parquet"
        if os.path.exists(parquet_path):
            st.session_state.dataframe = pd.read_parquet(parquet_path)
            min_date = st.session_state.dataframe['fecha'].min().date()
            max_date = st.session_state.dataframe['fecha'].max().date()
            st.session_state.fecha_inicio = min_date
            st.session_state.fecha_fin = max_date
        else:
            st.error(f"No se encontró el archivo Parquet para el procedimiento {selected_procedure_name}.")
            st.session_state.dataframe = None
    
    # Display date inputs and slider only if a procedure is selected
    if st.session_state.selected_procedure is not None and st.session_state.dataframe is not None:
        st.session_state.fecha_inicio = st.date_input(
            "Fecha inicio",
            value=st.session_state.fecha_inicio,
            min_value=st.session_state.dataframe['fecha'].min().date(),
            max_value=st.session_state.dataframe['fecha'].max().date()
        )
        st.session_state.fecha_fin = st.date_input(
            "Fecha fin",
            value=st.session_state.fecha_fin,
            min_value=st.session_state.dataframe['fecha'].min().date(),
            max_value=st.session_state.dataframe['fecha'].max().date()
        )
        
        # Date slider
        selected_range = st.slider(
            "Seleccione un rango de fechas",
            min_value=st.session_state.dataframe['fecha'].min().date(),
            max_value=st.session_state.dataframe['fecha'].max().date(),
            value=(st.session_state.fecha_inicio, st.session_state.fecha_fin)
        )
        st.session_state.fecha_inicio, st.session_state.fecha_fin = selected_range

# Define navigation with explicit pages
nav = st.navigation([
    st.Page("input.py", title="Demanda", icon="📋"),
    st.Page("bottleneck.py", title="Cuellos de botella", icon="🎯"),
    st.Page("flows.py", title="Flujos de proceso", icon="🔀"),
    st.Page("geo.py", title="Comparativa geográfica", icon="🌍")
])

nav.run()
