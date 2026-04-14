import os
from pathlib import Path

def read_utf16(file_path):
    try:
        with open(file_path, 'r', encoding='utf-16') as f:
            return f.read(2000) # Read first 2000 chars
    except Exception as e:
        return f"Error: {e}"

files = ["prep_april12.log", "r1_r8_retrospective.log", "cloud_status.txt"]
output = ""
for f in files:
    output += f"\n--- {f} ---\n"
    output += read_utf16(f)
    output += "\n"

print(output)
