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
    BAR_WIDTH_GLOBAL = 30  # Height per bar for global chart
    BAR_WIDTH_GROUPED = 20  # Height per bar for grouped chart
    PADDING = 80  # Padding for titles and margins
    
    # Original bar chart
    st.subheader("Duración media de cada trámite para toda la Comunidad")
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
    st.plotly_chart(fig_global, use_container_width=True)

    # Grouped bar chart if multiple unidades
    unique_unidades = filtered_processes['unidad_tramitadora'].nunique()
    if unique_unidades > 1:
        st.subheader("Tiempos medios de cada Unidad Tramitadora")
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
            custom_data=["Unidad", "Count"]
        )
        
        # Update hover template
        fig_grouped.update_traces(
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Unidad: %{customdata[0]}<br>"  # ← Now index 0 is Unidad
                "Duración: %{x:.1f} días<br>"
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
                yanchor="bottom",
                y=-0.1,
                xanchor="center",
                x=0.5
            ),
            uniformtext_minsize=8,
            uniformtext_mode='hide',
            yaxis=dict(autorange='reversed', title=None),
            xaxis_range=[0, max_x_group]
        )
        fig_grouped.update_yaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(211,211,211,0.3)'
        )
        st.plotly_chart(fig_grouped, use_container_width=True)
