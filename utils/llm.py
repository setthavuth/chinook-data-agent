import re
import os
import json
import duckdb
import numpy as np
import pandas as pd
import streamlit as st
from openai import OpenAI

schema_file = open("data/chinook_schema.json")
schema_dict = json.load(schema_file)

schema_string = "\n\n".join([schema for schema in schema_dict.values()])

client = OpenAI(
    api_key = st.secrets["TYPHOON_API_KEY"],
    base_url = st.secrets["TYPHOON_BASE_URL"]
)

def sql_generator(user_question):
    system_prompt = f"""ํYou're expert query generator. \
    Your task is to write correct and optimized queries based on the database schema and user questions. \
    Use database schema delimited in triple quotes to consider the tables, column and SQL generation. \
    '''{schema_string}'''

    Example format of SQL is delimited by <SQL FORMAT> tags
    <SQL FORMAT>
        SELECT
            <column_name>
        FROM 
            read_csv('data/chinook/<table_name>')
    </SQL FORMAT>

    Rules:
    - Always use the column and table names exactly as defined.
    - Always use the table names with the following format: read_csv('data/chinook/<table>.csv')
    - Return only SQL code (no explanation or markdown unless requested).
    - If multiple tables are required, use proper JOINs based on foreign key relationships.
    - If aggregation is needed, include GROUP BY as required.
    - If user input is ambiguous, write your best interpretation and comment it.
    - If the user uses term 'Sales Agent', keep in mind that Sales Agents are employees with Title 'Sales Support Agents'
    - Return SQL code without tags
    """

    response = client.chat.completions.create(
        model = st.secrets["TYPHOON_MODEL"],
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question}
        ]
    )

    return response.choices[0].message.content

def execute_sql(user_instruction):
    sql_string = sql_generator(user_instruction)
    dataframe = duckdb.sql(sql_string).to_df()
    return dataframe.to_string()

def chart_generator(user_instruction):
    pass