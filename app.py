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
if 'datos_base' not in st.session_state:
    st.session_state.datos_base = None
if 'datos_filtrados_rango' not in st.session_state:
    st.session_state.datos_filtrados_rango = None
if 'estados_finales_selecc' not in st.session_state:  # note: key name aligned with later usage
    st.session_state.estados_finales_selecc = []
if 'proced_seleccionado' not in st.session_state:
    st.session_state.proced_seleccionado = None
if 'estados' not in st.session_state:
    st.session_state.estados = None

# 3. Cache functions for loading and filtering data
@st.cache_data
def carga_codigos_procedimientos():
    df = pd.read_csv(
        "data/codigos_procedimientos.csv",
        sep=";",
        usecols=["codigo_procedimiento", "descripcion"]
    )
    # Convert the DataFrame into a dictionary mapping code -> description
    return df.set_index("codigo_procedimiento")["descripcion"].to_dict()

FECHA_MINIMA = pd.Timestamp("2015-01-01")

@st.cache_data(show_spinner="Cargando datos de procedimiento")
def carga_datos_base(codigo):
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
    expedientes = expedientes.drop(columns=['nif','es_telematica'])
    
    # 1. Filtrar expedientes con fecha_registro_exp > fecha_minima
    expedientes = expedientes[expedientes['fecha_registro_exp'] > FECHA_MINIMA].copy()
    
    
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
    tramites = tramites.drop(columns=['nif','es_telematica'])
    
    # 2. Quedarse solo con tramites de los expedientes filtrados
    tramites = tramites[tramites['id_exp'].isin(expedientes['id_exp'])].copy()
    
    # 3. Identificar expedientes que tengan algún tramite con fecha_tramite < fecha_minima
    expedientes_a_eliminar = tramites.loc[tramites['fecha_tramite'] < FECHA_MINIMA, 'id_exp'].unique()
    
    # 4. Eliminar de ambos DataFrames los expedientes identificados
    expedientes = expedientes[~expedientes['id_exp'].isin(expedientes_a_eliminar)].copy()
    tramites = tramites[~tramites['id_exp'].isin(expedientes_a_eliminar)].copy()
    
    
    return {
        'expedientes': expedientes,
        'tramites': tramites,
        'estados': pd.read_csv(f"{base_path}/estados_finales.csv", sep=";", encoding='utf-8')
    }

@st.cache_data(show_spinner="Filtrando datos para el rango de fechas seleccionado")
def filtra_datos_fechas(_expedientes, _tramites, rango_fechas):
    start_date, end_date = rango_fechas
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
        st.session_state.datos_filtrados_rango = None
        st.session_state.estados_finales_selecc = []
        st.session_state.proced_seleccionado = st.session_state.process_selector

    # carga los procedimientos activados en data/codigos_procedimientos.csv
    processes = carga_codigos_procedimientos()  # returns dict {codigo: descripcion}
    
    process_keys = list(processes.keys())
    process_descs = [processes[k] for k in process_keys]
    
    proced_seleccionado = st.session_state.get('proced_seleccionado', None)
    default_index = process_keys.index(proced_seleccionado) if proced_seleccionado in process_keys else 0
    
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
    datos_base = carga_datos_base(selected_codigo)

    # Store estados in session state
    st.session_state.estados = datos_base['estados'] 

    # Check if the stored texts do not exist or the selected procedure has changed.
    if ("textos_procedimiento" not in st.session_state) or (st.session_state.get("proced_seleccionado") != selected_codigo):
        # Extract the values (assuming all rows have the same values, so we take the first row)
        textos_procedimiento = datos_base["tramites"][["denominacion", "descripcion", "consejeria", "org_instructor"]].iloc[0].to_dict()
        # Store them in session state for reuse on other pages
        st.session_state.textos_procedimiento = textos_procedimiento
    
    # Remove these columns from the 'tramites' DataFrame to save memory
    datos_base["tramites"] = datos_base["tramites"].drop(columns=["denominacion", "descripcion", "consejeria", "org_instructor"])
    
    # In main page after loading datos_base:
    st.session_state.datos_base = datos_base
    
    
    # Optionally, update the selected procedure in session state for later comparisons
    st.session_state.proced_seleccionado = selected_codigo

    # Date range selection based on expedientes
    ##############################################
    original_start = datos_base['expedientes']['fecha_registro_exp'].min().date()
    original_end = datos_base['expedientes']['fecha_registro_exp'].max().date()
    min_date = max(original_start, FECHA_MINIMA.date())
    max_date = min(original_end, datetime.date.today())
    
    rango_fechas = st.slider(
        "Fecha inicio expediente",
        min_value=min_date,
        max_value=max_date,
        value=(min_date, max_date),
        format="DD-MM-YYYY"
    )
    st.session_state.rango_fechas = rango_fechas 
    
    # Multi-select for final states
    #################################
    df_final_states_1 = datos_base['estados'][datos_base['estados']['FINAL'] == 1]
    state_options = {
        row['DENOMINACION_SIMPLE']: row['NUMTRAM']
        for _, row in datos_base['estados'][['NUMTRAM', 'DENOMINACION_SIMPLE']].drop_duplicates().iterrows()
    }
    default_states = df_final_states_1['DENOMINACION_SIMPLE'].unique().tolist()
    estados_finales_selecc_ms = st.multiselect(
        "Seleccionar estados finales",
        options=list(state_options.keys()),
        default=default_states,
        help="Selecciona uno o varios estados finales. Si no seleccionas ninguno, se mostrarán todos los expedientes"
    )
    estados_finales_selecc = [state_options[denom] for denom in estados_finales_selecc_ms]

    # Update session state with new values
    ######################################
    st.session_state.datos_filtrados_rango = filtra_datos_fechas(
        datos_base['expedientes'],
        datos_base['tramites'],
        rango_fechas
    )
    st.session_state.estados_finales_selecc = estados_finales_selecc



# 5. Navigation / Page definitions
# NOTE: The st.Page and st.navigation APIs are not part of the official Streamlit API.
# If you are using a custom or experimental navigation solution, ensure you follow its guidelines.
datos_basicos = st.Page("datos_basicos.py", title="Datos básicos", icon="🏠")
flujo = st.Page("flujo.py", title="Flujos de tramitación", icon="⏳")
estados = st.Page("estados.py", title="Cuellos de botella", icon="🎯")
geografico = st.Page("geografico.py", title="Origen Geográfico", icon="🌍")

temporal_demanda = st.Page("temporal_demanda.py", title="Evolucion demanda", icon="✋")
temporal_tramitacion = st.Page("temporal_tramitacion.py", title="Evolución tramitación", icon="🗓️")
temporal_acumulado = st.Page("temporal_acumulado.py",  title="Carga de trabajo acumulada", icon="🛠️")

nav = st.navigation({
    "Análisis estático": [datos_basicos, flujo, estados, geografico],
    "Análisis dinámico": [temporal_demanda,temporal_tramitacion,  temporal_acumulado],
})
nav.run()
