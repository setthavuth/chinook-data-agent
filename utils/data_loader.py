import os
import duckdb
import numpy as np
import pandas as pd

def load_data(sql):
    df = duckdb.sql(sql).to_df()
    return df