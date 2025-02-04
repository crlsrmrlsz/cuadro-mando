# input_geografico.py
import streamlit as st
import json
import plotly.graph_objects as go
from datetime import datetime


# Títulos y explicaciones
st.header("Análisis Geográfico")
st.markdown("""
Visualiza cómo se distribuyen los trámites en el territorio, donde se hacen menos solicitudes telemáticas y donde hay más solicitudes por persona física o jurídica""")

# ====================
# CACHED DATA LOADING
# ====================

@st.cache_data
def load_geo_data():
    """Carga los datos geográficos"""
    with open('data/geo/provincias_id_ine.geojson', 'r', encoding='utf-8') as f:
        prov_geojson = json.load(f)
    
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


# Carga de datos
geo_data = load_geo_data()
df_prov, df_mun = aggregate_data(st.session_state.filtered_data['expedientes'])



# ====================
# VISUALIZATION FUNCTIONS
# ====================

def create_province_barchart(df_prov):
    """Crea gráfico de barras vertical de provincias con estilo minimalista"""
    # Ordenar y calcular porcentajes
    df = df_prov.sort_values('total', ascending=False).copy()  
    total_nacional = df['total'].sum()
    df['pct_total'] = (df['total'] / total_nacional * 100).round(1)

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
        #width=600,
        height=500,
        margin=dict(t=80, b=10, l=10, r=10),  # Adjusted margins for labels
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        ),
        yaxis=dict(  # Now yaxis for categories
            title=None,
            tickfont=dict(size=11),
            automargin=True,
            autorange='reversed'
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

# ====================
# PAGE STRUCTURE
# ====================

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
    col_tab1_1, col_tab1_2 = st.columns([0.7,0.3])
    with col_tab1_1:
        st.markdown("""
        **aqui ira el grafico de provincias
        """)
    with col_tab1_2:
        # Gráfico de barras (now returns modified df)
        chart, chart_df = create_province_barchart(df_prov)
        st.plotly_chart(chart, use_container_width=False)
            

    # Análisis textual dinámico (using chart_df)
    top_province = chart_df.iloc[0]  # First row after sorting
    st.markdown(f"""
    <div style="background-color:#f0f2f6; padding:15px; border-radius:10px; margin:15px 0;">
        <h4 style='color:#1f77b4'>🔍 Insight clave</h4>
        <b>{top_province['provincia']}</b> concentra el <b>{top_province['pct_total']}%</b> 
        de todos los expedientes a nivel nacional, siendo la provincia con mayor volumen.
    </div>
    """, unsafe_allow_html=True)
    st.divider()
    
    # Sección para el mapa (placeholder)
    st.subheader("Visualización Geográfica")
    st.markdown("""
    *En desarrollo: Mapa interactivo que mostrará la distribución territorial detallada, 
    combinando datos de volumen con tasas de digitalización.*
    """)
    
# Notas al pie
st.caption(f"""
*Los porcentajes se calculan sobre el total de trámites en cada área geográfica.
Datos actualizados al {datetime.today().strftime('%d/%m/%Y')}
""")