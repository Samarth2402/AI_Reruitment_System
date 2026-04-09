import json
import os

def read_json(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r") as f:
        return json.load(f)

def write_json(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)
