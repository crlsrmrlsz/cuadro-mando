# -*- coding: utf-8 -*-
"""
Created on Fri Feb 14 19:49:30 2025

@author: flipe
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# Get parameters from session state
rango_fechas = st.session_state.get('rango_fechas', (None, None))
proced_seleccionado = st.session_state.get('proced_seleccionado', None)
nombres_estados = st.session_state.estados.set_index('NUMTRAM')['DENOMINACION_SIMPLE'].to_dict()


# Cache function to load accumulated data
@st.cache_data(show_spinner="Cargando datos acumulados")
def carga_datos_acumulados(_codigo_procedimiento, rango_fechas):
    base_path = f"data/tratados/{_codigo_procedimiento}"
    _datos_acumulados = pd.read_parquet(
        f"{base_path}/tramites_acumulado.parquet"
    )
    return _datos_acumulados


df_acumulados = carga_datos_acumulados(proced_seleccionado, rango_fechas)

st.subheader("Acumulación de expedientes en cada estado a lo largo del tiempo")
st.info("Permite visualizar atascos, expedientes que se acumulan en cierto estado. La gráfica se presenta inicialmente con el estado inicial marcado, selecciona los estados que te interese visualizar.", icon="💡")
st.dataframe(df_acumulados)
