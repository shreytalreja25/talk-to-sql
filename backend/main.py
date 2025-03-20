import os
import re
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware  # Import CORS Middleware
from database import get_db_connection
from groq import Groq  # Using Groq SDK

# Load environment variables
load_dotenv()

app = FastAPI()

# ✅ Fix CORS Issues: Allow frontend to call backend API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows requests from any frontend (change this to ["http://localhost:5173"] for security)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Initialize Groq Client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

# Global variable to store the database schema
DATABASE_SCHEMA = None

def fetch_database_schema():
    """ Fetches the database schema dynamically from INFORMATION_SCHEMA. """
    print("[DEBUG] Fetching database schema...")

    conn = get_db_connection()
    if not conn:
        print("[ERROR] Failed to connect to the database while fetching schema.")
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
        for table, column in rows:
            if table not in schema_dict:
                schema_dict[table] = set()
            schema_dict[table].add(column)

        print(f"[SUCCESS] Schema fetched: {schema_dict}")
        return schema_dict
    except Exception as e:
        print(f"[ERROR] Error fetching schema: {e}")
        return {}

def get_schema():
    """ Returns the cached schema or fetches it if not already retrieved. """
    global DATABASE_SCHEMA
    if DATABASE_SCHEMA is None:
        print("[DEBUG] Schema is not cached. Fetching new schema...")
        DATABASE_SCHEMA = fetch_database_schema()
    return DATABASE_SCHEMA

def generate_sql_prompt(question):
    """ Generates a structured SQL query prompt using the schema. """
    print("[DEBUG] Generating SQL prompt...")

    schema = get_schema()
    if not schema:
        print("[ERROR] Schema could not be retrieved.")
        return "Schema could not be retrieved."

    schema_text = "The database contains the following tables and columns:\n\n"
    for table, columns in schema.items():
        schema_text += f"Table: {table}\n" + "\n".join(f" - {col}" for col in columns) + "\n\n"

    prompt = f"""
    Given an input question, create a syntactically correct SQL query to retrieve the answer.

    Use only the available tables and columns. Do not generate queries with missing columns.

    **Available tables and columns:**
    {schema_text}

    **Question:** {question}

    Only return the SQL query and nothing else.
    """

    print(f"[SUCCESS] SQL Prompt generated:\n{prompt}")
    return prompt.strip()

def call_groq_api(prompt):
    """ Calls the Groq API to generate an SQL query using streaming. """
    print("[DEBUG] Calling Groq API...")

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Ensure correct model name
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_completion_tokens=1024,
            top_p=1,
            stream=True,  # Enable streaming for efficiency
            stop=None
        )

        response_text = ""
        for chunk in completion:
            if chunk.choices and chunk.choices[0].delta.content:
                response_text += chunk.choices[0].delta.content

        print(f"[SUCCESS] Groq returned SQL query:\n{response_text}")
        return response_text.strip()
    except Exception as e:
        print(f"[ERROR] Groq API Error: {e}")
        return None

def clean_sql_response(response: str) -> str:
    """ Extracts the SQL query from the Groq response and removes irrelevant text. """
    if not response:
        print("[ERROR] No response from Groq to clean.")
        return None

    print("[DEBUG] Cleaning SQL response...")

    # Remove any explanations before or after the SQL query
    response = re.sub(r"<think>[\s\S]*?</think>", "", response).strip()

    # Extract SQL query from markdown-style triple backticks
    sql_match = re.search(r"```sql\s+([\s\S]*?)```", response, re.MULTILINE)
    if sql_match:
        cleaned_query = sql_match.group(1).strip()
        print(f"[SUCCESS] Extracted SQL Query:\n{cleaned_query}")
        return cleaned_query

    # Fallback: Try to extract the last SELECT statement
    select_match = re.search(r"(SELECT\s+.*?;)", response, re.IGNORECASE | re.DOTALL)
    if select_match:
        cleaned_query = select_match.group(1).strip()
        print(f"[SUCCESS] Extracted SQL Query:\n{cleaned_query}")
        return cleaned_query

    print("[ERROR] No valid SQL query found in response.")
    return None

@app.get("/")
def root():
    return {"message": "TalkToSQL Backend is Running!"}

@app.get("/fetch-schema")
def fetch_schema():
    """ Fetches and caches the database schema. """
    print("[DEBUG] Fetching database schema...")
    schema = get_schema()
    if not schema:
        print("[ERROR] Failed to fetch schema.")
        return {"error": "Failed to fetch schema"}
    return {"schema": schema}

@app.get("/generate-sql")
async def generate_sql(question: str):
    """ Uses Groq API to generate an SQL query based on the input question. """
    print(f"[DEBUG] Generating SQL for question: {question}")

    try:
        prompt = generate_sql_prompt(question)
        raw_response = call_groq_api(prompt)

        cleaned_query = clean_sql_response(raw_response)

        if cleaned_query is None:
            print("[ERROR] Failed to generate a valid SQL query.")
            return {"error": "Failed to generate a valid SQL query.", "raw_response": raw_response}

        return {"sql_query": cleaned_query}
    except Exception as e:
        print(f"[ERROR] Exception while generating SQL: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/execute-query")
async def execute_query(question: str):
    """ Generates an SQL query using Groq, validates it, and executes it. """
    print(f"[DEBUG] Executing query for question: {question}")

    try:
        # First, generate the SQL query using Groq
        response = await generate_sql(question)
        if "error" in response:
            return response

        sql_query = response["sql_query"]
        print(f"[INFO] Executing generated SQL: {sql_query}")

        # Connect to the database and execute the query
        conn = get_db_connection()
        if not conn:
            print("[ERROR] Database connection failed.")
            return {"error": "Database connection failed"}

        cursor = conn.cursor()
        cursor.execute(sql_query)

        # Fetch column names
        columns = [col[0] for col in cursor.description]

        # Fetch rows and convert them into a list of dictionaries
        rows = cursor.fetchall()
        conn.close()

        # Convert result tuples into a list of dictionaries
        result_list = [dict(zip(columns, row)) for row in rows]

        print(f"[SUCCESS] Query executed successfully:\n{sql_query}")
        return {"query": sql_query, "result": result_list}

    except Exception as e:
        print(f"[ERROR] Exception while executing query: {e}")
        raise HTTPException(status_code=400, detail=str(e))
