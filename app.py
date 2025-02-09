# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 19:06:10 2025

@author: flipe
"""

import streamlit as st
import pandas as pd
import datetime

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
if 'selected_final_states' not in st.session_state:  # note: key name aligned with later usage
    st.session_state.selected_final_states = []
if 'selected_procedure' not in st.session_state:
    st.session_state.selected_procedure = None
if 'estados' not in st.session_state:
    st.session_state.estados = None

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
    
    # EXPEDIENTES
    #############
    # Lista de columnas a cargar (incluyendo 'nif' para 'es_empresa')
    columnas_expedientes = [
        'id_exp',
        'fecha_registro_exp',
        'codine_provincia',
        'codine',
        'municipio',
        'provincia',
        'es_telematica',
        'nif'        
    ]

    expedientes = pd.read_parquet(
        f"{base_path}/expedientes.parquet",
        columns=columnas_expedientes  # Filtrado de columnas
    )
    
    # Creación de nuevas columnas
    expedientes['es_online'] = expedientes['es_telematica'].fillna(False)
    expedientes['es_empresa'] = expedientes['nif'].notnull()
    # Eliminar 'nif' del DataFrame
    expedientes = expedientes.drop(columns=['nif'])
    
    # TRAMITES
    ###########
    columnas_tramites = [
        'id_exp',
        'es_telematica',
        'nif',
        'unidad_tramitadora',
        'denominacion',
        'descripcion',
        'consejeria',
        'org_instructor',
        'municipio',
        'provincia',
        'fecha_tramite',
        'num_tramite' 
    ]   
    tramites = pd.read_parquet(
        f"{base_path}/tramites.parquet",
        columns=columnas_tramites  # Filtrado de columnas
    )
    
    # Creación de nuevas columnas
    tramites['es_online'] = tramites['es_telematica'].fillna(False)
    tramites['es_empresa'] = tramites['nif'].notnull()  
    # Eliminar 'nif' del DataFrame
    tramites = tramites.drop(columns=['nif'])
     
    return {
        'expedientes': expedientes,
        'tramites': tramites,
        'estados': pd.read_csv(f"{base_path}/estados_finales.csv", sep=";", encoding='utf-8')
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

    
    def process_selector_callback():
        st.session_state.filtered_data = None
        st.session_state.selected_final_states = []
        st.session_state.selected_procedure = st.session_state.process_selector

    # carga los procedimientos activados en data/codigos_procedimientos.csv
    processes = load_process_codes()  # returns dict {codigo: descripcion}
    
    process_keys = list(processes.keys())
    process_descs = [processes[k] for k in process_keys]
    
    selected_procedure = st.session_state.get('selected_procedure', None)
    default_index = process_keys.index(selected_procedure) if selected_procedure in process_keys else 0
    
    selected_desc = st.selectbox(
        "Selecciona Procedimiento",
        options=process_descs,
        index=default_index,
        key="process_selector",
        on_change=process_selector_callback,
        help="Elige un procedimiento"
    )

    # Map the selected description back to its code
    selected_codigo = [k for k, v in processes.items() if v == selected_desc][0]

    # Load data for the selected procedure
    base_data = load_base_data(selected_codigo)

    # Store estados in session state
    st.session_state.estados = base_data['estados'] 

    # Check if the stored texts do not exist or the selected procedure has changed.
    if ("tramites_texts" not in st.session_state) or (st.session_state.get("selected_procedure") != selected_codigo):
        # Extract the values (assuming all rows have the same values, so we take the first row)
        tramites_texts = base_data["tramites"][["denominacion", "descripcion", "consejeria", "org_instructor"]].iloc[0].to_dict()
        # Store them in session state for reuse on other pages
        st.session_state.tramites_texts = tramites_texts
    
        # Remove these columns from the 'tramites' DataFrame to save memory
        base_data["tramites"] = base_data["tramites"].drop(columns=["denominacion", "descripcion", "consejeria", "org_instructor"])
    
    # Optionally, update the selected procedure in session state for later comparisons
    st.session_state.selected_procedure = selected_codigo

    # Date range selection based on expedientes
  
    original_start = base_data['expedientes']['fecha_registro_exp'].min().date()
    original_end = base_data['expedientes']['fecha_registro_exp'].max().date()
    min_date = max(original_start, datetime.date(2010, 1, 1))
    max_date = min(original_end, datetime.date.today())
    
    selected_dates = st.slider(
        "Rango de fechas",
        min_value=min_date,
        max_value=max_date,
        value=(min_date, max_date),
        format="DD-MM-YYYY"
    )

    # Multi-select for final states
    df_final_states_1 = base_data['estados'][base_data['estados']['FINAL'] == 1]
    state_options = {
        row['DENOMINACION_SIMPLE']: row['NUMTRAM']
        for _, row in base_data['estados'][['NUMTRAM', 'DENOMINACION_SIMPLE']].drop_duplicates().iterrows()
    }
    default_states = df_final_states_1['DENOMINACION_SIMPLE'].unique().tolist()
    selected_final_states_ms = st.multiselect(
        "Seleccionar estados finales",
        options=list(state_options.keys()),
        default=default_states,
        help="Selecciona uno o varios estados finales"
    )
    selected_final_states = [state_options[denom] for denom in selected_final_states_ms]

    # Update session state with new values
    st.session_state.filtered_data = filter_data(
        base_data['expedientes'],
        base_data['tramites'],
        selected_dates
    )
    st.session_state.selected_final_states = selected_final_states



# 5. Navigation / Page definitions
# NOTE: The st.Page and st.navigation APIs are not part of the official Streamlit API.
# If you are using a custom or experimental navigation solution, ensure you follow its guidelines.
flujo_diagrama = st.Page("flujo_diagrama.py", title="Diagrama", icon="🔀")
flujo_temporal = st.Page("flujo_temporal.py", title="Análisis temporal", icon="⏳")
demanda_temporal = st.Page("input_temporal.py", title="Temporal", icon="📋")
demanda_geografico = st.Page("input_geografico.py", title="Geográfico", icon="🌍")
estado_temporal = st.Page("estados_temporal.py", title="Cuellos de botella", icon="🎯")
estado_acumulado = st.Page("estados_acumulado.py", title="Carga de trabajo", icon="▶️")

nav = st.navigation({
    "Visión general Proceso": [flujo_diagrama, flujo_temporal],
    "Análisis de la demanda": [demanda_temporal, demanda_geografico],
    "Cuellos de botella": [estado_temporal, estado_acumulado]
})
nav.run()
