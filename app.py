# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 19:06:10 2025

@author: flipe
"""

import streamlit as st
import pandas as pd

# 1. Set page configuration as early as possible
st.set_page_config(
    page_title="Análisis de proceso",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Initialize session state using .get() for consistency
if 'filtered_data' not in st.session_state:
    st.session_state.filtered_data = None
if 'final_states' not in st.session_state:
    st.session_state.final_states = None
if 'selected_final_states' not in st.session_state:  # note: key name aligned with later usage
    st.session_state.selected_final_states = []
if 'selected_procedure' not in st.session_state:
    st.session_state.selected_procedure = None

# 3. Cache functions for loading and filtering data
@st.cache_data
def load_process_codes():
    df = pd.read_csv(
        "data/codigos_procedimientos.csv",
        sep=";",
        usecols=["codigo_procedimiento", "descripcion"]
    )
    # Convert the DataFrame into a dictionary mapping code -> description
    return df.set_index("codigo_procedimiento")["descripcion"].to_dict()

@st.cache_data
def load_base_data(codigo):
    base_path = f"data/tratados/{codigo}"
    # Lista de columnas a cargar (personaliza con las que necesites)
    columnas_expedientes = [
        'id_exp',
        'fecha_registro_exp',
        'codine_provincia',
        'codine',
        'municipio',
        'provincia',
        'dni',
        'nif',
        'es_telematica'
        
    ]
    return {
        'expedientes': pd.read_parquet(
            f"{base_path}/expedientes.parquet",
            columns=columnas_expedientes  # Filtrado de columnas
        ),
        'tramites': pd.read_parquet(f"{base_path}/tramites.parquet"),
        'final_states': pd.read_csv(f"{base_path}/estados_finales.csv", sep=";", encoding='utf-8')
    }

@st.cache_data
def filter_data(_expedientes, _tramites, date_range):
    start_date, end_date = date_range
    mask = (
        (_expedientes['fecha_registro_exp'].dt.date >= start_date) &
        (_expedientes['fecha_registro_exp'].dt.date <= end_date)
    )
    filtered_exp = _expedientes[mask].copy()
    expediente_ids = filtered_exp['id_exp'].unique()
    return {
        'expedientes': filtered_exp,
        'tramites': _tramites[_tramites['id_exp'].isin(expediente_ids)]
    }

# 4. Sidebar: Group all interactive controls
with st.sidebar:
    # Process selection
    processes = load_process_codes()  # returns dict {codigo: descripcion}
    selected_procedure = st.session_state.get('selected_procedure', None)
    process_keys = list(processes.keys())
    default_index = process_keys.index(selected_procedure) if selected_procedure in process_keys else 0

    selected_desc = st.selectbox(
        "Selecciona Procedimiento",
        options=list(processes.values()),
        index=default_index,
        help="Elige un procedimiento"
    )

    # Get selected code from the dictionary by matching description
    selected_codigo = [k for k, v in processes.items() if v == selected_desc][0]

    # Load data for the selected procedure
    base_data = load_base_data(selected_codigo)
    
    # Save base data's final_states and procedure code into session state
    st.session_state.final_states = base_data['final_states']
    st.session_state.selected_procedure = selected_codigo

    # Date range selection based on expedientes
    min_date = base_data['expedientes']['fecha_registro_exp'].min().date()
    max_date = base_data['expedientes']['fecha_registro_exp'].max().date()
    selected_dates = st.slider(
        "Rango de fechas",
        min_value=min_date,
        max_value=max_date,
        value=(min_date, max_date),
        format="DD-MM-YYYY"
    )
    
    # Filter data based on date range and cache it
    st.session_state.filtered_data = filter_data(
        base_data['expedientes'],
        base_data['tramites'],
        selected_dates
    )

    # Multi-select for final states
    # Filter final_states to only those rows with FINAL == 1
    df_final_states_1 = base_data['final_states'][base_data['final_states']['FINAL'] == 1]
    # Build a dictionary mapping from state label to its code using all rows
    state_options = {
        row['DENOMINACION_SIMPLE']: row['NUMTRAM']
        for _, row in base_data['final_states'][['NUMTRAM', 'DENOMINACION_SIMPLE']].drop_duplicates().iterrows()
    }
    # Default: only those states with FINAL == 1
    default_states = df_final_states_1['DENOMINACION_SIMPLE'].unique().tolist()
    selected_final_states_ms = st.multiselect(
        "Seleccionar estados finales",
        options=list(state_options.keys()),
        default=default_states,
        help="Selecciona uno o varios estados finales"
    )
    # Convert selected state labels to their corresponding codes
    selected_final_states = [state_options[denom] for denom in selected_final_states_ms]
    st.session_state.selected_final_states = selected_final_states

# 5. Navigation / Page definitions
# NOTE: The st.Page and st.navigation APIs are not part of the official Streamlit API.
# If you are using a custom or experimental navigation solution, ensure you follow its guidelines.
demanda_temporal = st.Page("input_temporal.py", title="Análisis temporal", icon="📋")
demanda_geografico = st.Page("input_geografico.py", title="Análisis geográfico", icon="🌍")
flujo_diagrama = st.Page("flujo_diagrama.py", title="Diagrama", icon="🔀")
flujo_temporal = st.Page("flujo_temporal.py", title="Análisis temporal", icon="⏳")
estado_temporal = st.Page("estados_temporal.py", title="Cuellos de botella", icon="🎯")
estado_acumulado = st.Page("estados_acumulado.py", title="Carga de trabajo", icon="▶️")

nav = st.navigation({
    "Demanda": [demanda_temporal, demanda_geografico],
    "Flujo Proceso": [flujo_diagrama, flujo_temporal],
    "Cuellos de botella": [estado_temporal, estado_acumulado]
})
nav.run()
