import subprocess
import os
import sys
from pathlib import Path

# Add project root to path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from services.memory_service import MemoryService

def deepclean_vm():
    """Deep clean the Vultr VM via SSH"""
    mem = MemoryService()
    
    print("\n=== DEEP CLEANING VULTR VM ===")
    print("=" * 60)
    
    commands = [
        # Clean old odds snapshots (keep last 7 days)
        ("find /root/ultimate_engine/data/odds -name '*.json' -mtime +7 -delete", "Clean old odds snapshots (7+ days)"),
        
        # Clean old prediction files (keep last 30 days)
        ("find /root/ultimate_engine/data/predictions -name '*.json' -mtime +30 -delete", "Clean old predictions (30+ days)"),
        
        # Clean old result files (keep last 90 days)
        ("find /root/ultimate_engine/data/results -name '*.json' -mtime +90 -delete", "Clean old results (90+ days)"),
        
        # Clean browser sessions
        ("rm -rf /root/ultimate_engine/data/browser_session_check/*", "Clean browser session cache"),
        ("rm -rf /root/ultimate_engine/data/browser_session_ingest/*", "Clean browser ingest cache"),
        
        # Clean temporary files
        ("rm -rf /root/ultimate_engine/tmp/*", "Clean tmp directory"),
        ("rm -rf /root/ultimate_engine/scratch/*", "Clean scratch directory"),
        
        # Clean log files
        ("find /root/ultimate_engine -name '*.log' -mtime +7 -delete", "Clean old log files (7+ days)"),
        
        # Clear Python cache
        ("find /root/ultimate_engine -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true", "Clear Python cache"),
        ("find /root/ultimate_engine -name '*.pyc' -delete", "Clear .pyc files"),
        
        # Clean processed parquet files (keep last 30 days)
        ("find /root/ultimate_engine/data/processed -name '*.parquet' -mtime +30 -delete", "Clean old processed features (30+ days)"),
        
        # Clear AI sentiment cache (rebuild on next run)
        ("rm -f /root/ultimate_engine/data/ai_sentiment_cache.parquet", "Clean AI sentiment cache"),
        
        # Clear weather cache
        ("rm -rf /root/ultimate_engine/data/weather/*", "Clean weather cache"),
        
        # Clean up old racecards (keep last 60 days)
        ("find /root/ultimate_engine/data -name 'racecard_*.json' -mtime +60 -delete", "Clean old racecards (60+ days)"),
        
        # Check disk space
        ("df -h /root", "Check disk space after cleanup"),
    ]
    
    results = []
    for cmd, description in commands:
        print(f"\n{description}...")
        try:
            output = mem._execute_cmd(cmd)
            if output:
                print(output)
            print(f"✓ Done")
            results.append((description, True))
        except Exception as e:
            print(f"✗ Failed: {e}")
            results.append((description, False))
    
    # Optional: Reindex Mempalace for fresh index
    print("\n=== OPTIONAL: Reindex Mempalace? ===")
    print("This will rebuild the vector index (takes 5-10 minutes)")
    print("Run manually if needed: mem.reindex_palace()")
    
    print("\n" + "=" * 60)
    print("=== SUMMARY ===")
    for desc, success in results:
        status = "✓" if success else "✗"
        print(f"{status} {desc}")
    
    print("\nDeep clean complete!")

if __name__ == "__main__":
    deepclean_vm()
