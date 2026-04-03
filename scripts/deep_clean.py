import os
import shutil
import argparse
import time
from pathlib import Path

def get_dir_size(path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size

def clean_old_files(base_dir, days=30, dry_run=False):
    print(f"\n[6/6] Checking for old data files (> {days} days)...")
    data_dir = base_dir / "data"
    if not data_dir.exists():
        return 0

    reclaimed_bytes = 0
    cutoff = time.time() - (days * 24 * 3600)
    
    # 1. Scan subdirectories
    folders = ["predictions", "racecards", "results", "odds", "weather", "logs", "archive"]
    for folder in folders:
        target = data_dir / folder
        if not target.exists(): continue
        
        print(f"  Scanning directory: {folder}...")
        for f in target.rglob("*"):
            if f.is_file() and f.stat().st_mtime < cutoff:
                size = f.stat().st_size
                print(f"    Removing: {folder}/{f.name} ({size / 1024:.1f} KB)")
                reclaimed_bytes += size
                if not dry_run:
                    try: f.unlink()
                    except: pass
    
    # 2. Scan root of data directory for racecards
    print(f"  Scanning root of data directory for racecards...")
    for f in data_dir.glob("racecard_*.json"):
        if f.stat().st_mtime < cutoff:
            size = f.stat().st_size
            print(f"    Removing: {f.name} ({size / 1024:.1f} KB)")
            reclaimed_bytes += size
            if not dry_run:
                try: f.unlink()
                except: pass

    return reclaimed_bytes

def clean_agent_artifacts(dry_run=False):
    print("\n[5/6] Checking AI Agent Artifacts...")
    user_profile = os.environ.get("USERPROFILE")
    if not user_profile:
        print("  Error: Could not find USERPROFILE environment variable.")
        return 0
    
    brain_dir = Path(user_profile) / ".gemini" / "antigravity" / "brain"
    if not brain_dir.exists():
        print(f"  Note: Artifact directory not found at {brain_dir}")
        return 0

    reclaimed_bytes = 0
    print(f"  Scanning: {brain_dir}...")
    media_extensions = [".webp", ".png", ".mp4", ".mov"]
    
    try:
        for session_dir in brain_dir.iterdir():
            if session_dir.is_dir():
                for p in session_dir.rglob("*"):
                    if p.is_file() and p.suffix.lower() in media_extensions:
                        size = p.stat().st_size
                        print(f"    Removing agent media: {session_dir.name}/{p.name} ({size / 1024 / 1024:.1f} MB)")
                        reclaimed_bytes += size
                        if not dry_run:
                            try: p.unlink()
                            except: pass
    except Exception as e:
        print(f"  Warning: Could not fully scan agent directory: {e}")

    return reclaimed_bytes

def deep_clean(target_path, dry_run=False, include_agent=False, retention_days=None):
    base_dir = Path(target_path).resolve()
    print(f"--- DEEP CLEAN TARGET: {base_dir} ---")
    if dry_run: print("[DRY RUN] No files will be deleted.")

    reclaimed_bytes = 0

    # 1. Clean Python caches and caches
    print("\n[1/6] Cleaning caches (__pycache__, .pytest_cache, etc.)...")
    cache_patterns = ["__pycache__", ".pytest_cache", ".coverage", "htmlcov", ".ipynb_checkpoints"]
    for pattern in cache_patterns:
        for p in base_dir.rglob(pattern):
            if p.is_dir():
                size = get_dir_size(p)
                print(f"  Removing: {p.relative_to(base_dir)} ({size / 1024:.1f} KB)")
                reclaimed_bytes += size
                if not dry_run:
                    try: shutil.rmtree(p)
                    except Exception as e: print(f"    Error: {e}")
            elif p.is_file():
                size = p.stat().st_size
                print(f"  Removing: {p.relative_to(base_dir)} ({size / 1024:.1f} KB)")
                reclaimed_bytes += size
                if not dry_run:
                    try: p.unlink()
                    except Exception as e: print(f"    Error: {e}")

    # 2. Clean Browser Sessions
    print("\n[2/6] Cleaning Playwright session data...")
    # It might be in data/ or root/
    search_dirs = [base_dir, base_dir / "data"]
    for d in search_dirs:
        if d.exists():
            for p in d.glob("browser_session_*"):
                if p.is_dir():
                    size = get_dir_size(p)
                    print(f"  Removing: {p.relative_to(base_dir)} ({size / 1024 / 1024:.1f} MB)")
                    reclaimed_bytes += size
                    if not dry_run:
                        try: shutil.rmtree(p)
                        except Exception as e: 
                            if "lock" in str(e).lower():
                                print(f"    Skipped (Locked by active browser)")
                            else:
                                print(f"    Error: {e}")

    # 3. Clean tmp directory
    print("\n[3/6] Clearing tmp and logs directories...")
    cleanup_dirs = [base_dir / "tmp", base_dir / "logs"]
    for target_dir in cleanup_dirs:
        if target_dir.exists():
            for p in target_dir.iterdir():
                size = get_dir_size(p) if p.is_dir() else p.stat().st_size
                print(f"  Removing: {p.relative_to(base_dir)} ({size / 1024:.1f} KB)")
                reclaimed_bytes += size
                if not dry_run:
                    try:
                        if p.is_dir(): shutil.rmtree(p)
                        else: p.unlink()
                    except Exception as e: print(f"    Error: {e}")

    # 4. Clean Debug Files
    print("\n[4/6] Removing scraper debug files...")
    debug_patterns = ["services/debug_*", "services/*.png", "services/*.html", "data/debug_*", "**/force_update.log"]
    for pattern in debug_patterns:
        for p in base_dir.glob(pattern):
            if p.is_file():
                size = p.stat().st_size
                print(f"  Removing debug file: {p.relative_to(base_dir)} ({size / 1024:.1f} KB)")
                reclaimed_bytes += size
                if not dry_run:
                    try: p.unlink()
                    except Exception as e: print(f"    Error: {e}")

    # 5. Optional Agent Artifacts
    if include_agent:
        reclaimed_bytes += clean_agent_artifacts(dry_run)
    else:
        print("\n[5/6] Skipping AI Agent Media (use --agent to include)")

    # 6. Data Retention
    if retention_days is not None:
        reclaimed_bytes += clean_old_files(base_dir, days=retention_days, dry_run=dry_run)
    else:
        print("\n[6/6] Skipping Data Retention (use --days N to include)")

    print(f"\nTotal Space Reclaimed for {base_dir.name}: {reclaimed_bytes / 1024 / 1024:.2f} MB")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-workspace Deep Clean Utility")
    parser.add_argument("--path", type=str, default=str(Path(__file__).resolve().parent.parent), help="Base directory to clean")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted")
    parser.add_argument("--agent", action="store_true", help="Clean up AI agent media recordings (.webp, .png)")
    parser.add_argument("--days", type=int, default=None, help="Delete data files older than N days")
    args = parser.parse_args()
    
    deep_clean(target_path=args.path, dry_run=args.dry_run, include_agent=args.agent, retention_days=args.days)
