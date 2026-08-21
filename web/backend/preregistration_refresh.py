from app.database import SessionLocal
from app.preregistration.collector import collect_and_store

if __name__ == "__main__":
    db = SessionLocal()
    try:
        print(collect_and_store(db))
    finally:
        db.close()
