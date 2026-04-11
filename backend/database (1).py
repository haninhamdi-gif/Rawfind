import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        port=8889,
        user="root",
        password="root",
        database="rawfind"
    )