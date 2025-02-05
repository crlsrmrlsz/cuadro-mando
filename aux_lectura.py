# -*- coding: utf-8 -*-
"""
Created on Wed Feb  5 06:12:49 2025

@author: flipe
"""

import pandas as pd

df_e = pd.read_parquet('data/tratados/884/expedientes.parquet')
df_t = pd.read_parquet('data/tratados/884/tramites.parquet')