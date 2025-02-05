# input_geografico.py
import streamlit as st
import json
import plotly.graph_objects as go
from datetime import datetime

# ====================
# CACHED DATA LOADING
# ====================

@st.cache_data
def load_geo_data():
    """Carga los datos geográficos"""
    with open('data/geo/provincias_id_ine.geojson', 'r', encoding='utf-8') as f:
        prov_geojson = json.load(f)  # properties.codigo
    
    with open('data/geo/municipios_id_ine_simple.geojson', 'r', encoding='utf-8') as f:
        mun_geojson = json.load(f)

    return {
        'provincias': prov_geojson,
        'municipios': mun_geojson
    }

@st.cache_data
def aggregate_data(df):
    """Preprocesa y agrega los datos para visualización"""
    # Filtrado de columnas
    df = df[[ 'id_exp', 'codine_provincia', 'codine', 
              'es_telematica', 'nif', 'dni',
              'provincia', 'municipio' ]].copy()
    
    # Limpieza de datos
    df['es_online'] = df['es_telematica'].fillna(False)
    df['es_empresa'] = df['nif'].notnull()
       
    # Agregación por provincia (manteniendo el nombre)
    df_prov = df.groupby('codine_provincia', observed=True).agg(
        provincia=('provincia', 'first'),
        total=('id_exp', 'count'),
        online=('es_online', 'sum'),
        empresas=('es_empresa', 'sum')
    ).reset_index()
    
    # Agregación por municipio (manteniendo el nombre)
    df_mun = df.groupby(['codine_provincia', 'codine'], observed=True).agg(
        municipio=('municipio', 'first'),
        provincia=('provincia', 'first'),
        total=('id_exp', 'count'),
        online=('es_online', 'sum'),
        empresas=('es_empresa', 'sum')
    ).reset_index()

    # Cálculo de otros porcentajes (relativos a cada área)
    for df_agg in [df_prov, df_mun]:
        total_nacional = df_agg['total'].sum()
        df_agg['%_total'] = (df_agg['total'] / total_nacional * 100).round(1)
        df_agg['%_online'] = (df_agg['online'] / df_agg['total'] * 100).round(1)
        df_agg['%_empresas'] = (df_agg['empresas'] / df_agg['total'] * 100).round(1)
        df_agg['total'] = df_agg['total'].astype('int32')
    
    return df_prov, df_mun

# ====================
# GLOBAL SETTINGS
# ====================

heigh_tab1 = 500
opacity_data_map = 0.9
colors_map_prov = "Plasma_r"
colors_map_mun = "Blues"
top_m_bar = 60
left_m_bar = 10
right_m_bar = 20
bottom_m_bar = 20
bar_width = 0.9
num_bars = 20
# ====================
# VISUALIZATION FUNCTIONS
# ====================

def create_province_barchart(df_prov, value_col, pct_col):
    """Crea gráfico de barras horizontal de provincias"""
    # Ordenar y limitar a las 15 provincias con más valor
    df = df_prov.sort_values(value_col, ascending=False).nlargest(num_bars, pct_col).copy()  
    
    COLOR_PRIMARY = 'rgba(255, 127, 14, 0.7)'
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=df['provincia'],  # categorías
        x=df[pct_col],    # valor según columna
        marker_color=COLOR_PRIMARY,
        customdata=df[value_col],
        hovertemplate="%{customdata}<extra></extra>",
        text=df[pct_col].astype(str) + '%',
        textposition='outside',
        textfont=dict(size=10),
        width=bar_width,
        orientation='h'
    ))
    
    fig.update_layout(
        height=heigh_tab1,
        margin=dict(t=top_m_bar, b=bottom_m_bar, l=left_m_bar, r=right_m_bar),
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        ),
        yaxis=dict(
            title=None,
            tickfont=dict(size=11),
            autorange='reversed'
        ),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            side="top",
            range=[0, df[pct_col].max() * 1.15]
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False
    )
    
    return fig, df

def create_province_map(df_prov, geojson, value_col, pct_col):
    """Crea mapa coroplético de provincias"""
    df = df_prov.copy()
    df['codine_provincia'] = df['codine_provincia'].astype(str)
       
    fig = go.Figure(go.Choroplethmapbox(
        geojson=geojson,
        locations=df['codine_provincia'],
        z=df[pct_col],
        featureidkey="properties.codigo",
        colorscale=colors_map_prov,
        hovertemplate = "%{customdata[0]}<br>" + "%{customdata[2]:.2f}%<br>" + "num: %{customdata[1]}" + \
                        (" de %{customdata[3]}" if value_col in ['online', 'empresas'] else "") + \
                        "<extra></extra>",
        customdata=df[['provincia', value_col, pct_col, 'total']].values,
        marker_opacity=opacity_data_map
    ))
    
    fig.update_layout(
        height=heigh_tab1,
        margin=dict(t=60, b=0, l=0, r=0),
        mapbox=dict(
            style="open-street-map",
            zoom=5,
            center={"lat": 40.0, "lon": -3.5}
        )
    )
    
    return fig

def create_municipios_barchart(df_mun, value_col, pct_col):
    """Crea gráfico de barras horizontal de municipios"""
    df = df_mun.sort_values(value_col, ascending=False).nlargest(num_bars, pct_col).copy()  
    
    COLOR_PRIMARY = 'rgba(31, 119, 180, 0.7)'
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=df['municipio'],
        x=df[pct_col],
        marker_color=COLOR_PRIMARY,
        customdata=df[value_col],
        hovertemplate="%{customdata}<extra></extra>",
        text=df[pct_col].astype(str) + '%',
        textposition='outside',
        textfont=dict(size=10),
        width=bar_width,
        orientation='h'
    ))
    
    fig.update_layout(
        height=heigh_tab1,
        margin=dict(t=top_m_bar, b=bottom_m_bar, l=left_m_bar, r=right_m_bar),
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        ),
        yaxis=dict(
            title=None,
            tickfont=dict(size=11),
            autorange='reversed'
        ),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            side="top",
            range=[0, df[pct_col].max() * 1.15]
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False
    )
    
    return fig, df

def create_municipio_map(df_mun, geojson, value_col, pct_col):
    """Crea mapa coroplético de municipios"""
    df = df_mun.copy()
    df['codine'] = df['codine'].astype(str)
       
    fig = go.Figure(go.Choroplethmapbox(
        geojson=geojson,
        locations=df['codine'],
        z=df[pct_col],
        featureidkey="properties.CODIGOINE",
        colorscale=colors_map_mun,
        hovertemplate = "%{customdata[0]}<br>" + "%{customdata[2]:.2f}%<br>" + "num: %{customdata[1]}" + \
                        (" de %{customdata[3]}" if value_col in ['online', 'empresas'] else "") + \
                        "<extra></extra>",
        customdata=df[['municipio', value_col, pct_col]].values,
        marker_opacity=opacity_data_map
    ))
    
    fig.update_layout(
        height=heigh_tab1,
        margin=dict(t=60, b=0, l=0, r=0),
        mapbox=dict(
            style="open-street-map",
            zoom=6,
            center={"lat": 40.0, "lon": -3.5}
        )
    )
    
    return fig

# ====================
# PAGE STRUCTURE
# ====================

# Carga de datos
geo_data = load_geo_data()
df_prov, df_mun = aggregate_data(st.session_state.filtered_data['expedientes'])

# --- TAB 1: Número de expedientes (usa columna "total" y "%_total") ---
tab1, tab2, tab3 = st.tabs([
    "Número de expedientes", 
    "Digitalización", 
    "Persona física/Persona jurídica"
])

with tab1:
    st.subheader("Número de expedientes por Provincia (datos de solicitud)")
    st.markdown("Distribución geográfica de la demanda")
    
    col_tab1_prov_1, col_tab1_prov_2 = st.columns([0.7, 0.3])
    with col_tab1_prov_1:
        map_fig_prov = create_province_map(df_prov, geo_data['provincias'], value_col='total', pct_col='%_total')
        st.plotly_chart(map_fig_prov, use_container_width=True)
    with col_tab1_prov_2:
        chart, chart_df = create_province_barchart(df_prov, value_col='total', pct_col='%_total')
        st.plotly_chart(chart, use_container_width=True)
    
    st.divider()
    
    st.subheader("Número de expedientes por Municipio")
    col_tab1_mun_1, col_tab1_mun_2 = st.columns([0.7, 0.3])
    with col_tab1_mun_1:
        map_fig_mun = create_municipio_map(df_mun, geo_data['municipios'], value_col='total', pct_col='%_total')
        st.plotly_chart(map_fig_mun, use_container_width=True)
    with col_tab1_mun_2:
        chart_mun, chart_df_mun = create_municipios_barchart(df_mun, value_col='total', pct_col='%_total')
        st.plotly_chart(chart_mun, use_container_width=True)

    st.caption(f"*Los porcentajes se calculan sobre el total de trámites en cada área geográfica. Datos actualizados al {datetime.today().strftime('%d/%m/%Y')}*")

# --- TAB 2: Digitalización (usa columna "online" y "%_online") ---
with tab2:
    st.subheader("Porcentaje de expedientes solicitados de manera telemática")
    st.markdown("Identifica las áreas que más utilizan la administración electrónica")
    
    col_tab2_prov_1, col_tab2_prov_2 = st.columns([0.7, 0.3])
    with col_tab2_prov_1:
        map_fig_prov = create_province_map(df_prov, geo_data['provincias'], value_col='online', pct_col='%_online')
        st.plotly_chart(map_fig_prov, use_container_width=True)
    with col_tab2_prov_2:
        chart, chart_df = create_province_barchart(df_prov, value_col='online', pct_col='%_online')
        st.plotly_chart(chart, use_container_width=True)
    
    st.divider()
    
    st.subheader("Expedientes telemáticos por Municipio")
    col_tab2_mun_1, col_tab2_mun_2 = st.columns([0.7, 0.3])
    with col_tab2_mun_1:
        map_fig_mun = create_municipio_map(df_mun, geo_data['municipios'], value_col='online', pct_col='%_online')
        st.plotly_chart(map_fig_mun, use_container_width=True)
    with col_tab2_mun_2:
        chart_mun, chart_df_mun = create_municipios_barchart(df_mun, value_col='online', pct_col='%_online')
        st.plotly_chart(chart_mun, use_container_width=True)
    
    st.caption(f"*Los porcentajes se calculan sobre el total de trámites en cada área geográfica. Datos actualizados al {datetime.today().strftime('%d/%m/%Y')}*")

# --- TAB 3: Persona física/Persona jurídica (usa columna "empresas" y "%_empresas") ---
with tab3:
    st.subheader("Expedientes de persona jurídica")
    st.markdown("Identifica las áreas con mayor participación de empresas en las solicitudes")
    
    col_tab3_prov_1, col_tab3_prov_2 = st.columns([0.7, 0.3])
    with col_tab3_prov_1:
        map_fig_prov = create_province_map(df_prov, geo_data['provincias'], value_col='empresas', pct_col='%_empresas')
        st.plotly_chart(map_fig_prov, use_container_width=True)
    with col_tab3_prov_2:
        chart, chart_df = create_province_barchart(df_prov, value_col='empresas', pct_col='%_empresas')
        st.plotly_chart(chart, use_container_width=True)
    
    st.divider()
    
    st.subheader("Expedientes de persona jurídica por Municipio")
    col_tab3_mun_1, col_tab3_mun_2 = st.columns([0.7, 0.3])
    with col_tab3_mun_1:
        map_fig_mun = create_municipio_map(df_mun, geo_data['municipios'], value_col='empresas', pct_col='%_empresas')
        st.plotly_chart(map_fig_mun, use_container_width=True)
    with col_tab3_mun_2:
        chart_mun, chart_df_mun = create_municipios_barchart(df_mun, value_col='empresas', pct_col='%_empresas')
        st.plotly_chart(chart_mun, use_container_width=True)
    
    st.caption(f"*Los porcentajes se calculan sobre el total de trámites en cada área geográfica. Datos actualizados al {datetime.today().strftime('%d/%m/%Y')}*")
