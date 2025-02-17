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
expedientes = st.session_state.datos_filtrados_rango['expedientes']
# Ensure datetime type
expedientes['fecha_registro_exp'] = pd.to_datetime(expedientes['fecha_registro_exp'])

##########################
# FUNCIONES CACHEADAS
##########################
@st.cache_data
def compute_agregado(_expedientes, freq, rango_fechas, proced_seleccionado):
    """Compute aggregated data for Tab1"""
    freq_map = {'Diaria': 'D', 'Semanal': 'W-MON', 'Mensual': 'MS'}
    return _expedientes.set_index('fecha_registro_exp').resample(freq_map[freq]).agg(
        total_exp=('id_exp', 'count')
    ).reset_index()

@st.cache_data
def compute_provincia(_expedientes, freq, rango_fechas, proced_seleccionado):
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
def compute_heatmap_data(_expedientes, rango_fechas, proced_seleccionado):
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


rango_fechas = st.session_state.get('rango_fechas', (None, None))
proced_seleccionado = st.session_state.proced_seleccionado
# Determine frequency based on the date range
start_date, end_date = rango_fechas
if start_date is not None and end_date is not None:
    delta_days = (end_date - start_date).days
    if delta_days < 90:
        freq = 'Diaria'
    elif delta_days < 180:
        freq = 'Semanal'
    else:
        freq = 'Mensual'
else:
    freq = 'Mensual'
        
        
with tab1:
    st.subheader("Evolución mensual de la recepción de solicitudes")
    st.info("Identifica patrones de mayor entrada de solicitudes y posibles relaciones con eventos relacionados con el procedimiento",  icon="🕵️‍♂️")


    df_agregado = compute_agregado(expedientes, freq, rango_fechas, proced_seleccionado)
    
    # Checkbox to include rolling mean
    include_rolling_mean = st.checkbox("Ver media móvil")
    
    # Dynamic labels and ticks
    if freq == 'Diaria':
        df_agregado['label'] = df_agregado['fecha_registro_exp'].dt.strftime('%Y-%m-%d')
        tick_format = '%Y-%m-%d'
    elif freq == 'Semanal':
        df_agregado['label'] = df_agregado['fecha_registro_exp'].dt.strftime('Semana %U, %Y')
        tick_format = 'Semana %U, %Y'
    else:  # Mensual
        df_agregado['label'] = df_agregado['fecha_registro_exp'].dt.strftime('%b %Y')
        tick_format = '%b %Y'

    fig = px.bar(df_agregado,
                 x='fecha_registro_exp',
                 y='total_exp',
                 labels={'fecha_registro_exp': 'Fecha', 'total_exp': 'Solicitudes'})
    
    fig.update_xaxes(tickformat=tick_format)
    
    
    # Optionally add a rolling mean line
    if include_rolling_mean:
        # Determine an appropriate window size for the rolling mean
        # n_months = len(df_agregado)
        # if n_months < 24:
        #     window_size = 3
        # elif n_months < 48:
        #     window_size = 6
        # else:
        #     window_size = 12
        window_size = 6
        # Compute the rolling mean with a minimum period of 1 so early values are computed
        #df_agregado['rolling_mean'] = df_agregado['total_exp'].rolling(window=window_size, min_periods=1).mean()
        df_agregado['centered_mean'] = df_agregado['total_exp'].rolling(window=window_size, min_periods=1, center=True).mean()
        #df_agregado['centered_mean'] = df_agregado['total_exp'].rolling(window=window_size, min_periods=1, center=True).median()

        # Add the rolling mean as a red line trace over the bar chart
        fig.add_trace(
            go.Scatter(
                x=df_agregado['fecha_registro_exp'],
                y=df_agregado['centered_mean'],
                mode='lines',
                line=dict(color='red', width=2),
                showlegend=False
                # name=f'Media móvil ({window_size} meses)'
            )
        )
    
    
    # Compute the max stacked value across all dates and set y-axis range accordingly
    max_total_1 = df_agregado['total_exp'].max()
    fig.update_yaxes(range=[0, max_total_1])
    
    #fig.update_layout(height=plot_height)
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Evolución mensual por provincia")
    st.info("Visualiza los patrones de presentación de solictudes distinguiendo por provincia. Haz doble click en una provincia para aislar esos datos",  icon="🕵️‍♂️")

    df_provincia = compute_provincia(expedientes, freq, rango_fechas, proced_seleccionado)
    
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
    
    # Set default visibility so that only specific provinces are marked (visible)
    default_provinces = ['Toledo', 'Cuenca', 'Ciudad Real', 'Albacete', 'Guadalajara']
    for trace in fig_prov.data:
        if trace.name not in default_provinces:
            trace.visible = 'legendonly'
    # Compute the max stacked value across all dates and set y-axis range accordingly
    max_total = df_provincia.groupby('fecha_registro_exp')['total_exp'].sum().max()
    fig_prov.update_yaxes(range=[0, max_total])
    
    st.plotly_chart(fig_prov, use_container_width=True)

    # fig_area = px.area(
    #     df_provincia,
    #     x='fecha_registro_exp',
    #     y='total_exp',
    #     color='provincia',
    #     labels={'fecha_registro_exp': 'Fecha', 'total_exp': 'Solicitudes', 'provincia': 'Provincia'}
    # )
    # fig_area.update_xaxes(tickformat=tick_format)
    # fig_area.update_layout(height=plot_height)
    # st.plotly_chart(fig_area, use_container_width=True)

with tab3:
    st.subheader("Mapa de calor con demanda semanal a lo largo del año")
    st.info("El mapa de calor permite visualizar posibles semanas o periodos anuales en que se presentan más solicitudes",  icon="🕵️‍♂️")


    df_week, heatmap_data, custom_data = compute_heatmap_data(expedientes, rango_fechas, proced_seleccionado)
    
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
    df_provincia = compute_provincia(expedientes, freq, rango_fechas, proced_seleccionado)
    
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