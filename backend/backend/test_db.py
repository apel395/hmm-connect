from app.database.database import engine

try:
    conn = engine.connect()

    print("Connected")

    conn.close()

except Exception as e:
    print(e)