import os
import re
import json
import duckdb
import numpy as np
import pandas as pd
import streamlit as st
from openai import OpenAI
from utils.llm import execute_sql
from utils.data_loader import load_data

# Agent Name
agent_name = "ChinoBot"

st.set_page_config(
    page_title="Track Sales Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Chinook Dashboard")

# Inititializa OpenAI client
client = OpenAI(
    api_key = st.secrets["TYPHOON_API_KEY"],
    base_url = st.secrets["TYPHOON_BASE_URL"]
)

system_prompt = f"""You are {agent_name}, an agent assist of Chinook Company.
    You task is to assist business user and finding information and respond to user questions.
    If users ask any question not related to Chinook Company, you must respond that Sorry I do not have context about the topic you asked.
    You are given tools as below to retrieve information from database and respond the user based on retrieved data: 
        - execute_sql: use this tool to retrieve information and provide information based on user question.
    Rules:
        - If the question need to be presented in table format, respond the user question with short description and table in markdown
"""

function_definition = [
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "extract the data based on user question",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_instruction": {
                        "type": "string",
                        "description": "User question related to the data"
                    }
                }
            }
        }
    }
]

# Check if chat history in streamlit session state or not
if "messages" not in st.session_state:
    # Initialize greeting message
    st.session_state.messages = [
        {"role": "system", "content": system_prompt},
        {"role": "assistant", "content": "Hello! How can I help you?"}
    ]

def get_response():
    final_response = ""

    response = client.chat.completions.create(
        model = st.secrets["TYPHOON_MODEL"],
        messages = [m for m in st.session_state.messages],
        tools = function_definition
    )

    tool_calls = response.choices[0].message.tool_calls

    if tool_calls:
        for tool_call in tool_calls: 
            function_name = tool_call.function.name
            arguments = tool_call.function.arguments

            if function_name == "execute_sql":
                kwargs = json.loads(arguments)
                result = execute_sql(**kwargs)   

                st.session_state.messages.append({"role": "tool", "content": str(result)})

        final_response = client.chat.completions.create(
            model = st.secrets["TYPHOON_MODEL"],
            messages = [m for m in st.session_state.messages]
        )

        return final_response.choices[0].message.content
    else:
        return response.choices[0].message.content

with st.sidebar:
    st.title(f"Chat with {agent_name}")

    container = st.container(height=700)

    # Iterating over chat history and display chat history
    for m in st.session_state.messages:
        if m["role"] not in ["system", "tool"]:
            with container.chat_message(m["role"]):
                st.markdown(m["content"])

    # Waiting for chat input
    if prompt := st.chat_input("Say something"):
        with container.chat_message("user"):
            st.markdown(prompt)
        # Append chat input from user to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})

        with container.chat_message("assistant"):
            with st.spinner():
                response = get_response()
                st.markdown(response)

        # Append chat response from LLM to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})

st.markdown("## Total sales over period of time")

year_list = load_data("""
        SELECT DISTINCT DATE_PART('year', InvoiceDate) AS year 
        FROM read_csv('data/chinook/invoices.csv') 
        ORDER BY year
    """)

with st.container():
    selected_year = st.selectbox('Select a year', year_list)
    df = load_data("""
        SELECT DATE_PART('year', InvoiceDate) AS year, SUM(Total) AS total 
        FROM read_csv('data/chinook/invoices.csv') 
        GROUP BY year
    """)
    st.bar_chart(df, x = 'year', y = 'total', y_label = "Total amount (USD)")

with st.container():
    st.markdown(f"## Sales Analysis in {selected_year}")
    cols = st.columns(2)
    with cols[0]:
        st.write(f"Total sales by country in {selected_year} ")
        top_country = load_data(f"""
            SELECT BillingCountry AS country, SUM(Total) AS total 
            FROM read_csv('data/chinook/invoices.csv') 
            WHERE DATE_PART('year', InvoiceDate) = {selected_year}
            GROUP BY country 
            ORDER BY total DESC
        """)
        st.bar_chart(top_country, x = 'country', y = 'total', horizontal = True, sort = "-total")

    with cols[1]:
        st.write(f"Top 10 tracks sales in {selected_year}")
        top_track = load_data(f"""
            SELECT tr.Name AS TrackName, SUM(inv_item.Quantity) AS TotalQty, SUM(inv_item.Quantity * inv_item.UnitPrice) AS TotalAmount
            FROM read_csv('data/chinook/invoice_items.csv') inv_item
            INNER JOIN read_csv('data/chinook/invoices.csv') inv
            ON inv_item.InvoiceId = inv.InvoiceId
            INNER JOIN read_csv('data/chinook/tracks.csv') tr
            ON inv_item.TrackId = tr.TrackId
            WHERE DATE_PART('year', inv.InvoiceDate) = {selected_year}
            GROUP BY tr.Name
            ORDER BY TotalQty  DESC
            LIMIT 10
        """)
        st.table(top_track)


st.markdown(f"## Sales Performance Analysis")
cols = st.columns(2)
top_sales_agent = load_data(f"""
        SELECT
            DATE_PART('year', inv.InvoiceDate) AS Year,
            emp.FirstName || ' ' || emp.LastName AS SupportRep,
            SUM(inv.Total) AS TotalSales
        FROM read_csv('data/chinook/invoices.csv') inv
        INNER JOIN read_csv('data/chinook/customers.csv') cust
        ON inv.CustomerId = cust.CustomerId
        INNER JOIN read_csv('data/chinook/employees.csv') emp
        ON cust.SupportRepId = emp.EmployeeId
        GROUP BY Year, SupportRep
        ORDER BY Year, TotalSales
        """)

with cols[0]:
    st.markdown(f"Total sales by agent over period of time")
    st.bar_chart(top_sales_agent, x = 'Year', y = 'TotalSales', color = 'SupportRep')
with cols[1]:
    st.markdown(f"Total sales by agent in {selected_year}")
    st.bar_chart(top_sales_agent[top_sales_agent["Year"] == selected_year], x = "SupportRep", y = "TotalSales")