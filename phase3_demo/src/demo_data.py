import json


def load_documents(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)
