
import os

files = [
    r"c:\Users\n.amtage\ots\Dockerfile",
    r"c:\Users\n.amtage\ots\docker-compose.yml",
    r"c:\Users\n.amtage\ots\server.py",
    r"c:\Users\n.amtage\ots\secrets_store.py"
]

for f in files:
    print(f"--- START {f} ---")
    try:
        with open(f, 'r', encoding='utf-8') as file:
            print(file.read())
    except Exception as e:
        print(f"Error reading {f}: {e}")
    print(f"--- END {f} ---")
