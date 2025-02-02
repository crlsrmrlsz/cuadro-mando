# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 19:19:21 2025

@author: flipe
"""

# input_geografico.py
import streamlit as st
import json
import plotly.express as px
import geopandas as gpd
from datetime import datetime


# Títulos y explicaciones
st.header("Análisis Geográfico de Procedimientos")
st.markdown("""
**Visualiza cómo se distribuyen los trámites en el territorio:**
- Compara comunidades autónomas y municipios
- Identifica patrones de digitalización
- Detecta zonas con mayor actividad empresarial
""")

# ====================
# CACHED DATA LOADING
# ====================

@st.cache_data
def load_geo_data():
    """Carga los datos geográficos conservando los IDs correctos"""
    # Cargar GeoJSON crudo para inspeccionar propiedades
    with open('data/geo/provincias_id_ine.geojson', 'r') as f:
        prov_geojson = json.load(f)
    
    with open('data/geo/municipios_id_ine_simple.geojson', 'r') as f:
        mun_geojson = json.load(f)

    # Convertir a GeoDataFrames manteniendo propiedades
    provincias = gpd.GeoDataFrame.from_features(
        prov_geojson['features'],
        crs="EPSG:4326"
    ).set_index('id')  # Usar tu columna ID real
    
    municipios = gpd.GeoDataFrame.from_features(
        mun_geojson['features'],
        crs="EPSG:4326"
    ).set_index('id')  # Usar tu columna ID real

    return {'provincias': provincias, 'municipios': municipios}


@st.cache_data
def aggregate_data(df):
    """Preprocesa y agrega los datos para visualización"""
    # Filtrado de columnas
    df = df[[
        'id_exp', 'codine_provincia', 'codine', 
        'es_telematica', 'nif', 'dni',
        'provincia', 'municipio'
    ]].copy()
    
    # Limpieza de datos
    df['es_online'] = df['es_telematica'].fillna(False)
    df['es_empresa'] = df['nif'].notnull()
       
    # Agregación por provincia
    df_prov = df.groupby('codine_provincia', observed=True).agg(
        total=('id_exp', 'count'),
        online=('es_online', 'sum'),
        empresas=('es_empresa', 'sum')
    ).reset_index()
    
    # Agregación por municipio
    df_mun = df.groupby(['codine_provincia', 'codine'], observed=True).agg(
        total=('id_exp', 'count'),
        online=('es_online', 'sum'),
        empresas=('es_empresa', 'sum')
    ).reset_index()

    # Cálculo de porcentajes
    for df in [df_prov, df_mun]:
        df['%_online'] = (df['online'] / df['total'] * 100).round(1)
        df['%_empresas'] = (df['empresas'] / df['total'] * 100).round(1)
        df['total'] = df['total'].astype('int32')
    
    return df_prov, df_mun

# ====================
# INTERFAZ PRINCIPAL
# ====================

# Selector de métrica
metric_options = {
    "total": ("Número total", "total", px.colors.sequential.Viridis),
    "online": ("% Trámites online", "%_online", px.colors.sequential.Blues),
    "empresas": ("% Solicitudes empresas", "%_empresas", px.colors.sequential.Oranges)
}

selected_metric = st.radio(
    "Selecciona la métrica a visualizar:",
    options=list(metric_options.keys()),
    format_func=lambda x: metric_options[x][0],
    horizontal=True,
    label_visibility="collapsed"
)

# Carga de datos
geo_data = load_geo_data()
df_prov, df_mun = aggregate_data(st.session_state.filtered_data['expedientes'])

# Configuración común
mapbox_style = "carto-positron"
metric_label, metric_col, color_scale = metric_options[selected_metric]

# ====================
# VISUALIZACIÓN PROVINCIAS
# ====================

col_prov_map, col_prov_bar = st.columns([0.7, 0.3])

with col_prov_map:
    fig_prov = px.choropleth_mapbox(
        df_prov,
        geojson=geo_data['provincias'],
        locations='codine_provincia',
        featureidkey="properties.id",
        color=metric_col,
        color_continuous_scale=color_scale,
        mapbox_style=mapbox_style,
        center={"lat": 40.4165, "lon": -3.70256},
        zoom=4.5,
        height=500,
        title=f"Por Provincias - {metric_label}",
        labels={metric_col: metric_label}
    )
    fig_prov.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
    st.plotly_chart(fig_prov, use_container_width=True)

with col_prov_bar:
    # Top 10 provincias
    top_prov = df_prov.nlargest(10, metric_col)
    fig_bar_prov = px.bar(
        top_prov,
        x=metric_col,
        y='codine_provincia',
        orientation='h',
        title=f"Top 10 Provincias - {metric_label}",
        color=metric_col,
        color_continuous_scale=color_scale,
        labels={metric_col: metric_label}
    )
    fig_bar_prov.update_layout(showlegend=False, yaxis_title=None)
    st.plotly_chart(fig_bar_prov, use_container_width=True)

# ====================
# VISUALIZACIÓN MUNICIPIOS
# ====================

col_mun_map, col_mun_bar = st.columns([0.7, 0.3])

with col_mun_map:
    fig_mun = px.choropleth_mapbox(
        df_mun,
        geojson=geo_data['municipios'],
        locations='codine',
        featureidkey="properties.id",
        color=metric_col,
        color_continuous_scale=color_scale,
        mapbox_style=mapbox_style,
        center={"lat": 40.4165, "lon": -3.70256},
        zoom=4.5,
        height=500,
        title=f"Por Municipios - {metric_label}",
        labels={metric_col: metric_label}
    )
    fig_mun.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
    st.plotly_chart(fig_mun, use_container_width=True)

with col_mun_bar:
    # Top 10 municipios
    top_mun = df_mun.nlargest(10, metric_col)
    fig_bar_mun = px.bar(
        top_mun,
        x=metric_col,
        y='codine',
        orientation='h',
        title=f"Top 10 Municipios - {metric_label}",
        color=metric_col,
        color_continuous_scale=color_scale,
        labels={metric_col: metric_label}
    )
    fig_bar_mun.update_layout(showlegend=False, yaxis_title=None)
    st.plotly_chart(fig_bar_mun, use_container_width=True)

# Notas al pie
st.caption("""
*Los porcentajes se calculan sobre el total de trámites en cada área geográfica.
Datos actualizados al """ + datetime.today().strftime('%d/%m/%Y'))

