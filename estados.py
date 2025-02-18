import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

if "datos_filtrados_rango" not in st.session_state:
    st.error("Cargue los datos desde la página principal primero.")
    st.stop()

# Get parameters from session state
rango_fechas = st.session_state.get('rango_fechas', (None, None))
proced_seleccionado = st.session_state.get('proced_seleccionado', None)
estados_finales_selecc = [int(s) for s in st.session_state.estados_finales_selecc]
nombres_estados = st.session_state.estados.set_index('NUMTRAM')['DENOMINACION_SIMPLE'].to_dict()

@st.cache_data(show_spinner="Calculando transiciones de estados")
def process_flows_for_transitions(tramites, estados_finales_selecc, rango_fechas, proced_seleccionado):
    tramites_sorted = tramites.sort_values(['id_exp', 'fecha_tramite'])
    tramites_sorted['next_fecha'] = tramites_sorted.groupby('id_exp')['fecha_tramite'].shift(-1)
    tramites_sorted['duration'] = (
        (tramites_sorted['next_fecha'] - tramites_sorted['fecha_tramite'])
        .dt.total_seconds() / 86400
    ).fillna(0)
    tramites_sorted['unidad_tramitadora'] = tramites_sorted['unidad_tramitadora'].fillna('No especificada')
    
    tram_filtr_agg_tiempos = tramites_sorted.groupby('id_exp').agg(
        all_states=('num_tramite', lambda x: list(x.astype(int))),
        durations=('duration', list),
        unidad_tramitadora=('unidad_tramitadora', 'first')
    ).reset_index()
    if not estados_finales_selecc:
        filtered_processed = tram_filtr_agg_tiempos
    else:
        filtered_processed = tram_filtr_agg_tiempos[tram_filtr_agg_tiempos['all_states'].apply(
            lambda x: any(s in estados_finales_selecc for s in x)
        )]
    # filtered_processed = tram_filtr_agg_tiempos[tram_filtr_agg_tiempos['all_states'].apply(
    #     lambda x: any(s in estados_finales_selecc for s in x))]
    
    return filtered_processed

@st.cache_data
def calculate_transition_stats(filtered_processes, estados_finales_selecc, rango_fechas, proced_seleccionado):
    transition_stats = {}
    transition_stats_grouped = {}
    
    for _, row in filtered_processes.iterrows():
        #exp_id = row['id_exp']
        states = row['all_states']
        durations = row['durations']
        unidad = row['unidad_tramitadora']
        
        for i in range(len(states) - 1):
            src, tgt = states[i], states[i+1]
            duration = durations[i]
            
            # Global stats
            if (src, tgt) not in transition_stats:
                transition_stats[(src, tgt)] = {'sum_duration': 0.0, 'count': 0}
            transition_stats[(src, tgt)]['sum_duration'] += duration
            transition_stats[(src, tgt)]['count'] += 1
            
            # Grouped stats
            key = (src, tgt, unidad)
            if key not in transition_stats_grouped:
                transition_stats_grouped[key] = {'sum_duration': 0.0, 'count': 0}
            transition_stats_grouped[key]['sum_duration'] += duration
            transition_stats_grouped[key]['count'] += 1
    
    return transition_stats, transition_stats_grouped


@st.cache_data
def build_transition_dataframes(transition_stats, transition_stats_grouped):
    # Create main transitions dataframe
    data = []
    for (src, tgt), stats in transition_stats.items():
        avg_duration = stats['sum_duration'] / stats['count'] if stats['count'] > 0 else 0
        src_label = nombres_estados.get(src, f"S-{src}")
        tgt_label = nombres_estados.get(tgt, f"S-{tgt}")
        data.append({
            'src': src,  # added column for ordering
            'Transition': f"{src_label} → {tgt_label}",
            'Mean Duration': avg_duration,
            'Count': stats['count']
        })
    # Now sorting by the 'src' column
    df_transitions = pd.DataFrame(data).sort_values("src", ascending=False)

    # Prepare scatter data
    data_scatter_global = []
    for (src, tgt), stats in transition_stats.items():
        mean_duration = stats['sum_duration'] / stats['count'] if stats['count'] > 0 else 0
        total_days = stats['sum_duration']
        count = stats['count']
        src_label = nombres_estados.get(src, f"S-{src}")
        tgt_label = nombres_estados.get(tgt, f"S-{tgt}")
        transition_label = f"{src_label} → {tgt_label}"
        data_scatter_global.append({
            'src': src,  # added column for ordering
            'Transition': transition_label,
            'Mean Duration': mean_duration,
            'Total Processes': count,
            'Total Days': total_days
        })
    df_scatter_global = pd.DataFrame(data_scatter_global).sort_values("src", ascending=False)

    # Grouped scatter data
    data_scatter_grouped = []
    for (src, tgt, unidad), stats in transition_stats_grouped.items():
        mean_duration = stats['sum_duration'] / stats['count'] if stats['count'] > 0 else 0
        total_days = stats['sum_duration']
        count = stats['count']
        src_label = nombres_estados.get(src, f"S-{src}")
        tgt_label = nombres_estados.get(tgt, f"S-{tgt}")
        transition_label = f"{src_label} → {tgt_label}"
        data_scatter_grouped.append({
            'src': src,  # added column for ordering
            'Transition': transition_label,
            'Unidad': unidad,
            'Mean Duration': mean_duration,
            'Total Processes': count,
            'Total Days': total_days
        })
    df_scatter_grouped = pd.DataFrame(data_scatter_grouped).sort_values("src", ascending=False)

    return df_transitions, df_scatter_global, df_scatter_grouped


# Main processing pipeline
tramites_data = st.session_state.datos_filtrados_rango['tramites']
filtered_processes = process_flows_for_transitions(
    tramites_data, estados_finales_selecc, rango_fechas, proced_seleccionado
)
transition_stats, transition_stats_grouped = calculate_transition_stats(
    filtered_processes, estados_finales_selecc, rango_fechas, proced_seleccionado
)
df_transitions, df_scatter_global, df_scatter_grouped = build_transition_dataframes(
    transition_stats, transition_stats_grouped
)

# Tab definitions remain the same
tab_bar, tab_scatter = st.tabs(["Cuellos de botella", "Grandes consumidores de tiempo"])


with tab_bar:
    # Parameters for bar dimensions
    BAR_WIDTH_GLOBAL = 30  # Height per bar for global chart
    BAR_WIDTH_GROUPED = 20  # Height per bar for grouped chart
    PADDING = 80  # Padding for titles and margins
    
    # Original bar chart
    st.subheader("Duración media de cada trámite para toda la Comunidad")
    st.info("En esta gráfica se puede ver qué transisiones son las que tardan más, permite analizar si los tiempos están justificados, de qué variables depende el tiemp que se tarda y sacar conclusiones sobre cómo se tramitan los expedientes y puntos de mejora",icon='🕘')
    fig_global = go.Figure()
    fig_global.add_trace(go.Bar(
        x=df_transitions["Mean Duration"],
        y=df_transitions["Transition"],
        orientation="h",
        text=df_transitions["Mean Duration"].round().astype(int).astype(str) + " días",
        textposition="outside",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Duración: %{x:.1f} días<br>"
            "Procesos: %{customdata}<extra></extra>"
        ),
        customdata=df_transitions["Count"]
    ))
    max_x = df_transitions["Mean Duration"].max() * 1.2
    fig_global.update_layout(
        height=len(df_transitions) * BAR_WIDTH_GLOBAL + PADDING,
        template="plotly_white",
        margin=dict(l=120, r=20, t=40, b=20),
        xaxis_title="Duración Media (días)",
        yaxis_title=None,
        showlegend=False,
        xaxis_range=[0, max_x]
    )
    shapes = []
    for i in range(len(df_transitions)):
        if i % 2 == 0:
            shapes.append(dict(
                type="rect",
                xref="x", yref="y",
                x0=0, y0=i-0.5,
                x1=max_x, y1=i+0.5,
                fillcolor='rgba(0,0,0,0.03)',
                line={"width": 0},
                layer="below"
            ))
    
    fig_global.update_layout(shapes=shapes)
    fig_global.update_layout(
        plot_bgcolor='rgba(245,245,245,0.2)',
        yaxis=dict(showgrid=False, gridcolor='rgba(0,0,0,0.1)', gridwidth=1),
        xaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.1)', gridwidth=1)
    )
    st.plotly_chart(fig_global, use_container_width=True)

    # Grouped bar chart if multiple unidades
    unique_unidades = filtered_processes['unidad_tramitadora'].nunique()
    if unique_unidades > 1:
        st.subheader("Tiempos medios de cada Unidad Tramitadora")
        st.info("Puede haber grandes diferencias en el tiempo que se tarda en cada Unidad en ejecutar ciertos trámites",icon='😱')
        # Create grouped dataframe
        grouped_data = []
        for (src, tgt, unidad), stats in transition_stats_grouped.items():
            avg_duration = stats['sum_duration'] / stats['count'] if stats['count'] > 0 else 0
            src_label = nombres_estados.get(src, f"S-{src}")
            tgt_label = nombres_estados.get(tgt, f"S-{tgt}")
            grouped_data.append({
                'Transition': f"{src_label} → {tgt_label}",
                'Unidad': unidad,
                'Mean Duration': avg_duration,
                'Count': stats['count']
            })
        # Create grouped dataframe with same order
        transition_order = df_transitions['Transition'].tolist()
        df_grouped = pd.DataFrame(grouped_data)
        df_grouped['Transition'] = pd.Categorical(
            df_grouped['Transition'], 
            categories=transition_order, 
            ordered=True
        )
        df_grouped = df_grouped.sort_values('Transition')

        # Calculate height for grouped chart
        n_groups = len(transition_order)
        group_height = BAR_WIDTH_GROUPED * unique_unidades
        fig_height_grouped = n_groups * group_height + PADDING

        # Create grouped chart
        fig_grouped = px.bar(
            df_grouped,
            x="Mean Duration",
            y="Transition",
            color="Unidad",
            orientation="h",
            barmode="group",
            color_discrete_sequence=px.colors.qualitative.Plotly,
            text=df_grouped["Mean Duration"].round(1).astype(str) + " días",
            category_orders={"Transition": transition_order},
            custom_data=["Unidad", "Count"]
        )
        
        # Update hover template
        fig_grouped.update_traces(
            hovertemplate=(
                #"<b>%{y}</b><br>"
                "Unidad: %{customdata[0]}<br>"  # ← Now index 0 is Unidad
                "Duración: %{x:.0f} días<br>"
                "Procesos: %{customdata[1]}<extra></extra>"  # ← Index 1 is Count
            ),
            textposition='outside',
            textfont_size=12,
            marker_line_width=0
        )
        max_x_group = df_grouped["Mean Duration"].max() * 1.2
        # Update layout
        fig_grouped.update_layout(
            height=fig_height_grouped,
            template="plotly_white",
            margin=dict(l=120, r=20, t=40, b=20),
            xaxis_title="Duración Media (días)",
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.015,
                xanchor="center",
                x=0.5
            ),
            uniformtext_minsize=8,
            uniformtext_mode='hide',
            yaxis=dict(autorange='reversed', title=None),
            xaxis_range=[0, max_x_group]
        )
        shapes = []
        for i in range(len(df_transitions)):
            if i % 2 == 0:
                shapes.append(dict(
                    type="rect",
                    xref="x", yref="y",
                    x0=0, y0=i-0.5,
                    x1=max_x, y1=i+0.5,
                    fillcolor='rgba(0,0,0,0.03)',
                    line={"width": 0},
                    layer="below"
                ))
        
        fig_grouped.update_layout(shapes=shapes)
        fig_grouped.update_layout(
            plot_bgcolor='rgba(245,245,245,0.2)',
            yaxis=dict(showgrid=False, gridcolor='rgba(0,0,0,0.1)', gridwidth=1),
            xaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.1)', gridwidth=1)
        )
        st.plotly_chart(fig_grouped, use_container_width=True)

# Create scatter plots in second tab
with tab_scatter:
    # Global scatter plot
    if not df_scatter_global.empty:
        st.subheader("Estados que consumen más tiempo, datos globales de toda la Comunidad")
        st.info("El tamaño de la burbuja representa el número total de días dedicados a lo largo de la tramitación de todos los expedientes en el rango de fechas seleccionado. Se calcula como la multiplicación del tiempo medio y el número total expedientes que han pasado por ese trámite. Por lo tanto, las burbujas más grandes son los **grandes consumidores de tiempo**", icon='🧛‍♀️')
        fig_global = px.scatter(
            df_scatter_global,
            x='Mean Duration',
            y='Total Processes',
            size='Total Days',
            hover_name='Transition',
            custom_data=['Total Days'],
            size_max=40,
            labels={
                'Mean Duration': 'Duración Media (días)',
                'Total Processes': 'Número de Procesos',
                'Total Days': 'Días Totales'
            }
        )
        fig_global.update_traces(
            hovertemplate=(
                "<b>%{hovertext}</b><br>"
                "Duración Media: %{x:.1f} días<br>"
                "Procesos: %{y}<br>"
                "Días Totales: %{customdata[0]:.1f}<extra></extra>"
            ),
            #marker=dict(opacity=0.7, line=dict(width=0.5, color='Gray'))
        )
        fig_global.update_layout(
            template="plotly_white",
            xaxis_title="Duración Media (días)",
            yaxis_title="Número de Procesos",
            hovermode="closest"
        )

        fig_global.update_layout(
            plot_bgcolor='rgba(245,245,245,0.2)',
            yaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.1)', gridwidth=1),
            xaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.1)', gridwidth=1)
        )
        st.plotly_chart(fig_global, use_container_width=True)
    else:
        st.warning("No hay datos disponibles para el gráfico global")

    # Grouped scatter plot (only if multiple unidades)
    if unique_unidades > 1 and not df_scatter_grouped.empty:
        st.subheader("Comparación de tiempo empleado en cada estado entre Unidades Tramitadoras")
        st.info("Compara si hay diferencias en qué estados consumen más tiempo total en cada Unidad Tramitadora", icon='🧐')
        fig_grouped = px.scatter(
            df_scatter_grouped,
            x='Mean Duration',
            y='Total Processes',
            size='Total Days',
            color='Unidad',
            hover_name='Transition',
            custom_data=['Unidad', 'Total Days'],
            size_max=40,
            color_discrete_sequence=px.colors.qualitative.Plotly,
            labels={
                'Mean Duration': 'Duración Media (días)',
                'Total Processes': 'Número de Procesos',
                'Total Days': 'Días Totales'
            }
        )
        fig_grouped.update_traces(
            hovertemplate=(
                "<b>%{hovertext}</b><br>"
                "Unidad: %{customdata[0]}<br>"
                "Duración Media: %{x:.1f} días<br>"
                "Procesos: %{y}<br>"
                "Días Totales: %{customdata[1]:.1f}<extra></extra>"
            ),
            #marker=dict(opacity=0.7, line=dict(width=0.3, color='Gray'))
        )
        fig_grouped.update_layout(
            template="plotly_white",
            xaxis_title="Duración Media (días)",
            yaxis_title="Número de Procesos",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.3,
                xanchor="center",
                x=0.5
            ),
            hovermode="closest"
        )
        fig_grouped.update_layout(
            plot_bgcolor='rgba(245,245,245,0.2)',
            yaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.1)', gridwidth=1),
            xaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.1)', gridwidth=1)
        )
        st.plotly_chart(fig_grouped, use_container_width=True)
    elif unique_unidades > 1:
        st.warning("No hay datos suficientes para comparar unidades")
        