# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 19:19:18 2025

@author: flipe
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime 
import numpy as np

##########################
# CARGA DE DATOS DE SESSION STATE
##########################
# Get filtered expedientes
expedientes = st.session_state.filtered_data['expedientes']
# Ensure datetime type
expedientes['fecha_registro_exp'] = pd.to_datetime(expedientes['fecha_registro_exp'])

##########################
# FUNCIONES CACHEADAS
##########################
@st.cache_data
def compute_agregado(_expedientes, freq, date_range, selected_procedure):
    """Compute aggregated data for Tab1"""
    freq_map = {'Diaria': 'D', 'Semanal': 'W-MON', 'Mensual': 'MS'}
    return _expedientes.set_index('fecha_registro_exp').resample(freq_map[freq]).agg(
        total_exp=('id_exp', 'count')
    ).reset_index()

@st.cache_data
def compute_provincia(_expedientes, freq, date_range, selected_procedure):
    """Compute province data for Tab2 and Tab4"""
    freq_map = {'Diaria': 'D', 'Semanal': 'W-MON', 'Mensual': 'MS'}
    df = _expedientes.groupby(
        [pd.Grouper(key='fecha_registro_exp', freq=freq_map[freq]), 'provincia']
    ).agg(total_exp=('id_exp', 'count')).reset_index()
    
    province_totals = df.groupby('provincia')['total_exp'].sum().sort_values(ascending=False)
    df['provincia'] = pd.Categorical(
        df['provincia'],
        categories=province_totals.index.tolist(),
        ordered=True
    )
    return df

@st.cache_data
def compute_heatmap_data(_expedientes, date_range, selected_procedure):
    """Compute heatmap data for Tab3"""
    df_week = _expedientes.set_index('fecha_registro_exp').resample('W-MON').agg(
        total_exp=('id_exp', 'count')
    )
    df_week['year'] = df_week.index.year
    df_week['week'] = df_week.index.isocalendar().week
    df_week['start_date'] = df_week.index.strftime('%Y-%m-%d')
    df_week['month'] = df_week.index.strftime('%B')
    
    heatmap_data = df_week.pivot(index='year', columns='week', values='total_exp')
    custom_data = np.dstack([
        df_week.pivot(index='year', columns='week', values='start_date').values,
        df_week.pivot(index='year', columns='week', values='month').values
    ])
    
    return df_week, heatmap_data, custom_data

##########################
# INTERFAZ DE USUARIO
##########################
tab1, tab2, tab3, tab4 = st.tabs([
    "Totales", 
    "Por provincia", 
    "Patrones anuales",
    "Tabla de datos"
])

plot_height = 650

selected_dates = st.session_state.get('selected_dates', (None, None))
selected_procedure = st.session_state.selected_procedure

with tab1:
    st.subheader("Evolución mensual de la recepción de solicitudes")
    st.markdown("Identica periodos con mayor o menor recepción de solicitudes")
    
    freq = 'Mensual'
    df_agregado = compute_agregado(expedientes, freq, selected_dates, selected_procedure)
    
    # Dynamic labels and ticks
    if freq == 'Diaria':
        df_agregado['label'] = df_agregado['fecha_registro_exp'].dt.strftime('%Y-%m-%d')
        tick_format = '%Y-%m-%d'
    elif freq == 'Semanal':
        df_agregado['label'] = df_agregado['fecha_registro_exp'].dt.strftime('Week %U, %Y')
        tick_format = 'Week %U, %Y'
    else:  # Mensual
        df_agregado['label'] = df_agregado['fecha_registro_exp'].dt.strftime('%b %Y')
        tick_format = '%b %Y'

    fig = px.bar(df_agregado,
                 x='fecha_registro_exp',
                 y='total_exp',
                 labels={'fecha_registro_exp': 'Fecha', 'total_exp': 'Solicitudes'})
    
    fig.update_xaxes(tickformat=tick_format)
    fig.update_layout(height=plot_height)
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Evolución mensual por provincia")
    st.markdown("Bar chart apilado mostrando la distribución de solicitudes por provincia a lo largo del tiempo")
    
    freq = 'Mensual'
    df_provincia = compute_provincia(expedientes, freq, selected_dates, selected_procedure)
    
    # Create dynamic labels for the x-axis
    tick_format = '%b %Y' if freq == 'Mensual' else '%Y-%m-%d'
    
    fig_prov = px.bar(
        df_provincia,
        x='fecha_registro_exp',
        y='total_exp',
        color='provincia',
        labels={'fecha_registro_exp': 'Fecha', 'total_exp': 'Solicitudes', 'provincia': 'Provincia'}
    )
    
    fig_prov.update_layout(
        barmode='stack',
        height=plot_height,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.2,
            xanchor="center",
            x=0.5
        )
    )
    fig_prov.update_xaxes(tickformat=tick_format)
    
    # Reorder traces
    ordered_provinces = df_provincia['provincia'].cat.categories.tolist()
    sorted_traces = sorted(fig_prov.data, key=lambda trace: ordered_provinces.index(trace.name))
    fig_prov.data = tuple(sorted_traces)
    
    st.plotly_chart(fig_prov, use_container_width=True)

with tab3:
    st.subheader("Mapa de calor con demanda semanal a lo largo del año")
    st.markdown("Permite visualizar posibles patrones que se repiten anualmente")

    df_week, heatmap_data, custom_data = compute_heatmap_data(expedientes, selected_dates, selected_procedure)
    
    fig_heatmap = go.Figure(data=go.Heatmap(
        x=heatmap_data.columns,
        y=heatmap_data.index,
        z=heatmap_data.values,
        customdata=custom_data,
        hovertemplate=(
            "Año: %{y}<br>"
            "Semana: %{x}<br>"
            "Inicio semana: %{customdata[0]}<br>"
            "Mes: %{customdata[1]}<br>"
            "Solicitudes: %{z}<extra></extra>"
        ),
        colorscale='Viridis'
    ))
    
    fig_heatmap.update_layout(
        xaxis_title="Semana del año",
        yaxis_title="Año",
        template="plotly_white",
        height=500
    )
    # Force y-axis ticks to show only integer years
    fig_heatmap.update_yaxes(
        tickmode='array',
        tickvals=heatmap_data.index,
        ticktext=[str(int(year)) for year in heatmap_data.index]
    )
    st.plotly_chart(fig_heatmap, use_container_width=True)

with tab4:
    st.subheader("Datos completos agrupados por mes y provincia")
    
    # Usamos los datos cacheados de tab2
    freq = 'Mensual'
    df_provincia = compute_provincia(expedientes, freq, selected_dates, selected_procedure)
    
    df_subset = df_provincia[['fecha_registro_exp', 'provincia', 'total_exp']].rename(columns={
        'fecha_registro_exp': 'Fecha inicio mes',
        'provincia': 'Provincia',
        'total_exp': 'Número Solicitudes'
    })    
    
    st.dataframe(
        df_subset,
        height=600,
        hide_index=True,
        column_config={"Fecha inicio mes": st.column_config.DatetimeColumn(format="DD/MM/YYYY")}
    )