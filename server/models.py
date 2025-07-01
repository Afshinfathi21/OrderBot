import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")

def get_db():

    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row

    return db