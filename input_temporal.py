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

# Add time frequency selector
freq = st.radio("Frecuencia de agrupación", 
                    options=['Diaria', 'Semanal', 'Mensual'],
                    index=1,
                    horizontal = True)

# Map to pandas frequency codes
freq_map = {
    'Diaria': 'D',
    'Semanal': 'W-MON',
    'Mensual': 'MS'
}


# Update resampling in df_weekly
df_agregado = expedientes.set_index('fecha_registro_exp').resample(freq_map[freq]).agg(
    total_exp=('id_exp', 'count')
).reset_index()


# Create the plot
fig = px.bar(df_agregado,
             x='fecha_registro_exp',
             y='total_exp')

# # Customize layout
# fig.update_layout(
#     xaxis=dict(
#         title= "Fecha",
#         tickmode="linear",  # Ensures evenly spaced ticks
#         dtick="M2",  # One tick per month (use "M3" for every 3 months, etc.)
#         tickformat="%b %Y"  # Format as "Jan 2024"
#     ),
#     yaxis_title="Número de Solicitudes",
#     template="plotly_white",
#     hovermode="x unified"
# )

# fig.update_traces(hovertemplate="%{y}<extra></extra>")


# Display plot
st.plotly_chart(fig, use_container_width=True)
