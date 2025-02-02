# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 19:19:18 2025

@author: flipe
"""

import streamlit as st


st.title("Entrada de solicitudes")

# Add your content here
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Solicitudes totales", "1.500")
with col2:
    st.metric("Telemáticas", "15 días")
with col3:
    st.metric("Persona física", "68%")

st.subheader("Evolución temporal")
# Add your time series chart