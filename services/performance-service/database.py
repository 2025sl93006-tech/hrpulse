import os
import motor.motor_asyncio

MONGO_URL = os.getenv("MONGO_URL", "mongodb://hrpulse:hrpulse123@localhost:27017/performance_db?authSource=admin")
DB_NAME = os.getenv("MONGO_DB_NAME", "performance_db")

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
reviews_collection = db["reviews"]
