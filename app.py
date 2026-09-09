import os

from flask import Flask
import psycopg2

app = Flask(__name__)


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


@app.route("/")
def home():
    return "Flask application v2 is running on EKS!"


@app.route("/db")
def database_test():
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT version();")
        result = cursor.fetchone()

        cursor.close()
        connection.close()

        return f"PostgreSQL connection successful!<br>{result[0]}"

    except Exception as error:
        return f"PostgreSQL connection failed: {error}", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5006)
