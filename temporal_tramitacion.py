# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.graph_objects as go


# Get parameters from session state
rango_fechas = st.session_state.get('rango_fechas', (None, None))
proced_seleccionado = st.session_state.get('proced_seleccionado', None)
estados_finales_selecc = [int(s) for s in st.session_state.estados_finales_selecc]
nombres_estados = st.session_state.estados.set_index('NUMTRAM')['DENOMINACION_SIMPLE'].to_dict()

# Initialize session state variable to store the selected date
if 'selected_date' not in st.session_state:
    st.session_state.selected_date = None
    
    
# Add this function for tab1 data processing
@st.cache_data(show_spinner="Procesando datos de inicio vs completados...")
def process_starts_vs_completed(estados_finales_selecc, freq):
    #cogemos directamente de session state para evitar problemas de actualizacion
    _tramites_df= st.session_state.datos_filtrados_rango['tramites'].copy()
    # Get all process starts (num_tramite=0)
    starts_df = _tramites_df[_tramites_df['num_tramite'] == 0].copy()
    
    # Group starts by month
    starts_df['fecha'] = starts_df['fecha_tramite'].dt.to_period(freq).dt.to_timestamp()
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

# Cached helper function to precompute not completed expedientes by start month
@st.cache_data(show_spinner="Calculando expedientes no completados...")
def get_not_completed_expedientes(estados_finales_selecc, freq):
    tramites_df = st.session_state.datos_filtrados_rango['tramites'].copy()
    expedientes = st.session_state.datos_filtrados_rango['expedientes'].copy()
    
    # Get all process starts
    starts_df = tramites_df[tramites_df['num_tramite'] == 0].copy()
    starts_df['fecha'] = starts_df['fecha_tramite'].dt.to_period(freq).dt.to_timestamp()
    
    # Determine completed processes
    completed_procs = tramites_df[tramites_df['num_tramite'].isin(estados_finales_selecc)]['id_exp'].unique() if estados_finales_selecc else []
    
    # Filter not completed processes
    not_completed = starts_df[~starts_df['id_exp'].isin(completed_procs)]
    
    # Merge with expedientes data
    not_completed_expedientes = not_completed.merge(expedientes, on='id_exp', how='left')
    
    # Generate state sequences for all expedientes
    state_sequences = tramites_df.groupby('id_exp').apply(
    lambda g: ' → '.join(
            g.sort_values('num_tramite').apply(
                lambda row: f"({pd.to_datetime(row['fecha_tramite']).strftime('%Y-%m-%d')}) {nombres_estados.get(row['num_tramite'], str(row['num_tramite']))}",
                axis=1
            )
        )
    ).reset_index(name='Secuencia')
    
    # Merge sequences into main dataframe
    not_completed_expedientes = not_completed_expedientes.merge(
        state_sequences, on='id_exp', how='left'
    )
    
    # Select and rename columns
    not_completed_expedientes = not_completed_expedientes[[
        'fecha', 'id_exp', 'unidad_tramitadora', 'fecha_registro_exp',
        'municipio_x', 'provincia_x', 'es_online_x', 'es_empresa_x', 'Secuencia'
    ]].rename(columns={
        'id_exp': 'ID Expediente',
        'unidad_tramitadora': 'Unidad Tramitadora',
        'fecha_registro_exp': 'Fecha Registro',
        'municipio_x': 'Municipio',
        'provincia_x': 'Provincia',
        'es_online_x': 'Online',
        'es_empresa_x': 'Empresa'
    })
    
    # Format registration date
    not_completed_expedientes['Fecha Registro'] = pd.to_datetime(
        not_completed_expedientes['Fecha Registro']
    ).dt.strftime('%Y-%m-%d')
    
    return not_completed_expedientes

# Add this new plot function
def create_start_completion_plot(data, freq):
    # Add not completed column
    data['not_completed'] = data['total_starts'] - data['completed']
    
    fig = go.Figure()
    
    # Not completed processes (orange)
    fig.add_trace(go.Bar(
        x=data['fecha'],
        y=data['not_completed'],
        name='No completados',
        #marker_color='#ff7f0e',
        customdata=data[['fecha']],
        hovertemplate="No completados: %{y}<extra></extra>"
    ))
    
    # Completed processes (green)
    fig.add_trace(go.Bar(
        x=data['fecha'],
        y=data['completed'],
        name='Completados',
        marker_color='Orange',
        customdata=data[['fecha']],
        hovertemplate="Completados: %{y}<extra></extra>"
    ))
    
 
    # Apply date range
    start_date = pd.to_datetime(rango_fechas[0]).to_period(freq).to_timestamp()
    end_date = pd.to_datetime(rango_fechas[1]).to_period(freq).to_timestamp()
    
    # Dynamic labels and ticks
    if freq == 'D':
        _tick_format = '%Y-%m-%d'
    elif freq == 'W':
        _tick_format = 'Semana %U, %Y'
    else:  # Mensual
        _tick_format = '%b %Y'
    
    
    fig.update_layout(
        barmode='stack',  # Changed to stack
        xaxis_title='Fecha',
        yaxis_title='Número de procesos',
        legend_title='Leyenda',
        hovermode="x unified",
        height=600,
        xaxis=dict(
            tickformat=_tick_format,
            range=[start_date, end_date]
        ),
        legend=dict(
            traceorder="normal",
            orientation="h",
            yanchor="bottom",
            y=1.02
        )
        #clickmode='select' 
    )
    
    return fig


@st.cache_data(show_spinner="Procesando datos de trámites...")
def process_tramites_data(_tramites_df, estados_finales_selecc, rango_fechas, proced_seleccionado, freq):
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
    filtered_df['fecha'] = filtered_df['fecha_tramite'].dt.to_period(freq).dt.to_timestamp()
    grouped = filtered_df.groupby(
        ['fecha', 'num_tramite', 'unidad_tramitadora']
    ).size().reset_index(name='count')
    
    # Add state names
    grouped['estado'] = grouped['num_tramite'].map(nombres_estados)
    
    return grouped

def create_evolution_plot(data , freq):
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
    start_date = pd.to_datetime(rango_fechas[0]).to_period(freq).to_timestamp() 
    end_date = pd.to_datetime(rango_fechas[1]).to_period(freq).to_timestamp()
    
    # Dynamic labels and ticks
    if freq == 'D':
        _tick_format = '%Y-%m-%d'
    elif freq == 'W':
        _tick_format = 'Semana %U, %Y'
    else:  # Mensual
        _tick_format = '%b %Y'
    
    fig.update_layout(
        barmode='stack',
        xaxis_title='Fecha',
        yaxis_title='Número de trámites',
        legend_title='Estados',
        hovermode="x unified",
        height=600,
        xaxis=dict(
            tickformat=_tick_format,
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

start_date, end_date = rango_fechas
if start_date is not None and end_date is not None:
    delta_days = (end_date - start_date).days
    if delta_days < 90:
        freq = 'D'
    elif delta_days < 180:
        freq = 'W'
    else:
        freq = 'M'
else:
    freq = 'M'
    
    
    
with tab1:
    st.subheader("Progreso de procesos iniciados")
    st.info("Representación del número de expedientes finalizados según el momento en que se presentaron. identifica expedientes pendientes desde hace tiempo. Pulsa en las barras para ver el detalle de los expedientes pendientes.", icon='📈')
    
    # Process data for tab1
    start_complete_data = process_starts_vs_completed(estados_finales_selecc, freq)
    
    # Create plot and capture click events
    progress_fig = create_start_completion_plot(start_complete_data, freq)
    #st.plotly_chart(progress_fig, use_container_width=True)
    event = st.plotly_chart(progress_fig, use_container_width=True, on_select="rerun")
    # Check if an event occurred and process it
    
    st.markdown("")
    st.markdown("")
    
    if event and 'selection' in event:
        selection = event['selection']
        if selection and 'points' in selection and len(selection['points']) > 0:
            # Extract the 'x' value from the first clicked point
            clicked_date_str = selection['points'][0]['x']
            clicked_date = pd.to_datetime(clicked_date_str).to_period(freq).to_timestamp()
            st.subheader(f"Expedientes de {clicked_date.strftime('%b %Y')} no completados")
            st.markdown("Estos expedientes no han alcanzado ninguno de los estados finales seleccionados")
            # Get precomputed not completed expedientes
            not_completed_expedientes = get_not_completed_expedientes(estados_finales_selecc, freq)
            # Filter for the selected month
            df_filtered = not_completed_expedientes[not_completed_expedientes['fecha'] == clicked_date]
            # Drop the 'fecha' column
            df_filtered = df_filtered.drop(columns=['fecha'])

            st.dataframe(df_filtered, 
                    hide_index = True,
                    column_config={
                    "ID Expediente": st.column_config.TextColumn(),
                    "Fecha de Registro": st.column_config.DatetimeColumn(format="DD/MM/YYYY")
                    })

    
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
        tramites_df, estados_finales_selecc, rango_fechas, proced_seleccionado, freq
    )
    
    # Main plot (sum across all units)
    main_plot_data = processed_data.groupby(
        ['fecha', 'num_tramite', 'estado']
    )['count'].sum().reset_index()
    main_fig = create_evolution_plot(main_plot_data, freq)
    st.plotly_chart(main_fig, use_container_width=True)
    
    # Unit-specific plots
    unique_units = processed_data['unidad_tramitadora'].unique()
    if len(unique_units) > 1:
        st.subheader("Filtrado por unidad tramitadora")
        selected_unit = st.selectbox("Seleccionar unidad tramitadora", options=unique_units)
        
        unit_data = processed_data[processed_data['unidad_tramitadora'] == selected_unit]
        unit_fig = create_evolution_plot(unit_data, freq)
        st.plotly_chart(unit_fig, use_container_width=True)

