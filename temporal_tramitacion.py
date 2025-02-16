# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# Get parameters from session state
rango_fechas = st.session_state.get('rango_fechas', (None, None))
proced_seleccionado = st.session_state.get('proced_seleccionado', None)
estados_finales_selecc = [int(s) for s in st.session_state.estados_finales_selecc]
nombres_estados = st.session_state.estados.set_index('NUMTRAM')['DENOMINACION_SIMPLE'].to_dict()


# Add this function for tab1 data processing
@st.cache_data(show_spinner="Procesando datos de inicio vs completados...")
def process_starts_vs_completed(estados_finales_selecc):
    
    _tramites_df= st.session_state.datos_filtrados_rango['tramites'].copy()
    # Get all process starts (num_tramite=0)
    starts_df = _tramites_df[_tramites_df['num_tramite'] == 0].copy()
    
    # Group starts by month
    starts_df['fecha'] = starts_df['fecha_tramite'].dt.to_period('M').dt.to_timestamp()
    monthly_starts = starts_df.groupby('fecha')['id_exp'].nunique().reset_index(name='total_starts')
    
    if estados_finales_selecc:
        # Find processes that reached final states
        completed_procs = _tramites_df[
            _tramites_df['num_tramite'].isin(estados_finales_selecc)
        ]['id_exp'].unique()
        
        # Filter starts that were completed
        completed_starts = starts_df[
            starts_df['id_exp'].isin(completed_procs)
        ].groupby('fecha')['id_exp'].nunique().reset_index(name='completed')
        
        # Merge data
        merged = monthly_starts.merge(completed_starts, on='fecha', how='left')
    else:
        merged = monthly_starts.assign(completed=0)
    
    return merged.fillna(0)

# Add this new plot function
def create_start_completion_plot(data):
    fig = go.Figure()
    
    # Main starts bar
    fig.add_trace(go.Bar(
        x=data['fecha'],
        y=data['total_starts'],
        name='Procesos iniciados',
        marker_color='#1f77b4',
        # width=0.4  # Wider bar for starts
    ))
    
    # Completed overlay bar
    if data['completed'].sum() > 0:
        fig.add_trace(go.Bar(
            x=data['fecha'],
            y=data['completed'],
            name='Procesos completados',
            marker_color='#ff7f0e',
            # width=0.3,  # Narrower bar for completed
            #offset=0  # Offset to left-align
        ))
    
    # Apply date range from session state
    start_date = pd.to_datetime(rango_fechas[0]).to_period('M').to_timestamp()
    end_date = pd.to_datetime(rango_fechas[1]).to_period('M').to_timestamp()
    
    fig.update_layout(
        barmode='group',
        xaxis_title='Fecha',
        yaxis_title='Número de procesos',
        legend_title='Leyenda',
        hovermode="x unified",
        height=600,
        xaxis=dict(
            tickformat="%b %Y",
            range=[start_date, end_date]
        ),
        legend=dict(
            traceorder="normal",
            orientation="h",
            yanchor="bottom",
            y=1.02
        )
    )
    return fig


@st.cache_data(show_spinner="Procesando datos de trámites...")
def process_tramites_data(_tramites_df, estados_finales_selecc, rango_fechas, proced_seleccionado):
    # Filter processes that passed through selected final states
    # mask = _tramites_df.groupby('id_exp')['num_tramite'].transform(
    #     lambda x: x.isin(estados_finales_selecc).any()
    # )
    # filtered_df = _tramites_df[mask]
    # Filter processes that passed through selected final states
    if not estados_finales_selecc:
        filtered_df = _tramites_df
    else:
        mask = _tramites_df.groupby('id_exp')['num_tramite'].transform(
            lambda x: x.isin(estados_finales_selecc).any()
        )
        filtered_df = _tramites_df[mask]
    
    # Group by month, state, and processing unit
    filtered_df['fecha'] = filtered_df['fecha_tramite'].dt.to_period('M').dt.to_timestamp()
    grouped = filtered_df.groupby(
        ['fecha', 'num_tramite', 'unidad_tramitadora']
    ).size().reset_index(name='count')
    
    # Add state names
    grouped['estado'] = grouped['num_tramite'].map(nombres_estados)
    
    return grouped

def create_evolution_plot(data):
    fig = go.Figure()
    states = sorted(data['num_tramite'].unique(), key=lambda x: int(x))
    
    for state in states:
        state_data = data[data['num_tramite'] == state]
        fig.add_trace(go.Bar(
            x=state_data['fecha'],
            y=state_data['count'],
            name=state_data['estado'].iloc[0],
            visible=True if state == 0 else 'legendonly', 
            hovertemplate=(
                #"<b>%{x|%b %Y}</b><br>"
                "Estado: %{meta[0]}<br>"
                "Cantidad: %{y}<extra></extra>"
            ),
            meta=[state_data['estado'].iloc[0]]
        ))
    # Get date range from session state
    start_date = pd.to_datetime(rango_fechas[0]).to_period('M').to_timestamp() 
    end_date = pd.to_datetime(rango_fechas[1]).to_period('M').to_timestamp()
    
    fig.update_layout(
        barmode='stack',
        xaxis_title='Fecha',
        yaxis_title='Número de trámites',
        legend_title='Estados',
        hovermode="x unified",
        height=600,
        xaxis=dict(
            tickformat="%b %Y",
            range=[start_date, end_date]  # Force date range
        ),
        legend=dict(traceorder="normal")
    )
    return fig


# ------------------------------------------
# INTERFACE / USER INTERFACE
# ------------------------------------------
tab1, tab2 = st.tabs([
    "Evolución tiempo de tramitación", 
    "Evolución cambios de estado"
])

    
with tab1:
    st.subheader("Progreso de procesos iniciados")
    st.info("Muestra la cantidad de procesos iniciados vs aquellos que alcanzaron estados finales seleccionados", icon='📈')
    
 
    # Process data for tab1
    start_complete_data = process_starts_vs_completed(estados_finales_selecc)
    
    # Create and display plot
    progress_fig = create_start_completion_plot(start_complete_data)
    st.plotly_chart(progress_fig, use_container_width=True)
    
    # Add explanatory text
    if estados_finales_selecc:
        st.markdown("""
            **Interpretación:**
            - Barras azules: Total de procesos iniciados cada mes
            - Barras naranjas: Procesos de esos iniciados que alcanzaron los estados finales seleccionados
            """)
    else:
        st.warning("No se han seleccionado estados finales para mostrar procesos completados")

    
with tab2: 
    # Page Start
    st.subheader("Evolución de la tramitación a lo largo del tiempo")
    st.info("Permite identificar patrones temporales en la ejecución de cada trámite, picos, caidas, tendencias. Selecciona los trámites que quieres analizar", icon='🏔️')
    # Update the tab1 section
    tramites_df = st.session_state.datos_filtrados_rango['tramites'].copy()
    # Prepare data
    tramites_df['unidad_tramitadora'] = tramites_df['unidad_tramitadora'].fillna('No especificada')
    
    # Process data once
    processed_data = process_tramites_data(
        tramites_df, estados_finales_selecc, rango_fechas, proced_seleccionado
    )
    
    # Main plot (sum across all units)
    main_plot_data = processed_data.groupby(
        ['fecha', 'num_tramite', 'estado']
    )['count'].sum().reset_index()
    main_fig = create_evolution_plot(main_plot_data)
    st.plotly_chart(main_fig, use_container_width=True)
    
    # Unit-specific plots
    unique_units = processed_data['unidad_tramitadora'].unique()
    if len(unique_units) > 1:
        st.subheader("Filtrado por unidad tramitadora")
        selected_unit = st.selectbox("Seleccionar unidad tramitadora", options=unique_units)
        
        unit_data = processed_data[processed_data['unidad_tramitadora'] == selected_unit]
        unit_fig = create_evolution_plot(unit_data)
        st.plotly_chart(unit_fig, use_container_width=True)

