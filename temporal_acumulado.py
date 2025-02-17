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
    _datos_acumulados["fecha_tramite"] = pd.to_datetime(_datos_acumulados["fecha_tramite"]).dt.date
    # Filtra los datos según el rango de fechas
    start_date, end_date = rango_fechas
    df_filtrado = _datos_acumulados[
        (_datos_acumulados["fecha_tramite"] >= start_date) & (_datos_acumulados["fecha_tramite"] <= end_date)
    ]
    return df_filtrado


df_acumulados = carga_datos_acumulados(proced_seleccionado, rango_fechas)

st.subheader("Acumulación de expedientes en cada estado a lo largo del tiempo")
st.info("Permite visualizar acumulaciones de carga de trabajo, expedientes que se acumulan en determinados trámites. La gráfica se presenta inicialmente con el primer estado marcado, selecciona los estados que te interese visualizar.", icon="💡")

nombres_estados_str = {str(k): v for k, v in nombres_estados.items()}
state_cols = [col for col in df_acumulados.columns if col in nombres_estados_str]

# ---------------------------
# Plot 1: Datos agregados (todas las unidades)
# ---------------------------

# Agrupa los datos por fecha, sumando los procesos por cada estado
df_agg = df_acumulados.groupby("fecha_tramite")[state_cols].sum().reset_index()

# Crea la figura con Plotly
fig = go.Figure()

for state in state_cols:
    #state_name = nombres_estados.get(state, str(state))
    state_name = nombres_estados_str.get(state, str(state))
    # Por defecto, solo se mostrará el estado "0". El resto se ocultarán en la leyenda.
    visible_status = True if str(state) == "0" else "legendonly"
    
    fig.add_trace(go.Scatter(
        x=df_agg["fecha_tramite"],
        y=df_agg[state],
        mode="lines",
        name=state_name,
        #stackgroup='one',  # Esto crea un gráfico de área apilada.
        fill='tozeroy', 
        visible=visible_status,
        hovertemplate=f"<b>{state_name}:</b>%{{y}}<extra></extra>"
    ))

fig.update_layout(
    height= 600,
    xaxis_title="Fecha",
    yaxis_title="Número de procesos",
    hovermode="x unified",
    legend=dict(
         orientation="h",  # Orientación horizontal
         yanchor="top",
         y=-0.15,           # Posiciona la leyenda por debajo del gráfico
         xanchor="center",
         x=0.5,
         traceorder="normal"
    )

)

st.plotly_chart(fig, use_container_width=True)

# ---------------------------
# Plot 2: Filtrado por unidad tramitadora (si hay más de una)
# ---------------------------
unidades = sorted(df_acumulados["unidad_tramitadora"].unique())
if len(unidades) > 1:
    st.markdown("")
    st.subheader("GRáfica de estados acumulados para una Unidad específica")
    st.info("Compara la carga de trabajo acumulada de una Unidad en particular, posibles diferencias en tiempos o cantidad de expedientes acumulados en determinados estados", icon = "👬")
    unidad_seleccionada = st.selectbox("Selecciona la unidad tramitadora", unidades)
    df_unidad = df_acumulados[df_acumulados["unidad_tramitadora"] == unidad_seleccionada]
    df_agg_unidad = df_unidad.groupby("fecha_tramite")[state_cols].sum().reset_index()
    
    fig2 = go.Figure()
    for state in state_cols:
        visible_status = True if str(state) == "0" else "legendonly"
        state_name = nombres_estados_str.get(state, str(state))
        fig2.add_trace(go.Scatter(
            x=df_agg_unidad["fecha_tramite"],
            y=df_agg_unidad[state],
            mode="lines",
            name=state_name,
            #stackgroup='one',  # Esto crea un gráfico de área apilada.
            fill='tozeroy', 
            visible=visible_status,
            hovertemplate=f"<b>{state_name}:</b>%{{y}}<extra></extra>"
        ))
    
    fig2.update_layout(
        height= 600,
        xaxis_title="Fecha",
        yaxis_title="Número de procesos",
        hovermode="x unified",
        legend=dict(
             orientation="h",  # Orientación horizontal
             yanchor="top",
             y=-0.15,           # Posiciona la leyenda por debajo del gráfico
             xanchor="center",
             x=0.5,
             traceorder="normal"
        )
    )
    
    st.plotly_chart(fig2, use_container_width=True)


st.markdown("")
st.markdown("")
st.markdown("")
col1, col2, col3 = st.columns(3)
with col2: 
    if st.button("Pincha si te has enterado"):
        st.balloons()
