"""
Ensemble Prediction Service
Combines predictions from multiple AI models for improved accuracy
"""

import json
import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from loguru import logger
import statistics

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config
from models.schemas import Prediction

@dataclass
class ModelPrediction:
    """Prediction from a single model"""
    model_name: str
    model_id: str
    confidence_score: float
    recommended_bet: str
    probabilities: Dict[str, float]
    kelly_stakes: Dict[str, float] = field(default_factory=dict)
    analysis_markdown: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class EnsembleResult:
    """Combined ensemble prediction"""
    race_id: str
    model_predictions: List[ModelPrediction]
    ensemble_probabilities: Dict[str, float]
    ensemble_confidence: float
    ensemble_bet: str
    agreement_score: float  # How much models agree (0-1)
    weighting_used: Dict[str, float]  # Model weights used
    consensus_horses: List[str]  # Horses all models agree on
    disagreement_horses: List[str]  # Horses with significant disagreement

class EnsemblePredictor:
    """
    Combines predictions from multiple AI models using weighted averaging.
    
    Models in ensemble:
    1. Gemini 2.5 Flash (tuned model) - Primary
    2. Gemini 2.5 Pro - Shadow model
    3. Claude 3.5 Sonnet - Alternative perspective
    
    Weighting strategies:
    - Equal weights (default)
    - Performance-based weights
    - Confidence-based weights
    """
    
    def __init__(self):
        self.models = {
            'gemini_flash': {
                'id': Config.GEMINI_MODEL,
                'weight': 0.5,
                'enabled': True
            },
            'gemini_pro': {
                'id': Config.SHADOW_MODEL,
                'weight': 0.3,
                'enabled': True
            },
            'claude_sonnet': {
                'id': 'claude-3.5-sonnet',
                'weight': 0.2,
                'enabled': False  # Not implemented yet
            }
        }
        
        # Ensemble parameters
        self.agreement_threshold = 0.10  # Models must agree within 10%
        self.min_models_required = 2  # Minimum models for ensemble
        self.max_disagreement = 0.20  # Max disagreement before flagging
        
        logger.info(f"Ensemble Predictor initialized with {len([m for m in self.models.values() if m['enabled']])} models")
    
    async def predict_ensemble(self, prompt: str, response_schema: Dict, data: Dict, 
                             date_str: str, venue: str, race_no: int) -> EnsembleResult:
        """
        Run prediction with all enabled models and combine results.
        
        Args:
            prompt: Prediction prompt
            response_schema: Response schema
            data: Race data
            date_str: Date string
            venue: Venue code
            race_no: Race number
            
        Returns:
            Ensemble prediction result
        """
        race_id = f"{date_str}_{venue}_R{race_no}"
        logger.info(f"[ENSEMBLE] Running ensemble prediction for {race_id}")
        
        # Run predictions in parallel
        tasks = []
        for model_name, config in self.models.items():
            if config['enabled']:
                task = self._predict_single_model(model_name, prompt, response_schema, data)
                tasks.append((model_name, task))
        
        # Wait for all predictions
        predictions = []
        for model_name, task in tasks:
            try:
                result = await task
                if result:
                    predictions.append(result)
                    logger.info(f"[ENSEMBLE] {model_name}: confidence={result.confidence_score:.2f}")
            except Exception as e:
                logger.error(f"[ENSEMBLE] {model_name} failed: {e}")
        
        # Check minimum models
        if len(predictions) < self.min_models_required:
            raise ValueError(f"Only {len(predictions)} models succeeded, minimum {self.min_models_required} required")
        
        # Combine predictions
        ensemble = self._combine_predictions(race_id, predictions)
        
        # Log ensemble results
        logger.info(f"[ENSEMBLE] Combined confidence: {ensemble.ensemble_confidence:.2f}")
        logger.info(f"[ENSEMBLE] Agreement score: {ensemble.agreement_score:.2f}")
        logger.info(f"[ENSEMBLE] Consensus horses: {ensemble.consensus_horses}")
        
        return ensemble
    
    async def _predict_single_model(self, model_name: str, prompt: str, 
                                   response_schema: Dict, data: Dict) -> Optional[ModelPrediction]:
        """Run prediction with a single model"""
        import google.generativeai as genai
        
        config = self.models[model_name]
        model_id = config['id']
        
        try:
            # Initialize client for this model
            if model_name.startswith('gemini'):
                client = genai.Client(vertexai=True, project=Config.MODEL_PROJECT_ID, location=Config.GCP_LOCATION)
            else:
                # TODO: Implement Claude integration
                logger.warning(f"Model {model_name} not yet implemented")
                return None
            
            # Generate prediction
            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=genai.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema
                )
            )
            
            # Parse response
            pred_data = json.loads(response.text)
            
            return ModelPrediction(
                model_name=model_name,
                model_id=model_id,
                confidence_score=pred_data.get('confidence_score', 0.5),
                recommended_bet=pred_data.get('recommended_bet', ''),
                probabilities=pred_data.get('probabilities', {}),
                kelly_stakes=pred_data.get('kelly_stakes', {}),
                analysis_markdown=pred_data.get('analysis_markdown', ''),
                metadata={
                    'timestamp': datetime.now().isoformat(),
                    'response_time': 0  # TODO: Track response time
                }
            )
            
        except Exception as e:
            logger.error(f"[ENSEMBLE] Error in {model_name}: {e}")
            return None
    
    def _combine_predictions(self, race_id: str, predictions: List[ModelPrediction]) -> EnsembleResult:
        """Combine multiple model predictions using weighted averaging"""
        
        # Normalize weights
        total_weight = sum(self.models[p.model_name]['weight'] for p in predictions)
        weights = {p.model_name: self.models[p.model_name]['weight'] / total_weight for p in predictions}
        
        # Weighted average of probabilities
        ensemble_probs = {}
        horse_numbers = set()
        
        # Collect all horse numbers
        for pred in predictions:
            horse_numbers.update(pred.probabilities.keys())
        
        # Calculate weighted average for each horse
        for horse_no in horse_numbers:
            weighted_prob = 0.0
            total_weight_used = 0.0
            
            for pred in predictions:
                prob = pred.probabilities.get(horse_no, 0.0)
                weight = weights[p.model_name]
                weighted_prob += prob * weight
                total_weight_used += weight
            
            if total_weight_used > 0:
                ensemble_probs[horse_no] = weighted_prob / total_weight_used
        
        # Renormalize to sum to 1.0
        total_prob = sum(ensemble_probs.values())
        if total_prob > 0:
            ensemble_probs = {h: p / total_prob for h, p in ensemble_probs.items()}
        
        # Calculate ensemble confidence (weighted average)
        ensemble_confidence = sum(pred.confidence_score * weights[p.model_name] for pred in predictions)
        
        # Determine ensemble bet (horse with highest probability)
        if ensemble_probs:
            top_horse = max(ensemble_probs, key=ensemble_probs.get)
            ensemble_bet = f"WIN {top_horse}"
        else:
            ensemble_bet = "NO BET"
        
        # Calculate agreement score
        agreement_score = self._calculate_agreement_score(predictions)
        
        # Find consensus and disagreement horses
        consensus_horses, disagreement_horses = self._find_consensus_disagreement(predictions)
        
        return EnsembleResult(
            race_id=race_id,
            model_predictions=predictions,
            ensemble_probabilities=ensemble_probs,
            ensemble_confidence=ensemble_confidence,
            ensemble_bet=ensemble_bet,
            agreement_score=agreement_score,
            weighting_used=weights,
            consensus_horses=consensus_horses,
            disagreement_horses=disagreement_horses
        )
    
    def _calculate_agreement_score(self, predictions: List[ModelPrediction]) -> float:
        """Calculate how much models agree on top picks"""
        if len(predictions) < 2:
            return 1.0
        
        # Get top 3 horses from each model
        top_picks = []
        for pred in predictions:
            sorted_horses = sorted(pred.probabilities.items(), key=lambda x: x[1], reverse=True)
            top_picks.append([h for h, _ in sorted_horses[:3]])
        
        # Calculate overlap
        agreement = 0.0
        total_comparisons = 0
        
        for i in range(len(top_picks)):
            for j in range(i + 1, len(top_picks)):
                overlap = len(set(top_picks[i]) & set(top_picks[j]))
                agreement += overlap / 3.0  # 3 horses each
                total_comparisons += 1
        
        return agreement / total_comparisons if total_comparisons > 0 else 0.0
    
    def _find_consensus_disagreement(self, predictions: List[ModelPrediction]) -> Tuple[List[str], List[str]]:
        """Find horses with consensus and significant disagreement"""
        horse_probs = {}
        
        # Collect probabilities for each horse across models
        for pred in predictions:
            for horse_no, prob in pred.probabilities.items():
                if horse_no not in horse_probs:
                    horse_probs[horse_no] = []
                horse_probs[horse_no].append(prob)
        
        consensus = []
        disagreement = []
        
        for horse_no, probs in horse_probs.items():
            if len(probs) >= 2:
                # Calculate standard deviation
                std_dev = statistics.stdev(probs) if len(probs) > 1 else 0
                mean_prob = statistics.mean(probs)
                
                # Consensus: low variance and high mean probability
                if std_dev < self.agreement_threshold and mean_prob > 0.2:
                    consensus.append(horse_no)
                # Disagreement: high variance
                elif std_dev > self.max_disagreement:
                    disagreement.append(horse_no)
        
        return consensus, disagreement
    
    def get_ensemble_summary(self, result: EnsembleResult) -> Dict:
        """Get a summary of ensemble results for logging"""
        return {
            'race_id': result.race_id,
            'models_used': len(result.model_predictions),
            'model_names': [p.model_name for p in result.model_predictions],
            'ensemble_confidence': result.ensemble_confidence,
            'agreement_score': result.agreement_score,
            'top_horse': result.ensemble_bet.replace('WIN ', ''),
            'consensus_count': len(result.consensus_horses),
            'disagreement_count': len(result.disagreement_horses),
            'weights_used': result.weighting_used
        }
    
    def should_skip_ensemble(self, result: EnsembleResult) -> Tuple[bool, str]:
        """
        Determine if ensemble prediction should be skipped due to disagreement.
        
        Returns:
            (should_skip, reason)
        """
        # Skip if agreement is too low
        if result.agreement_score < 0.3:
            return True, f"Low agreement score: {result.agreement_score:.2f}"
        
        # Skip if consensus is too low
        if result.ensemble_confidence < 0.4:
            return True, f"Low ensemble confidence: {result.ensemble_confidence:.2f}"
        
        # Skip if significant disagreement on top horse
        top_horse = result.ensemble_bet.replace('WIN ', '')
        if top_horse in result.disagreement_horses:
            return True, f"Significant disagreement on top horse #{top_horse}"
        
        return False, "Ensemble prediction valid"

# Singleton instance
_ensemble_predictor = None

def get_ensemble_predictor() -> EnsemblePredictor:
    """Get the global ensemble predictor instance"""
    global _ensemble_predictor
    if _ensemble_predictor is None:
        _ensemble_predictor = EnsemblePredictor()
    return _ensemble_predictor
