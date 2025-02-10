# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 19:19:18 2025

@author: flipe
"""

# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from streamlit_plotly_events import plotly_events

@st.cache_data
def preprocess_visualization_data(state_groups):
    """Preprocess data for all visualizations with caching"""
    bubble_data = []
    heatmap_data = []
    flow_legend = []
    
    for group_idx, group in enumerate(state_groups):
        state_code = group['state_name'][:3].upper()
        
        for seq_idx, seq in enumerate(group['sequences']):
            flow_code = f"{state_code}-{seq_idx+1:02d}"
            total_duration = sum(seq['state_durations']) if seq['state_durations'] else 0
            num_steps = len(seq['state_names'])
            
            # Add metadata for flow lookup
            flow_metadata = {
                'group_idx': group_idx,
                'seq_idx': seq_idx
            }
            
            # Bubble Chart Data
            bubble_data.append({
                'Flow': flow_code,
                'Frequency': seq['count'],
                'Total Duration': total_duration,
                'Steps': num_steps,
                'Final State': group['state_name'],
                **flow_metadata
            })
            
            # Heatmap Data
            heat_row = {'Flow': flow_code, 'Final State': group['state_name'], **flow_metadata}
            for step_idx, (state, duration) in enumerate(zip(seq['state_names'], seq['state_durations'])):
                heat_row[f'Step {step_idx+1}'] = duration
            heatmap_data.append(heat_row)
            
            # Flow Legend
            flow_legend.append({
                'Code': flow_code,
                'Flow': " → ".join(seq['state_names']),
                'Final State': group['state_name'],
                'Avg. Days': total_duration,
                'Steps': num_steps,
                **flow_metadata
            })
    
    return pd.DataFrame(bubble_data), pd.DataFrame(heatmap_data), pd.DataFrame(flow_legend)

def show_flow_details(selected_flow, flow_legend_df, state_groups):
    """Display detailed breakdown for a selected flow"""
    try:
        flow_info = flow_legend_df[flow_legend_df['Code'] == selected_flow].iloc[0]
        group_idx = flow_info['group_idx']
        seq_idx = flow_info['seq_idx']
        
        group = state_groups[group_idx]
        seq = group['sequences'][seq_idx]
        
        with st.expander(f"🔍 Detailed Analysis: {selected_flow}", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                # Waterfall Chart
                if seq['state_durations']:
                    fig_steps = px.bar(
                        x=seq['state_names'][:-1],
                        y=seq['state_durations'],
                        labels={'x': 'Process Step', 'y': 'Days'},
                        title='Step Durations'
                    )
                    st.plotly_chart(fig_steps, use_container_width=True)
            
            with col2:
                # Timeline Visualization
                if seq['state_durations']:
                    cumulative = np.cumsum([0] + seq['state_durations'])
                    fig_time = px.line(
                        x=range(len(cumulative)),
                        y=cumulative,
                        markers=True,
                        labels={'x': 'Step Number', 'y': 'Cumulative Days'},
                        title='Cumulative Timeline'
                    )
                    st.plotly_chart(fig_time, use_container_width=True)
            
            st.markdown(f"**Full Flow Path:** {flow_info['Flow']}")
            st.markdown(f"**Total Processes:** {seq['count']} | **Average Total Duration:** {flow_info['Avg. Days']:.1f} days")
    
    except Exception as e:
        st.error(f"Error displaying flow details: {str(e)}")


# Load processed data from previous steps
state_groups = st.session_state.get('state_groups', [])

# Preprocess data for visualizations
bubble_df, heatmap_df, legend_df = preprocess_visualization_data(state_groups)

# Create tab layout
tab1, tab2, tab3 = st.tabs(["Flow Matrix", "Step Patterns", "Flow Legend"])

with tab1:
    # Interactive Bubble Chart
    st.header("Process Flow Matrix Analysis")
    
    fig_bubble = px.scatter(
        bubble_df,
        x='Frequency',
        y='Total Duration',
        size='Steps',
        color='Final State',
        hover_name='Flow',
        log_x=True,
        title='Flow Characteristics: Frequency vs Duration vs Complexity'
    )
    
    # Add trend line for reference
    fig_bubble.add_shape(
        type='line',
        x0=0.9*bubble_df['Frequency'].min(),
        y0=bubble_df['Total Duration'].median(),
        x1=1.1*bubble_df['Frequency'].max(),
        y1=bubble_df['Total Duration'].median(),
        line=dict(color='gray', dash='dash')
    )
    
    st.plotly_chart(fig_bubble, use_container_width=True)
    
    # In the main function, modify the bubble chart section:
    selected_point = plotly_events(fig_bubble, click_event=True)
    if selected_point:
        try:
            selected_flow = bubble_df.iloc[selected_point[0]['pointIndex']]['Flow']
            show_flow_details(selected_flow, legend_df, state_groups)
        except Exception as e:
            st.error(f"Error processing selection: {str(e)}")

with tab2:
    # Heatmap Visualization
    st.header("Step Duration Patterns")
    
    # Prepare heatmap data
    heatmap_fig = px.imshow(
        heatmap_df.set_index('Flow'),
        aspect='auto',
        labels=dict(x="Process Step", y="Flow", color="Days"),
        color_continuous_scale='Viridis'
    )
    
    # Improve heatmap readability
    heatmap_fig.update_layout(
        xaxis_title="Process Step Number",
        yaxis_title="Flow Code",
        coloraxis_colorbar=dict(title="Days")
    )
    st.plotly_chart(heatmap_fig, use_container_width=True)

with tab3:
    # Interactive Legend Table
    st.header("Flow Code Legend")
    
    # Search functionality
    search_col1, search_col2 = st.columns(2)
    with search_col1:
        search_term = st.text_input("Search flows:")
    with search_col2:
        min_steps = st.slider("Minimum steps:", 1, 20, 1)
    
    # Filter legend
    filtered_legend = legend_df[
        (legend_df['Flow'].str.contains(search_term, case=False)) &
        (legend_df['Steps'] >= min_steps)
    ]
    
    # Display interactive table
    st.dataframe(
        filtered_legend,
        column_config={
            "Code": "Flow ID",
            "Flow": st.column_config.TextColumn(width="large"),
            "Avg. Days": st.column_config.NumberColumn(format="%.1f"),
            "Steps": "Step Count"
        },
        height=600,
        use_container_width=True
    )
