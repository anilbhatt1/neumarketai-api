import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
print(f"os.getenv('DB_NAME') : {os.getenv('DB_NAME')}")

# Connect to PostgreSQL using psycopg2
def get_db_connection():
    try:
        connection = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT')
        )
        print(f"Successfully connected to DB - {os.getenv('DB_HOST')}")
        return connection
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return None
    
conn = get_db_connection()