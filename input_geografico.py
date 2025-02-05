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
        prov_geojson = json.load(f) # properties.codigo
    
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
        provincia=('provincia', 'first'),
        total=('id_exp', 'count'),
        online=('es_online', 'sum'),
        empresas=('es_empresa', 'sum')
  # Add province name
    ).reset_index()
    
    # Add percentage calculation here
    total_nacional_prov = df_prov['total'].sum()
    df_prov['pct_total'] = (df_prov['total'] / total_nacional_prov * 100).round(1)

    # Agregación por municipio (manteniendo el nombre)
    df_mun = df.groupby(['codine_provincia', 'codine'], observed=True).agg(
        municipio=('municipio', 'first'),  # Add municipality name
        provincia=('provincia', 'first'),   # Add province name for context
        total=('id_exp', 'count'),
        online=('es_online', 'sum'),
        empresas=('es_empresa', 'sum'),

    ).reset_index()

    # Add percentage calculation here
    total_nacional_mun = df_mun['total'].sum()
    df_mun['pct_total'] = (df_mun['total'] / total_nacional_mun * 100).round(1)

    # Cálculo de porcentajes
    for df in [df_prov, df_mun]:
        df['%_online'] = (df['online'] / df['total'] * 100).round(1)
        df['%_empresas'] = (df['empresas'] / df['total'] * 100).round(1)
        df['total'] = df['total'].astype('int32')
    
    return df_prov, df_mun

# ====================
# INTERFAZ PRINCIPAL
# ====================


# Carga de datos
geo_data = load_geo_data()
df_prov, df_mun = aggregate_data(st.session_state.filtered_data['expedientes'])


heigh_tab1 = 500
opacity_data_map = 0.8
colors_map_prov = "Plasma_r"
colors_map_mun = "Blues"
top_m_bar = 60
left_m_bar = 10
right_m_bar = 20
bottom_m_bar = 20
# ====================
# VISUALIZATION FUNCTIONS
# ====================

def create_province_barchart(df_prov):
    """Crea gráfico de barras vertical de provincias con estilo minimalista"""
    # Ordenar y calcular porcentajes
    df = df_prov.sort_values('total', ascending=False).nlargest(15, 'total').copy()  
    
    COLOR_PRIMARY = "#1f77b4"

    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=df['provincia'],  # Swapped x/y
        x=df['total'],      # Swapped x/y
        marker_color=COLOR_PRIMARY,
        hovertemplate="%{x:,}<extra></extra>",
        customdata=df['pct_total'],
        text=df['pct_total'].astype(str) + '%',
        textposition='outside',
        textfont=dict(size=10),
        orientation='h'  # Added horizontal orientation
    ))
    
    fig.update_layout(
        height=heigh_tab1,
        margin=dict(t=top_m_bar, b=bottom_m_bar, l= left_m_bar, r=right_m_bar),  # Adjusted margins for labels
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        ),
        yaxis=dict(  # Now yaxis for categories
            title=None,
            tickfont=dict(size=11),
            #automargin=True,
            autorange='reversed',
            # anchor="x",
            # fixedrange=True,
            # domain=[0, 1]            
        ),
        xaxis=dict(  # Now xaxis for values
            showgrid=False,
            zeroline=False,
            side = "top",
            range=[0, df['total'].max() * 1.15]            
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False
    )
    
    return fig, df


def create_province_map(df_prov, geojson):
    """Crea mapa coroplético de provincias"""
    # Asegurar matching de códigos INE
    df = df_prov.copy()
    df['codine_provincia'] = df['codine_provincia'].astype(str)
       
    fig = go.Figure(go.Choroplethmapbox(
        geojson=geojson,
        locations=df['codine_provincia'],
        z=df['total'],
        featureidkey="properties.codigo",
        colorscale= colors_map_prov,  # Color scale
        hovertemplate="%{customdata[0]}<br>" +
                  "<b>Expedientes:</b> %{customdata[1]}<br>" +
                  "%{customdata[2]:.2f}%<extra></extra>",
        customdata=df[['provincia', 'total', 'pct_total']].values,
        marker_opacity= opacity_data_map  # Set transparency
    ))
    
    fig.update_layout(
        height=heigh_tab1,
        margin=dict(t=60, b=0, l=0, r=0),
        mapbox=dict(
            style="carto-positron",  # Use Mapbox style
            zoom=5,  # Initial zoom level
            center={"lat": 40.0, "lon": -3.5}  # Center of the map (Spain in this case)
        )
    )
    
    return fig


def create_municipios_barchart(df_mun):
    """Crea gráfico de barras vertical de provincias con estilo minimalista"""
    # Ordenar y calcular porcentajes
    df = df_mun.sort_values('total', ascending=False).nlargest(15,'total').copy()  

    COLOR_PRIMARY = "#ff7f0e"

    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=df['municipio'],  # Swapped x/y
        x=df['total'],      # Swapped x/y
        marker_color=COLOR_PRIMARY,
        hovertemplate="%{x:,}<extra></extra>",
        customdata=df['pct_total'],
        text=df['pct_total'].astype(str) + '%',
        textposition='outside',
        textfont=dict(size=10),
        orientation='h'  # Added horizontal orientation
    ))
    
    fig.update_layout(
        height=heigh_tab1,
        margin=dict(t=top_m_bar, b=bottom_m_bar, l= left_m_bar, r=right_m_bar),  # Adjusted margins for labels
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        ),
        yaxis=dict(  # Now yaxis for categories
            title=None,
            tickfont=dict(size=11),
            #automargin=True,
            autorange='reversed',
            # anchor="x",
            # fixedrange=True,
            # domain=[0, 1]
        ),
        xaxis=dict(  # Now xaxis for values
            showgrid=False,
            zeroline=False,
            side = "top",
            range=[0, df['total'].max() * 1.15]            
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False
    )
    
    return fig, df

def create_municipio_map(df_mun, geojson):
    """Crea mapa coroplético de provincias"""
    # Asegurar matching de códigos INE
    df = df_mun.copy()
    df['codine'] = df['codine'].astype(str)
       
    fig = go.Figure(go.Choroplethmapbox(
        geojson=geojson,
        locations=df['codine'],
        z=df['total'],
        featureidkey="properties.CODIGOINE",
        colorscale=colors_map_mun,  # Color scale
        hovertemplate="%{customdata[0]}<br>" +
                  "<b>Expedientes:</b> %{customdata[1]}<br>" +
                  "%{customdata[2]:.2f}%<extra></extra>",
        customdata=df[['municipio', 'total', 'pct_total']].values,
        marker_opacity= opacity_data_map  # Set transparency
    ))
    
    fig.update_layout(
        height=heigh_tab1,
        margin=dict(t=60, b=0, l=0, r=0),
        mapbox=dict(
            style="carto-positron",  # Use Mapbox style
            zoom=6,  # Initial zoom level
            center={"lat": 40.0, "lon": -3.5}  # Center of the map (Spain in this case)
        )
    )
    
    return fig


# ====================
# PAGE STRUCTURE
# ====================

# Títulos y explicaciones
# st.header("Análisis Geográfico")
# st.markdown("""
# Visualiza cómo se distribuyen los trámites en el territorio, donde se hacen menos solicitudes telemáticas y donde hay más solicitudes por persona física o jurídica
# """)



tab1, tab2, tab3 = st.tabs([
    "Número de expedientes", 
    "Digitalización", 
    "Persona física/Persona jurídica"
])

with tab1:
    st.subheader("Número de expedientes por Provincia (datos de solicitud)")
    st.markdown("""
    Distribución geográfica de la demanda
    """)
    col_tab1_prov_1, col_tab1_prov_2 = st.columns([0.7,0.3])
    with col_tab1_prov_1:
        # Mapa coroplético
        map_fig_prov = create_province_map(df_prov, geo_data['provincias'])
        st.plotly_chart(map_fig_prov, use_container_width=True)
    with col_tab1_prov_2:
        # Gráfico de barras (now returns modified df)
        chart, chart_df = create_province_barchart(df_prov)
        st.plotly_chart(chart, use_container_width=True)
            

    # Análisis textual dinámico (using chart_df)
    # top_province = chart_df.iloc[0]  # First row after sorting
    # st.markdown(f"""
    # <div style="background-color:#f0f2f6; padding:15px; border-radius:10px; margin:15px 0;">
    #     <h4 style='color:#1f77b4'>🔍 Insight clave</h4>
    #     <b>{top_province['provincia']}</b> concentra el <b>{top_province['pct_total']}%</b> 
    #     de todos los expedientes a nivel nacional, siendo la provincia con mayor volumen.
    # </div>
    # """, unsafe_allow_html=True)
    
    
    st.divider()
    
    # Sección para el mapa (placeholder)
    st.subheader("Número de expedientes por Municipio")

    col_tab1_mun_1, col_tab1_mun_2 = st.columns([0.7,0.3])
    with col_tab1_mun_1:
        # Mapa coroplético
        map_fig_mun = create_municipio_map(df_mun, geo_data['municipios'])
        st.plotly_chart(map_fig_mun, use_container_width=True)
    with col_tab1_mun_2:
        # Gráfico de barras (now returns modified df)
        chart_mun, chart_df_mun = create_municipios_barchart(df_mun)
        st.plotly_chart(chart_mun, use_container_width=True)
    
# Notas al pie
st.caption(f"""
*Los porcentajes se calculan sobre el total de trámites en cada área geográfica.
Datos actualizados al {datetime.today().strftime('%d/%m/%Y')}
""")

