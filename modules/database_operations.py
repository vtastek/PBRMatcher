import os
import json

from modules.constants import DB_FILE

def load_database():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            db = json.load(f)
        for texture_path, texture_data in db.get("textures", {}).items():
            texture_data.setdefault("selected_thumbnails", [])
        return db
    return {"textures": {}}

def save_database(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=4)