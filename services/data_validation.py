"""Shared validation gates for scraped racecard data before predictions.

Prevents the prediction pipeline from producing phantom predictions when
HKJC changes their HTML layout and scrapers silently return empty/garbage data.
"""

from typing import Any, Dict, List, Tuple


# Fields every horse entry must have (horse_id is optional — backfill data lacks it)
_REQUIRED_HORSE_FIELDS = ("saddle_number", "horse_name", "jockey", "trainer")


def validate_racecard(racecard: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate scraped racecard data before it enters the prediction pipeline.

    Returns (is_valid, issues) where issues is a list of human-readable
    problem descriptions.  When is_valid is False the caller MUST skip the
    race rather than producing a prediction from garbage data.
    """
    issues: List[str] = []

    if not isinstance(racecard, dict) or not racecard:
        return False, ["racecard is empty or not a dict"]

    horses = racecard.get("horses")
    if not isinstance(horses, list):
        issues.append("'horses' key is missing or not a list")
    elif len(horses) == 0:
        issues.append("horses list is empty — scraper likely failed to find the table")
    else:
        # Check each horse has required fields
        missing_fields: Dict[int, List[str]] = {}
        valid_horse_count = 0
        for i, h in enumerate(horses):
            if not isinstance(h, dict):
                issues.append(f"horse[{i}] is not a dict, got {type(h).__name__}")
                continue
            missing = [f for f in _REQUIRED_HORSE_FIELDS if h.get(f) in (None, "")]
            if missing:
                missing_fields[i] = missing
            else:
                valid_horse_count += 1

        if missing_fields:
            detail = "; ".join(
                f"horse[{i}] missing {flds}" for i, flds in missing_fields.items()
            )
            issues.append(f"horses missing required fields: {detail}")

        if valid_horse_count == 0:
            issues.append(
                "zero horses passed field validation — likely an HTML layout change"
            )

        # Detect "all odds are dummy 10.0" — classic sign of a scraper silently failing
        all_odds = []
        for h in horses:
            if isinstance(h, dict):
                odds = h.get("win_odds")
                if odds is not None:
                    all_odds.append(float(odds))
        if all_odds and all(o == 10.0 for o in all_odds) and len(all_odds) >= 4:
            issues.append(
                "all win_odds are exactly 10.0 — odds scraper did not capture real odds"
            )

    # Metadata sanity
    distance = racecard.get("distance")
    if distance is not None:
        try:
            if float(distance) <= 0:
                issues.append(f"distance is {distance} — must be > 0")
        except (ValueError, TypeError):
            issues.append(f"distance '{distance}' is not a valid number")

    return len(issues) == 0, issues
