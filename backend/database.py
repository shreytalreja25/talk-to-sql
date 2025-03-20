import pyodbc # type: ignore

def get_db_connection():
    try:
        conn = pyodbc.connect(
            "DRIVER={SQL Server};"
            "SERVER=LAPTOP-5PMRBLQK\\SQLEXPRESS01;"
            "DATABASE=SchoolDB;"  # Change this to your actual database name
            "Trusted_Connection=yes;"
        )
        return conn
    except Exception as e:
        print(f"Database connection failed: {e}")
        return None
