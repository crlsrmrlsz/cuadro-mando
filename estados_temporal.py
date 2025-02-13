import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

if "filtered_data" not in st.session_state:
    st.error("Cargue los datos desde la página principal primero.")
    st.stop()

state_names = st.session_state.estados.set_index('NUMTRAM')['DENOMINACION_SIMPLE'].to_dict()
selected_states = [int(s) for s in st.session_state.selected_final_states]

@st.cache_data
def process_flows_for_transitions(tramites, selected_states):
    tramites_sorted = tramites.sort_values(['id_exp', 'fecha_tramite'])
    tramites_sorted['next_fecha'] = tramites_sorted.groupby('id_exp')['fecha_tramite'].shift(-1)
    tramites_sorted['duration'] = (
        (tramites_sorted['next_fecha'] - tramites_sorted['fecha_tramite'])
        .dt.total_seconds() / 86400
    ).fillna(0)
    tramites_sorted['unidad_tramitadora'] = tramites_sorted['unidad_tramitadora'].fillna('Desconocida')
    
    process_states = tramites_sorted.groupby('id_exp').agg(
        all_states=('num_tramite', lambda x: list(x.astype(int))),
        durations=('duration', list),
        unidad_tramitadora=('unidad_tramitadora', 'first')
    ).reset_index()
    
    return process_states[process_states['all_states'].apply(lambda x: any(s in selected_states for s in x))]

filtered_processes = process_flows_for_transitions(
    st.session_state.filtered_data['tramites'], selected_states
)

# Calculate global transitions
transition_stats = {}
transition_stats_grouped = {}
for _, row in filtered_processes.iterrows():
    exp_id = row['id_exp']
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

# Create main transitions dataframe
data = []
for (src, tgt), stats in transition_stats.items():
    avg_duration = stats['sum_duration'] / stats['count'] if stats['count'] > 0 else 0
    src_label = state_names.get(src, f"S-{src}")
    tgt_label = state_names.get(tgt, f"S-{tgt}")
    data.append({
        'Transition': f"{src_label} → {tgt_label}",
        'Mean Duration': avg_duration,
        'Count': stats['count']
    })
df_transitions = pd.DataFrame(data).sort_values("Mean Duration", ascending=True)

# Calculate figure height
n_bars = len(df_transitions)
bar_height = 30  # Adjust this value to control bar spacing
fig_height = n_bars * bar_height + 120  # Add padding for titles/labels

tab_bar, tab_scatter = st.tabs(["Tiempos medios por transición", "Cuellos de botella"])

with tab_bar:
    # Parameters for bar dimensions
    BAR_WIDTH_GLOBAL = 40  # Height per bar for global chart
    BAR_WIDTH_GROUPED = 20  # Height per bar for grouped chart
    PADDING = 80  # Padding for titles and margins
    
    # Original bar chart
    st.subheader("Duración Media Global")
    fig_global = go.Figure()
    fig_global.add_trace(go.Bar(
        x=df_transitions["Mean Duration"],
        y=df_transitions["Transition"],
        orientation="h",
        text=df_transitions["Mean Duration"].round().astype(int).astype(str) + " días",
        textposition="outside",
        marker_color="indianred",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Duración: %{x:.1f} días<br>"
            "Procesos: %{customdata}<extra></extra>"
        ),
        customdata=df_transitions["Count"]
    ))
    fig_global.update_layout(
        height=len(df_transitions) * BAR_WIDTH_GLOBAL + PADDING,
        template="plotly_white",
        margin=dict(l=120, r=20, t=40, b=20),
        xaxis_title="Duración Media (días)",
        yaxis_title=None,
        showlegend=False
    )
    st.plotly_chart(fig_global, use_container_width=True)

    # Grouped bar chart if multiple unidades
    unique_unidades = filtered_processes['unidad_tramitadora'].nunique()
    if unique_unidades > 1:
        st.subheader("Duración Media por Unidad Tramitadora")
        # Create grouped dataframe
        grouped_data = []
        for (src, tgt, unidad), stats in transition_stats_grouped.items():
            avg_duration = stats['sum_duration'] / stats['count'] if stats['count'] > 0 else 0
            src_label = state_names.get(src, f"S-{src}")
            tgt_label = state_names.get(tgt, f"S-{tgt}")
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
            text=df_grouped["Mean Duration"].round(1).astype(str) + " días",
            category_orders={"Transition": transition_order},
            custom_data=["Count"]
        )
        
        # Update hover template
        fig_grouped.update_traces(
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Unidad: %{marker.color}<br>"
                "Duración: %{x:.1f} días<br>"
                "Procesos: %{customdata[0]}<extra></extra>"
            )
        )
        
        # Update layout
        fig_grouped.update_layout(
            height=fig_height_grouped,
            template="plotly_white",
            margin=dict(l=120, r=20, t=40, b=20),
            xaxis_title="Duración Media (días)",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.1,
                xanchor="center",
                x=0.5
            ),
            uniformtext_minsize=8,
            uniformtext_mode='hide',
            yaxis=dict(autorange='reversed', title=None),
        )
        fig_grouped.update_traces(
            textposition='outside',
            textfont_size=12,
            marker_line_width=0
        )
        st.plotly_chart(fig_grouped, use_container_width=True)


# import streamlit as st
# import pandas as pd
# import plotly.graph_objects as go
# import plotly.express as px

# # Verificar session_state
# if "filtered_data" not in st.session_state:
#     st.error("Cargue los datos desde la página principal primero.")
#     st.stop()

# # Diccionario con nombres de estados y la lista de estados seleccionados
# state_names = st.session_state.estados.set_index('NUMTRAM')['DENOMINACION_SIMPLE'].to_dict()
# selected_states = [int(s) for s in st.session_state.selected_final_states]

# # Parámetros para la altura de cada barra (en píxeles)
# BAR_HEIGHT = 40
# BAR_HEIGHT_GROUP = 20  # Barra más pequeña para la gráfica agrupada

# @st.cache_data
# def process_flows_for_transitions(tramites, selected_states):
#     # Ordenar trámites y calcular la duración entre ellos
#     tramites_sorted = tramites.sort_values(['id_exp', 'fecha_tramite'])
#     tramites_sorted['next_fecha'] = tramites_sorted.groupby('id_exp')['fecha_tramite'].shift(-1)
#     tramites_sorted['duration'] = (
#         (tramites_sorted['next_fecha'] - tramites_sorted['fecha_tramite'])
#         .dt.total_seconds() / 86400
#     ).fillna(0)
    
#     # Agrupar por expediente:
#     # - 'all_states': lista de estados (convertidos a int)
#     # - 'durations': lista de duraciones entre trámites
#     # - 'unidad_tramitadora': se toma el primer valor (ya que es único por id_exp)
#     process_states = tramites_sorted.groupby('id_exp').agg(
#         all_states=('num_tramite', lambda x: list(x.astype(int))),
#         durations=('duration', list),
#         unidad_tramitadora=('unidad_tramitadora', 'first')
#     ).reset_index()
    
#     # Filtrar expedientes que contengan al menos uno de los estados seleccionados
#     return process_states[process_states['all_states'].apply(lambda x: any(s in selected_states for s in x))]

# # Procesar los trámites
# filtered_processes = process_flows_for_transitions(
#     st.session_state.filtered_data['tramites'], selected_states
# )

# # ========================
# # Estadísticas de Transición Global
# # ========================
# transition_stats = {}
# for _, row in filtered_processes.iterrows():
#     exp_id = row['id_exp']
#     states = row['all_states']
#     durations = row['durations']
#     for i in range(len(states) - 1):
#         transition = (states[i], states[i+1])
#         duration = durations[i]
#         if transition not in transition_stats:
#             transition_stats[transition] = {'sum_duration': 0.0, 'count': 0, 'process_ids': set()}
#         transition_stats[transition]['sum_duration'] += duration
#         transition_stats[transition]['count'] += 1
#         transition_stats[transition]['process_ids'].add(exp_id)

# # Convertir la información global en un DataFrame
# data = []
# for (src, tgt), stats in transition_stats.items():
#     count = stats['count']
#     unique_processes = len(stats['process_ids'])
#     avg_duration = stats['sum_duration'] / count if count > 0 else 0
#     src_label = state_names.get(src, f"S-{src}")
#     tgt_label = state_names.get(tgt, f"S-{tgt}")
#     data.append({
#         'Transition': f"{src_label} → {tgt_label}",
#         'Count': count,
#         'Unique Processes': unique_processes,
#         'Mean Duration': avg_duration
#     })

# df_transitions = pd.DataFrame(data)
# # Ordenar de menor a mayor duración media
# df_transitions = df_transitions.sort_values("Mean Duration", ascending=True)

# # Calcular altura para la gráfica global
# chart_height_global = max(400, len(df_transitions) * BAR_HEIGHT)

# # Crear gráfica de barras global (horizontal)
# fig_global = go.Figure(go.Bar(
#     x=df_transitions["Mean Duration"],
#     y=df_transitions["Transition"],
#     orientation="h",
#     text=df_transitions["Mean Duration"].apply(lambda x: f"{int(round(x))} días"),
#     textposition="outside",
#     marker_color="indianred",
#     customdata=df_transitions[['Count']],  # Pasar "Count" como customdata
#     hovertemplate="<b>%{y}</b><br>Duración media: %{x:.1f} días<br>Número de casos: %{customdata[0]}<extra></extra>"
# ))
# fig_global.update_layout(
#     template="plotly_white",
#     title="Transiciones ordenadas por Duración Media (Global)",
#     xaxis_title="Duración Media (días)",
#     margin=dict(l=120, r=20, t=40, b=20),
#     height=chart_height_global
# )

# # ========================
# # Estadísticas Agrupadas por Unidad Tramitadora
# # ========================
# # Se agrupa por (transición, unidad_tramitadora) utilizando el valor único de cada proceso.
# grouped_transition_stats = {}
# for _, row in filtered_processes.iterrows():
#     exp_id = row['id_exp']
#     states = row['all_states']
#     durations = row['durations']
#     # Tomamos la primera unidad_tramitadora (es la misma para todo el proceso)
#     ut = row['unidad_tramitadora']
#     for i in range(len(states) - 1):
#         transition = (states[i], states[i+1])
#         key = (transition, ut)
#         if key not in grouped_transition_stats:
#             grouped_transition_stats[key] = {'sum_duration': 0.0, 'count': 0, 'process_ids': set()}
#         grouped_transition_stats[key]['sum_duration'] += durations[i]
#         grouped_transition_stats[key]['count'] += 1
#         grouped_transition_stats[key]['process_ids'].add(exp_id)

# grouped_data = []
# for (transition, ut), stats in grouped_transition_stats.items():
#     count = stats['count']
#     unique_processes = len(stats['process_ids'])
#     avg_duration = stats['sum_duration'] / count if count > 0 else 0
#     src_label = state_names.get(transition[0], f"S-{transition[0]}")
#     tgt_label = state_names.get(transition[1], f"S-{transition[1]}")
#     transition_label = f"{src_label} → {tgt_label}"
#     grouped_data.append({
#         'Transition': transition_label,
#         'unidad_tramitadora': ut if pd.notnull(ut) else "Sin datos",
#         'Count': count,
#         'Unique Processes': unique_processes,
#         'Mean Duration': avg_duration
#     })

# df_group = pd.DataFrame(grouped_data)

# # Forzar que el orden de las transiciones en el gráfico agrupado sea el mismo que en el gráfico global.
# ordered_transitions = df_transitions["Transition"].tolist()
# df_group["Transition"] = pd.Categorical(df_group["Transition"], categories=ordered_transitions, ordered=True)
# df_group = df_group.sort_values("Transition")

# # Calcular altura para la gráfica agrupada (por número de transiciones) usando BAR_HEIGHT_GROUP
# num_groups = df_group["Transition"].nunique()
# chart_height_group = max(400, num_groups * BAR_HEIGHT_GROUP * len(df_group["unidad_tramitadora"].unique()))

# # Crear gráfica de barras agrupada por unidad_tramitadora (barmode = 'group')
# fig_group = go.Figure()
# for ut in df_group["unidad_tramitadora"].unique():
#     df_ut = df_group[df_group["unidad_tramitadora"] == ut]
#     fig_group.add_trace(go.Bar(
#          x=df_ut["Mean Duration"],
#          y=df_ut["Transition"],
#          name=str(ut),
#          orientation="h",
#          text=df_ut["Mean Duration"].apply(lambda x: f"{int(round(x))} días"),
#          textposition="outside",
#          customdata=df_ut[['Count']],  # Pasar "Count" como customdata
#          hovertemplate=(
#              "Unidad Tramitadora: " + str(ut) +
#              "<br>Transition: %{y}" +
#              "<br>Duración: %{x:.1f} días" +
#              "<br>Número de casos: %{customdata[0]}<extra></extra>"
#          )
#     ))
# fig_group.update_layout(
#     barmode="group",
#     template="plotly_white",
#     title="Transiciones por Unidad Tramitadora",
#     xaxis_title="Duración Media (días)",
#     margin=dict(l=120, r=20, t=40, b=20),
#     height=chart_height_group,
#     legend=dict(
#         orientation="h",
#         y=-0.2,
#         x=0.5,
#         xanchor='center'
#     )
# )

# # ========================
# # Mostrar ambos gráficos en la misma pestaña
# # ========================
# tab_bar, tab_scatter, tab_acumulado = st.tabs(["Tiempos medios de transiciones", "Cuellos de botella", "Carga de trabajo acumulada"])

# with tab_bar:
#     st.subheader("Gráfica de Barras Global")
#     st.plotly_chart(fig_global, use_container_width=True)
    
#     # Mostrar la gráfica agrupada solo si hay más de una unidad_tramitadora
#     if df_group["unidad_tramitadora"].nunique() > 1:
#         st.subheader("Gráfica de Barras Agrupada por Unidad Tramitadora")
#         st.plotly_chart(fig_group, use_container_width=True)
#     else:
#         st.info("No hay más de una unidad tramitadora en los datos para mostrar la gráfica agrupada.")

# with tab_scatter:
#     st.subheader("Gráfica de Dispersión (Bubble Chart)")
#     # Asignar un color único a cada transición
#     transitions_list = df_transitions["Transition"].tolist()
#     color_palette = px.colors.qualitative.Plotly
#     transition_color = {
#         tran: color_palette[i % len(color_palette)] for i, tran in enumerate(transitions_list)
#     }
    
#     fig_scatter = go.Figure()
#     for _, row in df_transitions.iterrows():
#         fig_scatter.add_trace(go.Scatter(
#             x=[row["Count"]],
#             y=[row["Mean Duration"]],
#             mode="markers",
#             marker=dict(
#                 size=row["Unique Processes"] * 1.5,
#                 color=transition_color.get(row["Transition"], "#1f77b4"),
#                 opacity=0.8
#             ),
#             name=row["Transition"],
#             hovertemplate=(
#                 f"<b>{row['Transition']}</b><br>Número de casos: {row['Count']}<br>"
#                 f"Duración media: {int(round(row['Mean Duration']))} días<br>"
#                 f"Procesos únicos: {row['Unique Processes']}<extra></extra>"
#             )
#         ))
#     fig_scatter.update_layout(
#         template="plotly_white",
#         title="Transiciones: Número de Casos vs Duración Media",
#         xaxis_title="Número de Casos",
#         yaxis_title="Duración Media (días)",
#         margin=dict(l=40, r=40, t=60, b=40)
#     )
#     st.plotly_chart(fig_scatter, use_container_width=True)
