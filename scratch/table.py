import json
from pathlib import Path

def print_table():
    path = Path('data/racecard_20260415_R9.json')
    if not path.exists():
        print("Racecard 9 not found, maybe Happy Valley only has 8 or 9 races.")
        return
        
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    print("| Horse No | Horse Name | Draw | Weight | Jockey | Trainer |")
    print("| --- | --- | --- | --- | --- | --- |")
    for r in data.get('runners', []):
        no = r.get('horse_number', '-')
        name = r.get('horse_name', '-')
        draw = r.get('draw', '-')
        weight = r.get('weight', '-')
        jockey = r.get('jockey', '-')
        trainer = r.get('trainer', '-')
        print(f"| {no} | {name} | {draw} | {weight} | {jockey} | {trainer} |")

if __name__ == '__main__':
    print_table()
