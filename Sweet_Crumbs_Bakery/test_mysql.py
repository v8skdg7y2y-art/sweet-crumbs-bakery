import mysql.connector

connection = mysql.connector.connect(
    host="127.0.0.1",
    user="root",
    password="",
    database="sweet_crumbs"
)

print("Connected to MySQL successfully!")

connection.close()