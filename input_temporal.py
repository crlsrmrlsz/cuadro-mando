# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 19:19:18 2025

@author: flipe
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

##########################
# CARGA DE DATOS DE SESSION STATE
##########################
# Get filtered expedientes
expedientes = st.session_state.filtered_data['expedientes']
# Ensure datetime type
expedientes['fecha_registro_exp'] = pd.to_datetime(expedientes['fecha_registro_exp'])

# --- TAB 1: Número de expedientes (usa columna "total" y "%_total") ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Totales", 
    "Por provincia", 
    "Patrones anuales",
    "Tabla de datos"
])

plot_height = 650

with tab1:
    st.subheader("Evolución mensual de la recepción de solicitudes")
    st.markdown("Identica periodos con mayor o menor recepción de solicitudes")
    
    # # Add time frequency selector
    # freq = st.radio("Frecuencia de agrupación", 
    #                     options=['Diaria', 'Semanal', 'Mensual'],
    #                     index=1,
    #                     horizontal = True)
    
    # # Map to pandas frequency codes
    freq_map = {
        'Diaria': 'D',
        'Semanal': 'W-MON',
        'Mensual': 'MS'
    }
    
    # Update resampling 
    freq = 'Mensual'
    df_agregado = expedientes.set_index('fecha_registro_exp').resample(freq_map[freq]).agg(
        total_exp=('id_exp', 'count')
    ).reset_index()
    
    
    # Dynamic labels and ticks
    if freq == 'Diaria':
        df_agregado['label'] = df_agregado['fecha_registro_exp'].dt.strftime('%Y-%m-%d')
        tick_format = '%Y-%m-%d'
    elif freq == 'Semanal':
        df_agregado['label'] = df_agregado['fecha_registro_exp'].dt.strftime('Week %U, %Y')
        tick_format = 'Week %U, %Y'
    elif freq == 'Mensual':
        df_agregado['label'] = df_agregado['fecha_registro_exp'].dt.strftime('%b %Y')
        tick_format = '%b %Y'
    
        
    
    # Create the plot
    fig = px.bar(df_agregado,
                 x='fecha_registro_exp',
                 y='total_exp',
                 labels={'fecha_registro_exp': 'Fecha', 'total_exp': 'Solicitudes'}
                 )

    # Adjust x-axis ticks
    fig.update_xaxes(
        tickformat=tick_format
    )
    # Set the bars to stack and adjust the gap between bars
    fig.update_layout(
        height=plot_height
    )
    st.plotly_chart(fig, use_container_width=True)

# ----------------------------
# Tab 2: Stacked Bar Chart by Province
# ----------------------------
with tab2:
    st.subheader("Evolución mensual por provincia")
    st.markdown("Bar chart apilado mostrando la distribución de solicitudes por provincia a lo largo del tiempo")
    
    freq = 'Mensual'
    
    # Group by month and province; count the number of expedientes per group
    df_provincia = expedientes.groupby(
        [pd.Grouper(key='fecha_registro_exp', freq=freq_map[freq]), 'provincia']
    ).agg(total_exp=('id_exp', 'count')).reset_index()
    
    # Create dynamic labels for the x-axis
    if freq == 'Mensual':
        df_provincia['label'] = df_provincia['fecha_registro_exp'].dt.strftime('%b %Y')
        tick_format = '%b %Y'
    
    # Compute overall totals for each province (over the entire period)
    province_totals = df_provincia.groupby('provincia')['total_exp'].sum().sort_values(ascending=False)
    ordered_provinces = province_totals.index.tolist()
    
    # Set 'provincia' as a categorical variable with the desired descending order
    df_provincia['provincia'] = pd.Categorical(
        df_provincia['provincia'],
        categories=ordered_provinces,
        ordered=True
    )
    
    # Create the stacked bar chart
    fig_prov = px.bar(
        df_provincia,
        x='fecha_registro_exp',
        y='total_exp',
        color='provincia',
        labels={
            'fecha_registro_exp': 'Fecha',
            'total_exp': 'Solicitudes',
            'provincia': 'Provincia'
        }
    )
    
    # Set the bars to stack and adjust the gap between bars
    fig_prov.update_layout(
        barmode='stack',
        height=plot_height,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.2,  # Adjust vertical position as needed
            xanchor="center",
            x=0.5
        )
    )
    fig_prov.update_xaxes(tickformat=tick_format)
    
    # Reorder the traces so that both the stack order and legend follow descending totals.
    # Each trace's name corresponds to a province.
    sorted_traces = sorted(fig_prov.data, key=lambda trace: ordered_provinces.index(trace.name))
    # In Plotly, the first trace in the list is drawn at the bottom of the stack.
    fig_prov.data = tuple(sorted_traces)
    
    st.plotly_chart(fig_prov, use_container_width=True)
    
    
# ----------------------------
# Tab 3: heatmap
# ----------------------------
with tab3:
    st.subheader("Mapa de calor con demanda semanal a lo largo de año")
    st.markdown("permite visualizar posibles patrones que se repiten anualmente")
 
    # Aggregate data by week (using Monday as the start of the week)
    df_week = expedientes.set_index('fecha_registro_exp').resample('W-MON').agg(total_exp=('id_exp', 'count'))
    
    # Extract year and week number from the index
    df_week['year'] = df_week.index.year.astype(int)
    df_week['week'] = df_week.index.isocalendar().week.astype(int)
    
    # Pivot the DataFrame to create a matrix: rows = year, columns = week number
    heatmap_data = df_week.pivot(index='year', columns='week', values='total_exp')
    
    # Create the heatmap
    fig_heatmap = go.Figure(data=go.Heatmap(
        x=heatmap_data.columns,  # Week numbers
        y=heatmap_data.index,    # Years
        z=heatmap_data.values,
        colorscale='Viridis'
    ))
    

    # Customize layout
    fig_heatmap.update_layout(
        xaxis_title="Semana del año",
        yaxis_title="Año",
        template="plotly_white",
        height=500
    )
    
    st.plotly_chart(fig_heatmap, use_container_width=True)
