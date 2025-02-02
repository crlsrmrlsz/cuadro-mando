# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 19:19:18 2025

@author: flipe
"""

import streamlit as st


st.title("Análisis Temporal")
st.write(f"Período analizado: {st.session_state.fecha_inicio} - {st.session_state.fecha_fin}")

# Add time analysis content
st.subheader("Tiempos por estado")
# Add your duration analysis charts