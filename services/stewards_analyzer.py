"""
Stewards Report Analyzer Service
Integrates red flag detection into the prediction engine
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from loguru import logger

class StewardsAnalyzer:
    """Analyzes stewards reports for red flags that indicate poor future performance"""
    
    def __init__(self, rules_file: Optional[Path] = None):
        self.rules_file = rules_file or Path("data/stewards_red_flags.json")
        self.red_flag_rules = self._load_rules()
        self.cache = {}  # Cache for analyzed reports
    
    def _load_rules(self) -> List[Dict]:
        """Load red flag rules from analysis results"""
        try:
            with open(self.rules_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('rules', [])
        except Exception as e:
            logger.warning(f"Could not load stewards rules from {self.rules_file}: {e}")
            return []
    
    def analyze_horse_report(self, horse_no: str, stewards_report: str, previous_report: str = None) -> Dict:
        """
        Analyze a horse's stewards report for red flags
        
        Args:
            horse_no: Horse number
            stewards_report: Current stewards report text
            previous_report: Previous race's stewards report (for pattern detection)
        
        Returns:
            Dict with red flag analysis and confidence adjustment
        """
        cache_key = f"{horse_no}_{hash(stewards_report)}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        report_text = stewards_report.lower()
        red_flags = []
        total_reduction = 0.0
        critical_flags = []
        
        for rule in self.red_flag_rules:
            category = rule['category']
            patterns = rule['patterns']
            severity = rule['severity']
            confidence_reduction = rule['confidence_reduction']
            
            # Check each pattern
            category_matched = False
            for pattern in patterns:
                if re.search(pattern, report_text, re.IGNORECASE):
                    red_flags.append({
                        'category': category,
                        'pattern': pattern,
                        'severity': severity,
                        'confidence_reduction': confidence_reduction
                    })
                    if not category_matched:  # Only add reduction once per category
                        total_reduction += confidence_reduction
                        category_matched = True
                    
                    if severity == 'critical':
                        critical_flags.append(category)
        
        # Check for worsening patterns (if previous report available)
        worsening_pattern = self._check_worsening_pattern(report_text, previous_report) if previous_report else None
        if worsening_pattern:
            total_reduction += 0.2  # Additional 20% reduction for worsening
            red_flags.append({
                'category': 'worsening_condition',
                'pattern': 'worsening from previous race',
                'severity': 'high',
                'confidence_reduction': 0.2
            })
        
        # Cap total reduction at 80%
        total_reduction = min(total_reduction, 0.8)
        
        result = {
            'horse_no': horse_no,
            'red_flags': red_flags,
            'total_confidence_reduction': total_reduction,
            'critical_flags': critical_flags,
            'worsening_pattern': worsening_pattern,
            'recommendation': self._get_recommendation(total_reduction, critical_flags)
        }
        
        self.cache[cache_key] = result
        return result
    
    def _check_worsening_pattern(self, current_report: str, previous_report: str) -> Optional[str]:
        """Check if the horse's condition is worsening compared to previous race"""
        if not previous_report:
            return None
        
        worsening_patterns = [
            (r'bled', r'bled from both nostrils'),  # From simple bleed to both nostrils
            (r'veterinary', r'required.*trial'),    # From vet check to required trial
            (r'slow to begin', r'never travelled'),  # From slow start to no travel
            (r'wide', r'raced wide.*without cover')  # From wide to very wide
        ]
        
        current_lower = current_report.lower()
        previous_lower = previous_report.lower()
        
        for mild_pattern, severe_pattern in worsening_patterns:
            if re.search(mild_pattern, previous_lower) and re.search(severe_pattern, current_lower):
                return f"Worsening: {mild_pattern} → {severe_pattern}"
        
        return None
    
    def _get_recommendation(self, total_reduction: float, critical_flags: List[str]) -> str:
        """Get betting recommendation based on red flags"""
        if total_reduction >= 0.6:
            return "AVOID BETTING - Critical red flags detected"
        elif total_reduction >= 0.4:
            return "EXTREME CAUTION - High risk, reduce stake significantly"
        elif total_reduction >= 0.2:
            return "CAUTION - Moderate risk, consider reducing stake"
        elif total_reduction >= 0.1:
            return "MINOR CAUTION - Low risk, monitor closely"
        else:
            return "NO RED FLAGS - Normal assessment"
    
    def adjust_probabilities(self, probabilities: Dict[str, float], stewards_reports: Dict[str, str], 
                           previous_reports: Dict[str, str] = None) -> Dict[str, float]:
        """
        Adjust horse probabilities based on stewards reports
        
        Args:
            probabilities: Original probabilities for each horse
            stewards_reports: Stewards reports for each horse (horse_no -> report)
            previous_reports: Previous race reports for pattern detection
        
        Returns:
            Adjusted probabilities
        """
        adjusted_probs = probabilities.copy()
        previous_reports = previous_reports or {}
        
        for horse_no, prob in probabilities.items():
            report = stewards_reports.get(horse_no, "")
            prev_report = previous_reports.get(horse_no, "")
            
            if report:
                analysis = self.analyze_horse_report(horse_no, report, prev_report)
                reduction = analysis['total_confidence_reduction']
                
                # Apply confidence reduction
                if reduction > 0:
                    adjusted_probs[horse_no] = prob * (1 - reduction)
                    logger.info(f"[STEWARDS] Horse #{horse_no}: {reduction:.1%} confidence reduction - {analysis['recommendation']}")
                    
                    # Log critical flags
                    if analysis['critical_flags']:
                        logger.warning(f"[STEWARDS] Horse #{horse_no}: Critical flags detected - {analysis['critical_flags']}")
        
        # Renormalize probabilities to sum to 1.0
        total_prob = sum(adjusted_probs.values())
        if total_prob > 0:
            adjusted_probs = {h: p / total_prob for h, p in adjusted_probs.items()}
        
        return adjusted_probs
    
    def get_horse_risk_summary(self, horse_no: str, stewards_report: str) -> Dict:
        """Get a detailed risk summary for a specific horse"""
        analysis = self.analyze_horse_report(horse_no, stewards_report)
        
        return {
            'horse_no': horse_no,
            'risk_level': self._get_risk_level(analysis['total_confidence_reduction']),
            'confidence_impact': f"{analysis['total_confidence_reduction']:.1%}",
            'red_flag_count': len(analysis['red_flags']),
            'critical_issues': analysis['critical_flags'],
            'recommendation': analysis['recommendation'],
            'flags_found': [f"{flag['category']}: {flag['pattern']}" for flag in analysis['red_flags']]
        }
    
    def _get_risk_level(self, reduction: float) -> str:
        """Convert confidence reduction to risk level"""
        if reduction >= 0.6:
            return "CRITICAL"
        elif reduction >= 0.4:
            return "HIGH"
        elif reduction >= 0.2:
            return "MODERATE"
        elif reduction >= 0.1:
            return "LOW"
        else:
            return "MINIMAL"

# Singleton instance for the application
_stewards_analyzer = None

def get_stewards_analyzer() -> StewardsAnalyzer:
    """Get the global stewards analyzer instance"""
    global _stewards_analyzer
    if _stewards_analyzer is None:
        _stewards_analyzer = StewardsAnalyzer()
    return _stewards_analyzer
