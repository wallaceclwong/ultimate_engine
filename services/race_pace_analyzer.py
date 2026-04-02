"""
Race Pace Analyzer Service
Analyzes pace scenarios and adjusts predictions based on horses' pace preferences
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config

class PaceScenario(Enum):
    """Different race pace scenarios"""
    SLOW_PACE = "slow"  # Slow early, sprint finish
    MODERATE_PACE = "moderate"  # Even pace throughout
    FAST_PACE = "fast"  # Fast early, survival test
    SPEED_DUEL = "duel"  # Multiple leaders fighting for pace

@dataclass
class HorsePaceProfile:
    """Horse's pace characteristics"""
    horse_no: str
    early_speed_rating: float  # 0-1, higher = better early speed
    late_speed_rating: float   # 0-1, higher = better late kick
    pace_preference: str  # 'front_runner', 'stalker', 'closer', 'versatile'
    ideal_pace: PaceScenario
    sectional_data: Dict[str, List[float]] = field(default_factory=dict)

@dataclass
class RacePaceAnalysis:
    """Analysis of race pace scenario"""
    race_id: str
    predicted_pace: PaceScenario
    pace_confidence: float
    front_runners: List[str]  # Horses likely to lead
    stalkers: List[str]      # Horses likely to sit behind leaders
    closers: List[str]       # Horses likely to come from behind
    pace_victims: List[str]   # Horses likely to be compromised by pace
    pace_beneficiaries: List[str]  # Horses likely to benefit from pace

class RacePaceAnalyzer:
    """
    Analyzes race pace scenarios and horse pace preferences.
    
    Uses sectional times and position data to:
    1. Predict likely race pace scenario
    2. Identify horses suited/not suited to that pace
    3. Adjust probabilities based on pace match
    """
    
    def __init__(self):
        self.analytical_dir = Path("data/analytical")
        self.results_dir = Path("data/results")
        
        # Pace thresholds
        self.fast_pace_threshold = 11.5  # Sectional time in seconds (fast = < 11.5s for 200m)
        self.slow_pace_threshold = 12.5  # Slow = > 12.5s for 200m
        
        # Horse pace classification thresholds
        self.front_runner_threshold = 0.7  # Early speed rating > 0.7
        self.closer_threshold = 0.7        # Late speed rating > 0.7
        
        logger.info("Race Pace Analyzer initialized")
    
    def load_analytical_data(self, race_id: str) -> Optional[Dict]:
        """Load analytical data for a race"""
        file_path = self.analytical_dir / f"analytical_{race_id}.json"
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.debug(f"Error loading analytical data for {race_id}: {e}")
            return None
    
    def load_results_data(self, race_id: str) -> Optional[Dict]:
        """Load results data for pace pattern analysis"""
        file_path = self.results_dir / f"results_{race_id}.json"
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.debug(f"Error loading results for {race_id}: {e}")
            return None
    
    def analyze_horse_pace_profile(self, horse_no: str, 
                                   historical_data: List[Dict]) -> HorsePaceProfile:
        """
        Analyze a horse's pace profile from historical sectional data.
        
        Args:
            horse_no: Horse number
            historical_data: List of historical race data with sectionals
            
        Returns:
            HorsePaceProfile with pace characteristics
        """
        if not historical_data:
            # Default profile if no data
            return HorsePaceProfile(
                horse_no=horse_no,
                early_speed_rating=0.5,
                late_speed_rating=0.5,
                pace_preference='versatile',
                ideal_pace=PaceScenario.MODERATE_PACE
            )
        
        early_speeds = []
        late_speeds = []
        
        for race_data in historical_data:
            sectionals = race_data.get('sectionals', {})
            
            # Early speed (first 400-600m)
            early_sectionals = sectionals.get('early', [])
            if early_sectionals:
                avg_early = sum(early_sectionals) / len(early_sectionals)
                early_speeds.append(avg_early)
            
            # Late speed (final 400-600m)
            late_sectionals = sectionals.get('late', [])
            if late_sectionals:
                avg_late = sum(late_sectionals) / len(late_sectionals)
                late_speeds.append(avg_late)
        
        # Calculate ratings (lower sectional time = higher rating)
        avg_early = sum(early_speeds) / len(early_speeds) if early_speeds else 12.0
        avg_late = sum(late_speeds) / len(late_speeds) if late_speeds else 12.0
        
        # Convert to 0-1 ratings (12.0s = 0.5, 11.0s = 1.0, 13.0s = 0.0)
        early_rating = max(0, min(1, (13.0 - avg_early) / 2.0))
        late_rating = max(0, min(1, (13.0 - avg_late) / 2.0))
        
        # Determine pace preference
        if early_rating > self.front_runner_threshold and late_rating < 0.5:
            preference = 'front_runner'
            ideal_pace = PaceScenario.MODERATE_PACE
        elif late_rating > self.closer_threshold and early_rating < 0.5:
            preference = 'closer'
            ideal_pace = PaceScenario.FAST_PACE
        elif early_rating > 0.6 and late_rating > 0.6:
            preference = 'versatile'
            ideal_pace = PaceScenario.MODERATE_PACE
        else:
            preference = 'stalker'
            ideal_pace = PaceScenario.MODERATE_PACE
        
        return HorsePaceProfile(
            horse_no=horse_no,
            early_speed_rating=early_rating,
            late_speed_rating=late_rating,
            pace_preference=preference,
            ideal_pace=ideal_pace
        )
    
    def predict_race_pace(self, race_id: str, horse_profiles: Dict[str, HorsePaceProfile],
                         analytical_data: Optional[Dict] = None) -> RacePaceAnalysis:
        """
        Predict the likely pace scenario for a race.
        
        Args:
            race_id: Race identifier
            horse_profiles: Dict of horse_no -> HorsePaceProfile
            analytical_data: Optional analytical data with sectionals
            
        Returns:
            RacePaceAnalysis with pace prediction and horse classifications
        """
        # Count front runners and closers
        front_runners = []
        stalkers = []
        closers = []
        
        for horse_no, profile in horse_profiles.items():
            if profile.pace_preference == 'front_runner':
                front_runners.append(horse_no)
            elif profile.pace_preference == 'closer':
                closers.append(horse_no)
            else:
                stalkers.append(horse_no)
        
        # Determine pace scenario
        num_leaders = len(front_runners)
        num_closers = len(closers)
        
        if num_leaders >= 3:
            predicted_pace = PaceScenario.SPEED_DUEL
            pace_confidence = 0.8
        elif num_leaders >= 2:
            predicted_pace = PaceScenario.FAST_PACE
            pace_confidence = 0.7
        elif num_closers >= 4 and num_leaders <= 1:
            predicted_pace = PaceScenario.SLOW_PACE
            pace_confidence = 0.6
        else:
            predicted_pace = PaceScenario.MODERATE_PACE
            pace_confidence = 0.5
        
        # Identify pace victims and beneficiaries
        pace_victims = []
        pace_beneficiaries = []
        
        if predicted_pace == PaceScenario.FAST_PACE or predicted_pace == PaceScenario.SPEED_DUEL:
            # Fast pace hurts front runners who can't sustain it
            pace_victims = [h for h in front_runners 
                          if horse_profiles[h].early_speed_rating < 0.8]
            # Benefits closers with strong late speed
            pace_beneficiaries = [h for h in closers 
                                 if horse_profiles[h].late_speed_rating > 0.7]
        
        elif predicted_pace == PaceScenario.SLOW_PACE:
            # Slow pace hurts closers who need fast pace to run into
            pace_victims = [h for h in closers 
                           if horse_profiles[h].late_speed_rating < 0.8]
            # Benefits front runners who can control slow pace
            pace_beneficiaries = [h for h in front_runners 
                                 if horse_profiles[h].early_speed_rating > 0.7]
        
        return RacePaceAnalysis(
            race_id=race_id,
            predicted_pace=predicted_pace,
            pace_confidence=pace_confidence,
            front_runners=front_runners,
            stalkers=stalkers,
            closers=closers,
            pace_victims=pace_victims,
            pace_beneficiaries=pace_beneficiaries
        )
    
    def adjust_probabilities_for_pace(self, probabilities: Dict[str, float],
                                     pace_analysis: RacePaceAnalysis,
                                     horse_profiles: Dict[str, HorsePaceProfile]) -> Dict[str, float]:
        """
        Adjust probabilities based on pace match.
        
        Args:
            probabilities: Original probabilities
            pace_analysis: Race pace analysis
            horse_profiles: Horse pace profiles
            
        Returns:
            Adjusted probabilities
        """
        adjusted = probabilities.copy()
        
        logger.info(f"[PACE] Adjusting for {pace_analysis.predicted_pace.value} pace")
        logger.info(f"[PACE] Victims: {pace_analysis.pace_victims}")
        logger.info(f"[PACE] Beneficiaries: {pace_analysis.pace_beneficiaries}")
        
        # Reduce probabilities for pace victims
        for horse_no in pace_analysis.pace_victims:
            if horse_no in adjusted:
                # Reduce by 15-25% depending on how badly suited
                reduction = 0.15
                adjusted[horse_no] *= (1 - reduction)
                logger.info(f"[PACE] Horse #{horse_no}: -15% (pace victim)")
        
        # Boost probabilities for pace beneficiaries
        for horse_no in pace_analysis.pace_beneficiaries:
            if horse_no in adjusted:
                # Boost by 10-20% depending on how well suited
                boost = 0.15
                adjusted[horse_no] *= (1 + boost)
                logger.info(f"[PACE] Horse #{horse_no}: +15% (pace beneficiary)")
        
        # Renormalize
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {h: p / total for h, p in adjusted.items()}
        
        return adjusted
    
    def analyze_race(self, race_id: str, horse_list: List[str]) -> Tuple[RacePaceAnalysis, Dict[str, HorsePaceProfile]]:
        """
        Full race pace analysis.
        
        Args:
            race_id: Race identifier
            horse_list: List of horse numbers in the race
            
        Returns:
            Tuple of (RacePaceAnalysis, Dict of horse profiles)
        """
        # Load analytical data
        analytical_data = self.load_analytical_data(race_id)
        results_data = self.load_results_data(race_id)
        
        # Build horse profiles (would need historical data in production)
        # For now, use default profiles or simple heuristics
        profiles = {}
        for horse_no in horse_list:
            # In production, this would query horse database for historical sectionals
            profiles[horse_no] = self._estimate_profile_from_available_data(
                horse_no, analytical_data, results_data
            )
        
        # Predict race pace
        pace_analysis = self.predict_race_pace(race_id, profiles, analytical_data)
        
        return pace_analysis, profiles
    
    def _estimate_profile_from_available_data(self, horse_no: str,
                                              analytical_data: Optional[Dict],
                                              results_data: Optional[Dict]) -> HorsePaceProfile:
        """
        Estimate horse pace profile from available race data.
        This is a simplified version - production would use historical database.
        """
        # Default neutral profile
        profile = HorsePaceProfile(
            horse_no=horse_no,
            early_speed_rating=0.5,
            late_speed_rating=0.5,
            pace_preference='versatile',
            ideal_pace=PaceScenario.MODERATE_PACE
        )
        
        # Try to extract from analytical data if available
        if analytical_data:
            for horse_data in analytical_data.get('horse_analytics', []):
                if str(horse_data.get('horse_no')) == str(horse_no):
                    # Parse sectional positions if available
                    sec_pos = horse_data.get('sectional_pos', '')
                    if sec_pos:
                        positions = [int(p) for p in sec_pos.split() if p.isdigit()]
                        if len(positions) >= 2:
                            # If early position is 1-3, likely front runner
                            if positions[0] <= 3:
                                profile.early_speed_rating = 0.7
                                profile.pace_preference = 'front_runner'
                            # If improving position in late stages, likely closer
                            if positions[-1] < positions[0]:
                                profile.late_speed_rating = 0.7
                                if profile.pace_preference == 'versatile':
                                    profile.pace_preference = 'closer'
                    break
        
        return profile
    
    def get_pace_summary(self, pace_analysis: RacePaceAnalysis) -> str:
        """Get a readable summary of pace analysis"""
        lines = [
            f"Predicted Pace: {pace_analysis.predicted_pace.value.upper()}",
            f"Confidence: {pace_analysis.pace_confidence:.0%}",
            f"",
            f"Front Runners: {', '.join(pace_analysis.front_runners) if pace_analysis.front_runners else 'None'}",
            f"Stalkers: {', '.join(pace_analysis.stalkers) if pace_analysis.stalkers else 'None'}",
            f"Closers: {', '.join(pace_analysis.closers) if pace_analysis.closers else 'None'}",
            f"",
            f"Pace Victims (Avoid): {', '.join(pace_analysis.pace_victims) if pace_analysis.pace_victims else 'None'}",
            f"Pace Beneficiaries (Target): {', '.join(pace_analysis.pace_beneficiaries) if pace_analysis.pace_beneficiaries else 'None'}"
        ]
        return "\n".join(lines)

# Singleton instance
_pace_analyzer = None

def get_race_pace_analyzer() -> RacePaceAnalyzer:
    """Get the global race pace analyzer instance"""
    global _pace_analyzer
    if _pace_analyzer is None:
        _pace_analyzer = RacePaceAnalyzer()
    return _pace_analyzer

# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Race Pace Analyzer")
    parser.add_argument("--race-id", required=True, help="Race ID (e.g., 2026-04-01_ST_R5)")
    parser.add_argument("--horses", required=True, help="Comma-separated horse numbers")
    
    args = parser.parse_args()
    
    analyzer = get_race_pace_analyzer()
    horse_list = args.horses.split(',')
    
    pace_analysis, profiles = analyzer.analyze_race(args.race_id, horse_list)
    
    print("=" * 60)
    print(f"Race Pace Analysis: {args.race_id}")
    print("=" * 60)
    print(analyzer.get_pace_summary(pace_analysis))
    print("\nHorse Profiles:")
    for horse_no, profile in profiles.items():
        print(f"  Horse #{horse_no}: {profile.pace_preference} (Early: {profile.early_speed_rating:.1f}, Late: {profile.late_speed_rating:.1f})")
