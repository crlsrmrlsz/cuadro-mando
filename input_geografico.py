# input_geografico.py
import streamlit as st
import json
import plotly.graph_objects as go
from datetime import datetime
import geopandas as gpd

# Títulos y explicaciones
st.header("Análisis Geográfico de Procedimientos")
st.markdown("""
**Visualiza cómo se distribuyen los trámites en el territorio:**
- Compara provincias y municipios
- Identifica patrones de digitalización
""")

# ====================
# CACHED DATA LOADING
# ====================

@st.cache_data
def load_geo_data():
    """Carga los datos geográficos y calcula centroides"""
    with open('data/geo/provincias_id_ine.geojson', 'r', encoding='utf-8') as f:
        prov_geojson = json.load(f)
    
    with open('data/geo/municipios_id_ine_simple.geojson', 'r', encoding='utf-8') as f:
        mun_geojson = json.load(f)

    # Convertir a GeoDataFrames para calcular centroides
    prov_gdf = gpd.GeoDataFrame.from_features(prov_geojson['features']).set_index('codigo')
    mun_gdf = gpd.GeoDataFrame.from_features(mun_geojson['features']).set_index('CODIGOINE')

    # Calcular centroides
    prov_gdf['centroid'] = prov_gdf.geometry.centroid
    mun_gdf['centroid'] = mun_gdf.geometry.centroid

    return {
        'provincias': prov_geojson,
        'municipios': mun_geojson,
        'prov_centroids': prov_gdf[['centroid']],
        'mun_centroids': mun_gdf[['centroid']]
    }

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
       
    # Agregación por provincia (manteniendo el nombre)
    df_prov = df.groupby('codine_provincia', observed=True).agg(
        total=('id_exp', 'count'),
        online=('es_online', 'sum'),
        empresas=('es_empresa', 'sum'),
        provincia=('provincia', 'first')  # Add province name
    ).reset_index()
    
    # Agregación por municipio (manteniendo el nombre)
    df_mun = df.groupby(['codine_provincia', 'codine'], observed=True).agg(
        total=('id_exp', 'count'),
        online=('es_online', 'sum'),
        empresas=('es_empresa', 'sum'),
        municipio=('municipio', 'first'),  # Add municipality name
        provincia=('provincia', 'first')   # Add province name for context
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

metric_options = {
    "total": "Número total",
    "%_online": "% Trámites online",
    "%_empresas": "% Solicitudes empresas"
}

selected_metric = st.radio(
    "Selecciona la métrica a visualizar:",
    options=list(metric_options.keys()),
    format_func=lambda x: metric_options[x],
    horizontal=True,
    label_visibility="collapsed"
)

# Carga de datos
geo_data = load_geo_data()
df_prov, df_mun = aggregate_data(st.session_state.filtered_data['expedientes'])

# ====================
# VISUALIZACIÓN PROVINCIAS
# ====================

col_prov_map, col_prov_bar = st.columns([0.7, 0.3])

with col_prov_map:
    # Mapa de provincias
    fig_prov = go.Figure(go.Choroplethmapbox(
        geojson=geo_data['provincias'],
        locations=df_prov['codine_provincia'],
        z=df_prov[selected_metric],
        featureidkey="properties.id",
        colorscale="Blues",
        marker_opacity=0.7,
        hoverinfo="text",
        hovertext=df_prov.apply(lambda x: f"{x['provincia']}<br>{selected_metric}: {x[selected_metric]}", axis=1)
    ))
    
    # Añadir porcentajes como texto
    fig_prov.add_trace(go.Scattermapbox(
        lat=geo_data['prov_centroids'].centroid.y,
        lon=geo_data['prov_centroids'].centroid.x,
        mode='text',
        text=df_prov.set_index('codine_provincia')[selected_metric].round(1).astype(str) + '%',
        textfont=dict(size=10, color='black'),
        hoverinfo='none'
    ))
    
    fig_prov.update_layout(
        mapbox=dict(
            style="carto-positron",
            zoom=4.2,
            center={"lat": 40.4165, "lon": -3.70256}
        ),
        margin={"r":0,"t":0,"l":0,"b":0},
        height=500,
        showlegend=False
    )
    st.plotly_chart(fig_prov, use_container_width=True)

with col_prov_bar:
    # Gráfico de barras simplificado
    top_prov = df_prov.nlargest(10, selected_metric).sort_values(selected_metric, ascending=True)
    fig_bar_prov = go.Figure(go.Bar(
        x=top_prov[selected_metric],
        y=top_prov['provincia'],
        orientation='h',
        marker_color='#1f77b4',
        hovertemplate="%{y}<br>%{x}<extra></extra>"
    ))
    
    fig_bar_prov.update_layout(
        margin=dict(l=150, r=20, t=0, b=20),
        height=500,
        yaxis=dict(autorange="reversed"),
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False
    )
    st.plotly_chart(fig_bar_prov, use_container_width=True)

# ====================
# VISUALIZACIÓN MUNICIPIOS
# ====================

col_mun_map, col_mun_bar = st.columns([0.7, 0.3])

with col_mun_map:
    # Mapa de municipios
    fig_mun = go.Figure(go.Choroplethmapbox(
        geojson=geo_data['municipios'],
        locations=df_mun['codine'],
        z=df_mun[selected_metric],
        featureidkey="properties.CODIGOINE",
        colorscale="Blues",
        marker_opacity=0.7,
        hoverinfo="text",
        hovertext=df_mun.apply(lambda x: f"{x['municipio']}<br>{selected_metric}: {x[selected_metric]}", axis=1)
    ))
    
    fig_mun.update_layout(
        mapbox=dict(
            style="carto-positron",
            zoom=4.2,
            center={"lat": 40.4165, "lon": -3.70256}
        ),
        margin={"r":0,"t":0,"l":0,"b":0},
        height=500,
        showlegend=False
    )
    st.plotly_chart(fig_mun, use_container_width=True)

with col_mun_bar:
    # Gráfico de barras simplificado
    top_mun = df_mun.nlargest(10, selected_metric).sort_values(selected_metric, ascending=True)
    fig_bar_mun = go.Figure(go.Bar(
        x=top_mun[selected_metric],
        y=top_mun['municipio'],
        orientation='h',
        marker_color='#1f77b4',
        hovertemplate="%{y}<br>%{x}<extra></extra>"
    ))
    
    fig_bar_mun.update_layout(
        margin=dict(l=150, r=20, t=0, b=20),
        height=500,
        yaxis=dict(autorange="reversed"),
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False
    )
    st.plotly_chart(fig_bar_mun, use_container_width=True)

# Notas al pie
st.caption(f"""
*Los porcentajes se calculan sobre el total de trámites en cada área geográfica.
Datos actualizados al {datetime.today().strftime('%d/%m/%Y')}
""")