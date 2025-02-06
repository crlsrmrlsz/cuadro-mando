# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 19:19:18 2025

@author: flipe
"""

import streamlit as st
import pandas as pd
import plotly.express as px

st.subheader("Recepción de solicitudes en el rango de fechas")



# Get filtered expedientes
expedientes = st.session_state.filtered_data['expedientes']

# Ensure datetime type
expedientes['fecha_registro_exp'] = pd.to_datetime(expedientes['fecha_registro_exp'])

# Create weekly aggregation
df_weekly = expedientes.set_index('fecha_registro_exp').resample('W-MON').agg(
    total_exp=('id_exp', 'count')
).reset_index()

# Create the plot
fig = px.bar(df_weekly,
             x='fecha_registro_exp',
             y='total_exp',
             title='Expedientes Registrados por Semana')

# Customize layout
fig.update_layout(
    xaxis_title="Fecha",
    yaxis_title="Número de Expedientes",
    template="plotly_white",
    hovermode="x unified"
)

# Display plot
st.plotly_chart(fig, use_container_width=True)


