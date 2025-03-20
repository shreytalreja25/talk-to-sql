import re
from fastapi import FastAPI
from database import get_db_connection
from langchain.llms import Ollama  # type: ignore
from langchain.chains import LLMChain  # type: ignore
from langchain.prompts import PromptTemplate  # type: ignore

app = FastAPI()

# Initialize DeepSeek Model with Ollama
llm = Ollama(model="deepseek-r1:1.5b")

# Global variable to store the database schema
DATABASE_SCHEMA = None

def fetch_database_schema():
    """
    Fetches the database schema dynamically from INFORMATION_SCHEMA.
    """
    conn = get_db_connection()
    if not conn:
        return {}

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT TABLE_NAME, COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS 
            ORDER BY TABLE_NAME, ORDINAL_POSITION;
        """)
        rows = cursor.fetchall()
        conn.close()

        schema_dict = {}
        for row in rows:
            table, column = row
            if table not in schema_dict:
                schema_dict[table] = set()
            schema_dict[table].add(column)

        return schema_dict
    except Exception as e:
        return {}

def get_schema():
    """
    Returns the cached schema or fetches it if not already retrieved.
    """
    global DATABASE_SCHEMA
    if DATABASE_SCHEMA is None:
        DATABASE_SCHEMA = fetch_database_schema()
    return DATABASE_SCHEMA

def validate_sql_query(sql_query):
    """
    Validates whether the generated SQL query contains correct table and column names.
    """
    schema = get_schema()
    if not schema:
        return False, "Database schema could not be retrieved."

    # Extract table names from the query
    table_matches = re.findall(r"FROM\s+([a-zA-Z_]+)|JOIN\s+([a-zA-Z_]+)", sql_query, re.IGNORECASE)
    tables_in_query = {t for match in table_matches for t in match if t}

    # If SELECT * is present, skip column validation (all columns are allowed)
    if "SELECT *" in sql_query.upper():
        return True, "SQL Query is valid."

    # Extract column names from the query (excluding * for wildcard selects)
    column_matches = re.findall(r"SELECT\s+(.*?)\s+FROM", sql_query, re.IGNORECASE)
    columns_in_query = set()

    if column_matches:
        columns_raw = column_matches[0].split(",")
        columns_in_query = {col.strip().split(" ")[0] for col in columns_raw}  # Remove aliasing

    # Check if all tables exist in schema
    for table in tables_in_query:
        if table not in schema:
            return False, f"Table '{table}' does not exist in the database."

    # Check if all columns exist in the specified tables
    for column in columns_in_query:
        found = any(column in schema[table] for table in tables_in_query)
        if not found:
            return False, f"Column '{column}' does not exist in any referenced tables."

    return True, "SQL Query is valid."

def generate_sql_prompt(question):
    """
    Generates a structured SQL query generation prompt using the schema.
    """
    schema = get_schema()
    schema_text = "The database contains the following tables and columns:\n\n"
    for table, columns in schema.items():
        schema_text += f"Table: {table}\n" + "\n".join(f" - {col}" for col in columns) + "\n\n"

    return f"{schema_text}\nConvert this user question into a safe and correct SQL query: {question}"

sql_prompt = PromptTemplate(
    input_variables=["question"],
    template="{question}"
)

# LangChain LLMChain
sql_chain = LLMChain(llm=llm, prompt=sql_prompt)

def clean_sql_response(response: str) -> str:
    """
    Cleans and extracts the final SQL query from the DeepSeek response.
    Ensures correct aliasing and column names.
    """
    if not response or "ERROR" in response:
        return None  # Prevents execution of an invalid response

    # Remove <think> blocks if present
    response = re.sub(r"<think>[\s\S]*?</think>", "", response).strip()

    # Extract SQL query from markdown-style triple backticks (```sql ... ```)
    sql_match = re.search(r"```sql\s+([\s\S]*?)```", response, re.MULTILINE)
    if sql_match:
        response = sql_match.group(1).strip()

    # Fallback: Try to extract the last SELECT statement
    select_match = re.search(r"(SELECT\s+.*?;)", response, re.IGNORECASE | re.DOTALL)
    if select_match:
        response = select_match.group(1).strip()

    # Ensure the query only contains valid table and column names
    schema = get_schema()
    if not schema:
        return None  # If schema retrieval failed, return None

    # Extract table names from the query
    table_matches = re.findall(r"FROM\s+([a-zA-Z_]+)|JOIN\s+([a-zA-Z_]+)", response, re.IGNORECASE)
    tables_in_query = {t for match in table_matches for t in match if t}

    # Ensure tables exist in schema
    for table in tables_in_query:
        if table not in schema:
            return None  # Return None if the table doesn't exist

    # Extract column names (with potential aliasing)
    column_matches = re.findall(r"SELECT\s+(.*?)\s+FROM", response, re.IGNORECASE)
    
    if column_matches:
        columns_raw = column_matches[0].split(",")
        columns_in_query = {col.strip().split(" ")[0] for col in columns_raw}  # Remove aliasing

        # Fix incorrect column names
        for column in columns_in_query:
            found = any(column in schema[table] for table in tables_in_query)
            if not found:
                return None  # Invalid column detected, reject the query

    return response if "SELECT" in response else None  # Return None if query is still invalid

@app.get("/")
def root():
    return {"message": "TalkToSQL Backend is Running!"}

@app.get("/test-db")
def test_db():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        return {"message": "Database connected successfully"}
    else:
        return {"error": "Failed to connect to the database"}

@app.get("/generate-sql")
def generate_sql(question: str):
    """
    Converts a natural language question into an SQL query using DeepSeek with schema guidance.
    """
    dynamic_prompt = generate_sql_prompt(question)
    sql_chain.prompt.template = dynamic_prompt  # Update prompt with schema
    raw_response = sql_chain.run(question)
    sql_query = clean_sql_response(raw_response)

    if sql_query is None:
        return {"error": "Failed to generate a valid SQL query.", "query": raw_response}

    # Validate SQL before returning
    is_valid, validation_message = validate_sql_query(sql_query)
    if not is_valid:
        return {"error": validation_message, "query": sql_query}

    return {"sql_query": sql_query}

@app.get("/execute-query")
def execute_query(question: str):
    """
    Generates and executes an SQL query based on user input.
    """
    dynamic_prompt = generate_sql_prompt(question)
    sql_chain.prompt.template = dynamic_prompt  # Update prompt with schema
    raw_response = sql_chain.run(question)
    cleaned_query = clean_sql_response(raw_response)

    if cleaned_query is None:
        return {"error": "Failed to generate a valid SQL query.", "query": raw_response}

    # Validate SQL before execution
    is_valid, validation_message = validate_sql_query(cleaned_query)
    if not is_valid:
        return {"error": validation_message, "query": cleaned_query}

    conn = get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}

    try:
        cursor = conn.cursor()
        cursor.execute(cleaned_query)
        result = cursor.fetchall()
        conn.close()
        return {"query": cleaned_query, "result": result}
    except Exception as e:
        return {"error": str(e), "query": cleaned_query}
