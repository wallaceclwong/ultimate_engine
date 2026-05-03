"""
mempalace_narrator.py
Generates natural-language narratives from raw HKJC data (racecards and results).
Ensures MemPalace has searchable, semantic context for the 'War Room' audit.
"""
import json
import glob
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
NARR_DIR = DATA_DIR / "narratives"

def generate_narratives():
    NARR_DIR.mkdir(exist_ok=True)
    count = 0
    
    # 1. Process Predictions (Recent AI Analysis)
    pred_files = sorted(glob.glob(str(DATA_DIR / "predictions" / "*.json")))
    for f in pred_files[-200:]: # Last 200 races
        try:
            with open(f, 'r', encoding='utf-8') as jf:
                data = json.load(jf)
                race_id = data.get('race_id', 'Unknown')
                horse = data.get('horse_name', 'Unknown')
                analysis = data.get('analysis_markdown', '')
                rec = data.get('recommended_bet', 'N/A')
                
                if analysis:
                    narrative = f"""PAST ANALYSIS for {horse} in Race {race_id}:
Recommended Action: {rec}
Detailed Context:
{analysis}
"""
                    out_path = NARR_DIR / f"pred_{race_id}_{horse.replace(' ', '_')}.txt"
                    out_path.write_text(narrative, encoding='utf-8')
                    count += 1
        except:
            continue

    # 2. Process Race Results (Historical Performance)
    result_files = sorted(glob.glob(str(DATA_DIR / "results_*.json")))
    for f in result_files[-50:]:  # Last 50 meetings
        try:
            with open(f, 'r', encoding='utf-8') as jf:
                data = json.load(jf)
                date = data.get('date', 'Unknown')
                race_no = data.get('race_no', '?')
                venue = data.get('venue', 'HK')
                horses = data.get('horses', [])
                
                for h in horses:
                    name = h.get('horse_name', 'Unknown')
                    plc = h.get('plc', 'N/A')
                    comment = h.get('comment', '')
                    jockey = h.get('jockey', '')
                    trainer = h.get('trainer', '')
                    
                    if plc == '1':
                        perf = f"WON the race"
                    elif plc in ['2', '3']:
                        perf = f"PLACED ({plc})"
                    else:
                        perf = f"finished {plc}"
                        
                    narrative = f"On {date} at {venue} (Race {race_no}), {name} {perf} under {jockey} for trainer {trainer}."
                    if comment:
                        narrative += f" Performance Note: {comment}"
                        
                    out_path = NARR_DIR / f"res_{date}_{name.replace(' ', '_')}.txt"
                    out_path.write_text(narrative, encoding='utf-8')
                    count += 1
        except:
            continue

    # 3. Process Pedigree (Genetic Intelligence)
    pedigree_file = DATA_DIR / "pedigree_cache.json"
    if pedigree_file.exists():
        try:
            with open(pedigree_file, 'r', encoding='utf-8') as pf:
                pedigree_data = json.load(pf)
                for h_id, ped in pedigree_data.items():
                    if ped.get("sire") == "Unknown" and ped.get("dam") == "Unknown":
                        continue
                    
                    narrative = f"PEDIGREE FOR HORSE ID {h_id}:\n"
                    narrative += f"Sire: {ped.get('sire', 'Unknown')}\n"
                    narrative += f"Dam: {ped.get('dam', 'Unknown')}\n"
                    narrative += f"Origin: {ped.get('origin', 'Unknown')}\n"
                    narrative += f"Color: {ped.get('color', 'Unknown')}\n"
                    narrative += f"Import Type: {ped.get('import_type', 'Unknown')}\n"
                    
                    out_path = NARR_DIR / f"ped_{h_id}.txt"
                    out_path.write_text(narrative, encoding='utf-8')
                    count += 1
        except Exception as e:
            print(f"Error processing pedigree: {e}")

    # 4. Racecard Soft Data (Gear Changes & CTC Horses)
    racecard_files = sorted(glob.glob(str(DATA_DIR / "racecard_*.json")))
    for f in racecard_files[-200:]:  # Last 200 racecards
        try:
            with open(f, 'r', encoding='utf-8') as jf:
                data = json.load(jf)
            race_id  = data.get('race_id', Path(f).stem)
            date     = data.get('date', 'Unknown')[:10]
            venue    = 'ST' if 'ST' in Path(f).stem.upper() else 'HV'
            distance = data.get('distance', '?')

            for h in data.get('horses', []):
                name     = h.get('horse_name', 'Unknown')
                h_id     = h.get('horse_id', '')
                gear     = h.get('gear', '').strip()
                location = h.get('training_location', 'HK')
                allowance = h.get('weight_allowance', 0)
                jockey   = h.get('jockey', '')
                trainer  = h.get('trainer', '')

                lines = []

                # Gear narrative — only emit when gear is non-empty
                if gear:
                    lines.append(
                        f"GEAR CHANGE for {name} ({h_id}) on {date} at {venue} {distance}m: "
                        f"Equipped with {gear} under {jockey} for trainer {trainer}."
                    )

                # CTC narrative
                if location == 'CTC':
                    lines.append(
                        f"CTC HORSE: {name} ({h_id}) was trained at Conghua Training Centre "
                        f"ahead of {date} at {venue} {distance}m. Trainer: {trainer}."
                    )

                # Apprentice allowance narrative
                if allowance != 0:
                    lines.append(
                        f"APPRENTICE CLAIM: {name} ({h_id}) on {date} at {venue} — "
                        f"jockey {jockey} carried a {abs(allowance)}lb weight claim."
                    )

                if lines:
                    narrative = "\n".join(lines)
                    slug = name.replace(' ', '_')
                    out_path = NARR_DIR / f"rc_{date}_{slug}.txt"
                    out_path.write_text(narrative, encoding='utf-8')
                    count += 1
        except:
            continue

    print(f"Narrator complete. Generated {count} semantic files in {NARR_DIR}")

if __name__ == "__main__":
    generate_narratives()
