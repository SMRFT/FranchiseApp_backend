"""
Mongo connection handle for the `franchise` database.

Uses MONGO_URI from the environment so you're not hardcoding credentials
into source. If your project already opens a MongoClient somewhere else
(e.g. settings.py), swap this out to reuse that client instead of
opening a second connection.
"""

import os
from pymongo import MongoClient

MONGO_URI =  os.getenv("GLOBAL_DB_HOST")

client = MongoClient(MONGO_URI)

db = client["franchise"]

location_collection = db["franchise_location_details"]