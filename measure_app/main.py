from flask import Flask, request, jsonify
import os
import time
import threading
import mysql.connector

from dotenv import load_dotenv

load_dotenv()


app = Flask(__name__)


def setup_database_and_table():
    """
    Connects to MySQL, creates a database if it doesn't exist,
    and then creates a 'students' table if it doesn't exist.
    """
    db_host = os.getenv("DB_HOST")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_name = "student_db"

    if not all([db_host, db_user, db_password]):
        print("Error: Missing required environment variables in .env file.")
        return

    connection = None
    try:
        connection = mysql.connector.connect(
            host=db_host, user=db_user, password=db_password
        )
        cursor = connection.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
        print(f"Database '{db_name}' is ready.")
        connection.database = db_name

        table_name = "students"
        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS `{table_name}` (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE
        ) ENGINE=InnoDB;
        """
        cursor.execute(create_table_query)
        print(f"Table '{table_name}' is ready.")
        cursor.close()
    except mysql.connector.Error as err:
        print(f"An error occurred during setup: {err}")
    finally:
        if connection and connection.is_connected():
            connection.close()


def insert_sample_data():
    """Connects to the database and inserts 20 sample students if the table is empty."""

    db_host = os.getenv("DB_HOST")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_name = "student_db"

    connection = None
    try:
        # Connect to the specific database
        connection = mysql.connector.connect(
            host=db_host, user=db_user, password=db_password, database=db_name
        )
        cursor = connection.cursor()

        # --- Check if the table already has data ---
        cursor.execute("SELECT COUNT(*) FROM students")
        (number_of_rows,) = cursor.fetchone()

        if number_of_rows > 0:
            print(
                "Table 'students' already contains data. Skipping sample data insertion."
            )
            return  # Exit the function early

        # --- Prepare the sample data if the table is empty ---
        print("Table is empty. Inserting sample data...")
        students_to_add = []
        for i in range(1, 21):
            name = f"student{i}"
            email = f"student{i}@gmail.com"
            students_to_add.append((name, email))

        # --- The SQL query to insert data ---
        insert_query = "INSERT INTO students (name, email) VALUES (%s, %s)"

        # Use executemany for efficient batch insertion
        cursor.executemany(insert_query, students_to_add)

        # --- IMPORTANT: Commit the transaction to save changes ---
        connection.commit()

        print(f"Successfully inserted {cursor.rowcount} rows of sample data.")

    except mysql.connector.Error as err:
        print(f"An error occurred while inserting data: {err}")

    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection is closed.")


def background_query_task(duration):
    """Continuously queries the students table for a given duration using MySQL."""

    db_host = os.getenv("DB_HOST")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_name = "student_db"

    print(f"\n--- Starting background query task for {duration} seconds ---")
    end_time = time.time() + duration
    query_count = 0

    while time.time() < end_time:
        connection = None
        cursor = None
        try:
            connection = mysql.connector.connect(
                host=db_host, user=db_user, password=db_password, database=db_name
            )
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM students")
            _ = cursor.fetchall()  # Fetch results but don't use them
            query_count += 1
        except mysql.connector.Error as err:
            print(f"Query failed during background task: {err}")
            time.sleep(1)  # Wait a bit before retrying if there's an error
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    print(f"--- Finished background task. Executed {query_count} queries. ---")


@app.route("/list-students", methods=["GET"])
def list_students():
    try:
        duration = float(request.args.get("duration", 5))
    except:
        duration = 5.0

    thread = threading.Thread(target=background_query_task, args=(duration,))
    thread.daemon = True
    thread.start()

    return jsonify({"status": "started", "duration_sec": duration}), 200


@app.route("/processing_time/<int:student_id>", methods=["GET"])
def check_student(student_id):
    """
    Checks for a student by ID, measures the query time, and returns the result.
    """
    db_host = os.getenv("DB_HOST")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_name = "student_db"

    student = None
    connection = None
    cursor = None

    start_time = time.perf_counter()  # Start high-resolution timer

    try:
        connection = mysql.connector.connect(
            host=db_host, user=db_user, password=db_password, database=db_name
        )
        cursor = connection.cursor()
        # Use %s for parameter substitution in mysql-connector
        cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
        student = cursor.fetchone()
    except mysql.connector.Error as err:
        print(f"Error checking student: {err}")
        return jsonify({"error": "Database query failed."}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

    end_time = time.perf_counter()
    duration = end_time - start_time

    response_data = {
        "start_time_sec": start_time,
        "end_time_sec": end_time,
        "processing_time_sec": duration,
    }

    if student:
        return jsonify(response_data), 200
    else:
        return jsonify(response_data), 404


if __name__ == "__main__":
    print("--- Running Database Setup ---")
    setup_database_and_table()
    print("\n--- Seeding Database with Sample Data ---")
    insert_sample_data()
    app.run(host="0.0.0.0", port=5000)
