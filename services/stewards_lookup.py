"""
Stewards Report Historical Lookup Service
=========================================
Scans data/results/results_*.json for a horse's past stewards incidents
and provides risk profiles for the War Room audit.
"""
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger


def _norm(name: str) -> str:
    """Normalize horse name: lowercase, strip parenthetical code like (K284), trim."""
    return re.sub(r"\s*\([A-Z]\d+\)", "", name).strip().lower()


class StewardsLookup:
    """Indexes historical stewards reports from disk and provides per-horse lookups."""

    def __init__(self, results_dir: Path = None):
        self.results_dir = results_dir or Path(__file__).parent.parent / "data" / "results"
        self._index: Dict[str, List[dict]] = {}  # norm_name -> [{date, race_id, incident, ...}]
        self._built = False

    def _build_index(self):
        """Scan all results JSON files and build an in-memory horse->incidents index."""
        if self._built:
            return
        if not self.results_dir.exists():
            logger.warning(f"Results directory not found: {self.results_dir}")
            self._built = True
            return

        for fp in sorted(self.results_dir.glob("results_*.json")):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            race_id = data.get("race_id", fp.stem)
            date_str = race_id[:10] if len(race_id) >= 10 else ""
            results = data.get("results", [])
            incidents = {inc["horse_no"]: inc["incident"] for inc in data.get("incidents", [])}

            for r in results:
                h_no = r.get("horse_no", "")
                h_name = r.get("horse", r.get("horse_name", ""))
                if not h_name:
                    continue
                key = _norm(h_name)
                incident_text = incidents.get(h_no, "")
                entry = {
                    "date": date_str,
                    "race_id": race_id,
                    "horse_no": h_no,
                    "horse_name": h_name.strip(),
                    "incident": incident_text,
                    "finish": r.get("plc", ""),
                    "lbw": r.get("lbw", ""),
                }
                self._index.setdefault(key, []).append(entry)
        self._built = True
        logger.info(f"Stewards index built: {len(self._index)} horses from results files")

    def get_recent_incidents(
        self, horse_name: str, lookback_days: int = 90, max_entries: int = 3
    ) -> List[dict]:
        """Return the most recent stewards incidents for a horse by name."""
        self._build_index()
        key = _norm(horse_name)
        entries = self._index.get(key, [])
        if not entries:
            # Try partial match (e.g. just the name part without the code)
            for idx_key, idx_entries in self._index.items():
                if key in idx_key or idx_key in key:
                    entries = idx_entries
                    break

        if not entries:
            return []

        cutoff = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        recent = [e for e in entries if e["date"] >= cutoff]
        recent.sort(key=lambda e: e["date"], reverse=True)
        return recent[:max_entries]

    def get_horse_risk_profile(self, horse_name: str) -> dict:
        """
        Return a risk profile for the War Room.
        Includes recent incidents and a red-flag analysis via StewardsAnalyzer.
        """
        recent = self.get_recent_incidents(horse_name)
        if not recent:
            return {"horse_name": horse_name, "has_history": False, "recent_incidents": [], "risk": "clean"}

        # Use stewards_analyzer if available for red-flag scoring
        flags = []
        try:
            from services.stewards_analyzer import get_stewards_analyzer
            analyzer = get_stewards_analyzer()
            for entry in recent:
                if entry["incident"]:
                    analysis = analyzer.analyze_horse_report(entry["horse_no"], entry["incident"])
                    if analysis["red_flags"]:
                        for f in analysis["red_flags"]:
                            flags.append({
                                "date": entry["date"],
                                "race": entry["race_id"],
                                "finish": entry["finish"],
                                "category": f["category"],
                                "severity": f["severity"],
                            })
        except Exception:
            pass

        if flags:
            if any(f["severity"] == "critical" for f in flags):
                risk = "high"
            elif any(f["severity"] == "high" for f in flags):
                risk = "moderate"
            else:
                risk = "low"
        else:
            risk = "clean"

        return {
            "horse_name": horse_name,
            "has_history": True,
            "recent_incidents": recent,
            "red_flags": flags,
            "risk": risk,
        }


# Singleton
_stewards_lookup: Optional[StewardsLookup] = None


def get_stewards_lookup() -> StewardsLookup:
    global _stewards_lookup
    if _stewards_lookup is None:
        _stewards_lookup = StewardsLookup()
    return _stewards_lookup
