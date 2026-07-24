# import psycopg2
# from psycopg2.extras import RealDictCursor

# # Database connection details
# DB_CONFIG = {
#     "host": "db.gbbacytvrgcwuppzvtrs.supabase.co",
#     "port": 5432,
#     "database": "postgres",
#     "user": "postgres",
#     "password": "iVii87Tp&*4DrF9",
# }

# try:
#     # Connect to PostgreSQL
#     conn = psycopg2.connect(**DB_CONFIG)

#     # Dictionary cursor (returns rows as dictionaries)
#     cursor = conn.cursor(cursor_factory=RealDictCursor)

#     # Fetch all rows from users table
#     cursor.execute("SELECT * FROM users;")

#     rows = cursor.fetchall()

#     print(f"Total Rows: {len(rows)}\n")

#     for row in rows:
#         print(row)

# except Exception as e:
#     print("Error:", e)

# finally:
#     if 'cursor' in locals():
#         cursor.close()
#     if 'conn' in locals():
#         conn.close()

import psycopg2
from psycopg2.extras import RealDictCursor


DB_CONFIG = {
    "host": "db.gbbacytvrgcwuppzvtrs.supabase.co",
    "port": 5432,
    "database": "postgres",
    "user": "postgres",
    "password": "your_password",
}


def get_connection():

    return psycopg2.connect(
        **DB_CONFIG,
        cursor_factory=RealDictCursor
    )