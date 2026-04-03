import subprocess
import os
import sys
from datetime import datetime

def run_git(args):
    try:
        result = subprocess.run(['git'] + args, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Git error: {e.stderr}")
        return None

def sync():
    print(f"--- HKJC GIT SYNC ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---")
    
    # 1. Check for changes
    status = run_git(['status', '--porcelain'])
    if not status:
        print("No changes detected. Skipping sync.")
        return

    print("Changes detected. Starting sync...")
    
    # 2. Stage changes
    run_git(['add', '.'])
    
    # 3. Commit
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    commit_msg = f"Auto-sync from VM: {timestamp}"
    run_git(['commit', '-m', commit_msg])
    print(f"Committed: {commit_msg}")
    
    # 4. Push
    print("Pushing to GitHub...")
    push_result = run_git(['push', 'origin', 'main'])
    if push_result is not None:
        print("Sync complete! Code is now on GitHub.")
    else:
        print("Push failed. Check connectivity or potential conflicts.")

if __name__ == "__main__":
    # Ensure we are in the project root
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root_dir)
    sync()
