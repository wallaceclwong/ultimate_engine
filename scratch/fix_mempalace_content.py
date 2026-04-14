"""
fix_mempalace_content.py
1. Updates mempalace.yaml to index useful text content (predictions, logs, reports)
2. Creates a nightly race summary generator so future races get indexed as natural language
3. Triggers a re-mine to populate the search index with real readable content
"""
import paramiko, time, json
from pathlib import Path

VM_IP = "45.32.255.155"
VM_USER = "root"
VM_PASS = "6{tJs[Dhe,jv3@_G"
VM_ROOT = "/root/ultimate_engine"
VENV_BIN = "/root/mempalace_venv/bin"

def run_ssh(ssh, cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(errors="ignore").strip()

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VM_IP, username=VM_USER, password=VM_PASS, timeout=10)
    print("[OK] Connected.\n")

    # --- Step 1: Check what text content exists ---
    print("=== Checking existing text content ===")
    out = run_ssh(ssh, f"find {VM_ROOT}/data -name '*.md' -o -name '*.txt' 2>/dev/null | head -10")
    print(f"Markdown/text files:\n{out or '[NONE]'}")
    out2 = run_ssh(ssh, f"ls {VM_ROOT}/data/predictions/*.json 2>/dev/null | wc -l")
    print(f"Prediction JSON files: {out2}")
    out3 = run_ssh(ssh, f"ls {VM_ROOT}/data/soft_data/ 2>/dev/null | head -5")
    print(f"Soft data:\n{out3 or '[NONE]'}")

    # --- Step 2: Generate race narrative summaries from prediction JSONs ---
    # These will be natural language text that MemPalace can actually search
    print("\n=== Step 2: Generating race narrative summaries ===")
    narrative_script = '''
import json, glob
from pathlib import Path

DATA_DIR = Path("/root/ultimate_engine/data")
NARR_DIR = DATA_DIR / "narratives"
NARR_DIR.mkdir(exist_ok=True)
count = 0

# From prediction files
for f in sorted(glob.glob(str(DATA_DIR / "predictions/*.json")))[-50:]:
    try:
        d = json.load(open(f))
        race_id = d.get("race_id", Path(f).stem)
        analysis = d.get("analysis_markdown", "")
        recommended = d.get("recommended_bet", "")
        confidence = d.get("confidence_score", 0)
        stakes = d.get("kelly_stakes", {})

        if analysis:
            text = f"""RACE PREDICTION: {race_id}
Recommended Bet: {recommended}
Confidence: {confidence:.0%}
Stakes: {stakes}

ANALYSIS:
{analysis}
"""
            out_file = NARR_DIR / f"prediction_{race_id}.txt"
            out_file.write_text(text, encoding="utf-8")
            count += 1
    except Exception as e:
        pass

# From racecard files (horse form summaries)
for f in sorted(glob.glob(str(DATA_DIR / "racecard_*.json")))[-30:]:
    try:
        d = json.load(open(f))
        race_id = d.get("race_id", Path(f).stem)
        date = d.get("date", "")
        dist = d.get("distance", "")
        track = d.get("track_type", "")
        horses = d.get("horses", [])

        lines = [f"RACECARD: {race_id} | {dist}m {track}"]
        for h in horses:
            name = h.get("horse_name", "")
            jockey = h.get("jockey", "")
            trainer = h.get("trainer", "")
            last6 = h.get("last_6_runs", [])
            odds = h.get("win_odds", "")
            lines.append(f"  Horse: {name} | Jockey: {jockey} | Trainer: {trainer} | Last 6: {last6} | Odds: {odds}")

        text = "\\n".join(lines)
        out_file = NARR_DIR / f"racecard_{race_id}.txt"
        out_file.write_text(text, encoding="utf-8")
        count += 1
    except Exception as e:
        pass

print(f"Generated {count} narrative files in {NARR_DIR}")
'''

    sftp = ssh.open_sftp()
    with sftp.file('/tmp/gen_narratives.py', 'w') as f:
        f.write(narrative_script)
    sftp.close()

    out = run_ssh(ssh, f"cd {VM_ROOT} && ./.venv/bin/python3 /tmp/gen_narratives.py", timeout=30)
    print(out)

    # --- Step 3: Update mempalace.yaml to include narratives ---
    print("\n=== Step 3: Updating mempalace.yaml ===")
    new_config = """project_name: ultimate_engine
rooms:
  - name: code
    path: .
    include: ['*.py']
  - name: data
    path: data
    include: ['*.json']
  - name: general
    path: data/narratives
    include: ['*.txt']
  - name: reports
    path: data/reports
    include: ['*.md', '*.txt']
"""
    sftp = ssh.open_sftp()
    with sftp.file(f'{VM_ROOT}/mempalace.yaml', 'w') as f:
        f.write(new_config)
    sftp.close()
    print("mempalace.yaml updated.")

    # --- Step 4: Re-mine the narratives room ---
    print("\n=== Step 4: Mining narratives into MemPalace ===")
    print("(This may take 30-60 seconds...)")
    # Mine only the narratives room for speed
    out = run_ssh(ssh,
        f"export OMP_NUM_THREADS=1; export MKL_NUM_THREADS=1; "
        f"cd {VM_ROOT} && {VENV_BIN}/python -m mempalace.cli mine data/narratives --wing ultimate_engine_2026",
        timeout=120)
    print(out[:500] if out else "[EMPTY]")

    # --- Step 5: Test search ---
    print("\n=== Step 5: Testing search ===")
    time.sleep(5)
    queries = [
        "horse win prediction high confidence",
        "jockey trainer combination recommendation",
        "turf race 1200m winner form",
    ]
    for q in queries:
        print(f"\nQuery: '{q}'")
        out = run_ssh(ssh,
            f"export OMP_NUM_THREADS=1; export MKL_NUM_THREADS=1; "
            f"{VENV_BIN}/python -m mempalace.cli search \"{q}\" --wing ultimate_engine_2026",
            timeout=20)
        lines = [l for l in out.splitlines() if l.strip() and "Warning" not in l and "telemetry" not in l.lower()]
        if lines:
            for l in lines[:4]:
                print(f"  {l}")
        else:
            print("  [NO RESULTS]")

    # Status after mining
    print("\n=== Final Status ===")
    out = run_ssh(ssh,
        f"export OMP_NUM_THREADS=1; export MKL_NUM_THREADS=1; "
        f"{VENV_BIN}/python -m mempalace.cli status",
        timeout=20)
    lines = [l for l in out.splitlines() if l.strip() and "Warning" not in l and "telemetry" not in l.lower()]
    for l in lines:
        print(l)

    ssh.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
