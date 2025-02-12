import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Verificar session_state
if "filtered_data" not in st.session_state:
    st.error("Cargue los datos desde la página principal primero.")
    st.stop()

# Diccionario con nombres de estados y la lista de estados seleccionados
state_names = st.session_state.estados.set_index('NUMTRAM')['DENOMINACION_SIMPLE'].to_dict()
selected_states = [int(s) for s in st.session_state.selected_final_states]

@st.cache_data
def process_flows_for_transitions(tramites, selected_states):
    # Ordenar trámites y calcular la duración entre ellos
    tramites_sorted = tramites.sort_values(['id_exp', 'fecha_tramite'])
    tramites_sorted['next_fecha'] = tramites_sorted.groupby('id_exp')['fecha_tramite'].shift(-1)
    tramites_sorted['duration'] = (
        (tramites_sorted['next_fecha'] - tramites_sorted['fecha_tramite'])
        .dt.total_seconds() / 86400
    ).fillna(0)
    
    # Agrupar por expediente para obtener la secuencia de estados y sus duraciones
    process_states = tramites_sorted.groupby('id_exp').agg(
        all_states=('num_tramite', lambda x: list(x.astype(int))),
        durations=('duration', list)
    ).reset_index()
    
    # Filtrar expedientes que contengan al menos uno de los estados seleccionados
    return process_states[process_states['all_states'].apply(lambda x: any(s in selected_states for s in x))]

# Procesar los trámites
filtered_processes = process_flows_for_transitions(
    st.session_state.filtered_data['tramites'], selected_states
)

# Calcular estadísticas de transición
transition_stats = {}
for _, row in filtered_processes.iterrows():
    exp_id = row['id_exp']
    states = row['all_states']
    durations = row['durations']
    for i in range(len(states) - 1):
        transition = (states[i], states[i+1])
        duration = durations[i]
        if transition not in transition_stats:
            transition_stats[transition] = {'sum_duration': 0.0, 'count': 0, 'process_ids': set()}
        transition_stats[transition]['sum_duration'] += duration
        transition_stats[transition]['count'] += 1
        transition_stats[transition]['process_ids'].add(exp_id)

# Convertir la información en un DataFrame
data = []
for (src, tgt), stats in transition_stats.items():
    count = stats['count']
    unique_processes = len(stats['process_ids'])
    avg_duration = stats['sum_duration'] / count if count > 0 else 0
    src_label = state_names.get(src, f"S-{src}")
    tgt_label = state_names.get(tgt, f"S-{tgt}")
    data.append({
        'Transition': f"{src_label} → {tgt_label}",
        'Count': count,
        'Unique Processes': unique_processes,
        'Mean Duration': avg_duration
    })

df_transitions = pd.DataFrame(data)

# Crear dos pestañas: una para la gráfica de barras y otra para la de dispersión
tab_bar, tab_scatter = st.tabs(["Gráfica de Barras", "Gráfica de Dispersión"])

with tab_bar:
    st.subheader("Gráfica de Barras Horizontal")
    df_bar = df_transitions.sort_values("Mean Duration", ascending=True)
    fig_bar = go.Figure(go.Bar(
        x=df_bar["Mean Duration"],
        y=df_bar["Transition"],
        orientation="h",
        text=df_bar["Mean Duration"].apply(lambda x: f"{int(round(x))} días"),
        textposition="outside",
        marker_color="indianred"
    ))
    fig_bar.update_layout(
        template="plotly_white",
        title="Transiciones ordenadas por Duración Media",
        xaxis_title="Duración Media (días)",
        yaxis_title="Transición",
        margin=dict(l=120, r=20, t=40, b=20)
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with tab_scatter:
    st.subheader("Gráfica de Dispersión (Bubble Chart)")
    # Asignar un color único a cada transición
    transitions_list = df_transitions["Transition"].tolist()
    color_palette = px.colors.qualitative.Plotly
    transition_color = {
        tran: color_palette[i % len(color_palette)] for i, tran in enumerate(transitions_list)
    }
    
    fig_scatter = go.Figure()
    for _, row in df_transitions.iterrows():
        fig_scatter.add_trace(go.Scatter(
            x=[row["Count"]],
            y=[row["Mean Duration"]],
            mode="markers",
            marker=dict(
                size=row["Unique Processes"] * 1.5,
                color=transition_color.get(row["Transition"], "#1f77b4"),
                opacity=0.8
            ),
            name=row["Transition"],
            hovertemplate=(
                f"<b>{row['Transition']}</b><br>Número de casos: {row['Count']}<br>"
                f"Duración media: {int(round(row['Mean Duration']))} días<br>"
                f"Procesos únicos: {row['Unique Processes']}<extra></extra>"
            )
        ))
    fig_scatter.update_layout(
        template="plotly_white",
        title="Transiciones: Número de Casos vs Duración Media",
        xaxis_title="Número de Casos",
        yaxis_title="Duración Media (días)",
        legend_title="Transición",
        margin=dict(l=40, r=40, t=60, b=40)
    )
    st.plotly_chart(fig_scatter, use_container_width=True)
