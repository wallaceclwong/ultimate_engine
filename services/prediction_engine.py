import json
import os
import sys
from google import genai
from google.genai import types
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger

# Add project root to path to allow imports from config and models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config
from models.schemas import Prediction
from services.firestore_service import FirestoreService
# Stubs for missing services (Temporary for verification)
class SynergyService:
    def get_synergy(self, j, t): return {}
class StewardAnalyser:
    def get_hidden_form(self, b): return []
class PedigreeService:
    async def get_enriched_pedigree(self, h): return {}
class KellyCriterion:
    def __init__(self, bankroll: float = 10000.0, fractional_kelly: float = 0.1):
        self.bankroll = bankroll
        self.fractional_kelly = fractional_kelly

    def calculate_race_stakes(self, probabilities: Dict[str, float], market_odds: Dict[str, float], racecard: Dict[str, Any] = None) -> Dict[str, float]:
        """
        Calculates recommended stakes for each horse in a race.
        Kelly Formula: f* = (p*o - 1) / (o - 1)
        where:
        - p is the probability of winning
        - o is the decimal odds
        Safeguards include max 2 horses, min 5% edge, max 5% bankroll exposure per race.
        """
        stakes = {}
        if not market_odds:
            return stakes

        edges = {}
        for horse_no, p in probabilities.items():
            h_id = str(horse_no)
            o = market_odds.get(h_id)
            if o and o > 1.0 and p > 0:
                # Filter: Minimum confidence threshold (dynamic)
                # Calculate dynamic confidence based on race conditions
                race_class = racecard.get('race_class')
                field_size = len(racecard.get('horses', []))
                track_condition = racecard.get('track_condition', 'GOOD')
                distance = racecard.get('distance', 0)
                
                dynamic_confidence = Config.get_dynamic_confidence(
                    race_class=race_class,
                    field_size=field_size,
                    track_condition=track_condition,
                    distance=distance
                )
                
                if p < dynamic_confidence:
                    continue
                
                # Calculate edge (f*)
                edge = (p * o - 1) / (o - 1)
                edges[h_id] = edge

        # Sort by edge, descending
        sorted_horses = sorted(edges.items(), key=lambda x: x[1], reverse=True)
        total_exposure = 0.0
        max_exposure = self.bankroll * 0.05  # 5% max exposure per race

        for h_id, edge in sorted_horses:
            # Skip if edge is too small
            if edge < Config.MIN_EDGE:
                continue
            
            # Max 2 horses per race
            if len(stakes) >= 2:
                continue
            
            # Apply fractional Kelly to bankroll
            stake = self.bankroll * self.fractional_kelly * edge
            
            # Apply exposure cap
            if total_exposure + stake > max_exposure:
                remaining = max_exposure - total_exposure
                if remaining > 0:
                    stake = remaining
                else:
                    break
                    
            # Round down to nearest $10 (conservative)
            stake = max(10, int(stake // 10) * 10)
            
            stakes[h_id] = float(stake)
            total_exposure += stake

        return stakes
class WeatherNextClient:
    pass

from services.notification_service import NotificationService
from services.bigquery_service import BigQueryService
from services.storage_service import StorageService
from services.stewards_analyzer import get_stewards_analyzer
from services.live_odds_monitor import get_live_odds_monitor
from services.ensemble_predictor import get_ensemble_predictor
from services.race_pace_analyzer import get_race_pace_analyzer

class PredictionEngine:
    def __init__(self):
        # Tuned model requires Vertex AI; always use Vertex for predictions
        print(f"[INFO] Initializing Vertex AI Client in {Config.GCP_LOCATION}...")
        self.client = genai.Client(
            vertexai=True,
            project=Config.MODEL_PROJECT_ID,
            location=Config.GCP_LOCATION
        )
            
        self.cache_id = None # Can be set after initialization if using Vertex AI
        self.model_id = Config.GEMINI_MODEL
        print(f"[INFO] Prediction model: {self.model_id}")
        self.base_dir = Path(__file__).resolve().parent.parent
        self.data_dir = self.base_dir / "data"
        self.predictions_dir = self.data_dir / "predictions"
        self.predictions_dir.mkdir(parents=True, exist_ok=True)
        self.firestore = FirestoreService()
        self.synergy = SynergyService()
        self.steward = StewardAnalyser()
        self.weathernext = WeatherNextClient()
        self.pedigree = PedigreeService()
        
        from services.bankroll_manager import BankrollManager
        self.bankroll_manager = BankrollManager()
        
        self.kelly = KellyCriterion(
            bankroll=self.bankroll_manager.get_current_bankroll(), 
            fractional_kelly=Config.KELLY_FRACTION
        )
        self.notifications = NotificationService()
        self.bigquery = BigQueryService()
        self.storage = StorageService()
        
        # Load RL Bias Correction with contextual awareness
        from services.rl_optimizer import RLOptimizer
        self.optimizer = RLOptimizer()
        
        from services.deep_dive_agent import DeepDiveAgent
        self.deep_dive_agent = DeepDiveAgent()


    async def load_race_data(self, date_str: str, venue: str, race_no: int) -> Dict[str, Any]:
        """Loads all available data for a single race."""
        # Note: Racecard filename uses slightly different format in current data
        # data/racecard_20260315_R1.json vs results_2026-03-15_ST_R1.json
        date_racecard = date_str.replace("-", "")
        
        racecard_path = self.data_dir / f"racecard_{date_racecard}_R{race_no}.json"
        results_path = self.data_dir / "results" / f"results_{date_str}_{venue}_R{race_no}.json"
        analytical_path = self.data_dir / "analytical" / f"analytical_{date_str}_{venue}_R{race_no}.json"
        
        # Look for the latest odds snapshot for this specific date and race
        odds_dir = self.data_dir / "odds"
        odds_data = {}
        if odds_dir.exists():
            # First: try to find a snapshot that matches date AND race number exactly
            date_compact = date_str.replace("-", "")
            exact_snapshots = list(odds_dir.glob(f"snapshot_{date_str}_R{race_no}_*.json"))
            if not exact_snapshots:
                # Also try compact date format (snapshot_20260318_R1_...)
                exact_snapshots = list(odds_dir.glob(f"snapshot_{date_compact}_R{race_no}_*.json"))
            
            if exact_snapshots:
                # Filter for valid snapshots (not empty win_odds)
                valid_snapshots = []
                for p in sorted(exact_snapshots, key=lambda x: x.stat().st_mtime, reverse=True):
                    try:
                        with open(p, "r", encoding="utf-8") as f:
                            temp_data = json.load(f)
                            if temp_data.get("win_odds"):
                                valid_snapshots.append((p, temp_data))
                                break # Found the latest valid one
                    except Exception:
                        continue
                
                if valid_snapshots:
                    latest_snapshot, odds_data = valid_snapshots[0]
                    print(f"[INFO] Loaded valid odds snapshot: {latest_snapshot.name}")
                else:
                    print(f"[WARNING] No valid date-specific odds snapshots found for {date_str} R{race_no}.")

            if not odds_data:
                # Fallback: use most recent snapshot for this race number (any date)
                all_snapshots = list(odds_dir.glob(f"snapshot_*_R{race_no}_*.json"))
                if all_snapshots:
                    # Sort by modification time and find first valid one
                    for p in sorted(all_snapshots, key=lambda x: x.stat().st_mtime, reverse=True):
                        try:
                            with open(p, "r", encoding="utf-8") as f:
                                temp_data = json.load(f)
                                if temp_data.get("win_odds"):
                                    odds_data = temp_data
                                    print(f"[INFO] Using latest valid matching race snapshot: {p.name}")
                                    break
                        except Exception:
                            continue

        data = {
            "racecard": {},
            "results": {},
            "analytical": {},
            "odds": odds_data
        }

        if not racecard_path.exists() and results_path.exists():
            print(f"[INFO] Racecard missing for {date_str} R{race_no}. Reconstructing from results...")
            with open(results_path, "r", encoding="utf-8") as f:
                res_data = json.load(f)
            
            # Reconstruct a skeleton racecard
            skeleton_horses = []
            for r in res_data.get("results", []):
                skeleton_horses.append({
                    "saddle_number": int(r["horse_no"]) if r["horse_no"].isdigit() else 0,
                    "horse_name": r.get("brand_id", ""),  # Using brand_id as a hint
                    "jockey": r.get("jockey", ""),
                    "trainer": r.get("trainer", ""),
                    "weight": 133, # Dummy weight if missing
                    "last_6_runs": []
                })
            
            data["racecard"] = {
                "id": f"{date_str}_R{race_no}",
                "distance": 1200, # Defaulting or could extract from results if available
                "horses": skeleton_horses
            }
        elif racecard_path.exists():
            with open(racecard_path, "r", encoding="utf-8") as f:
                data["racecard"] = json.load(f)
        
        if results_path.exists():
            with open(results_path, "r", encoding="utf-8") as f:
                data["results"] = json.load(f)
                
        if analytical_path.exists():
            with open(analytical_path, "r", encoding="utf-8") as f:
                data["analytical"] = json.load(f)

        # 5. Load Synergy Data
        synergy_data = {}
        for h in data["racecard"].get("horses", []):
            jockey = h.get("jockey")
            trainer = h.get("trainer")
            if jockey and trainer:
                stats = self.synergy.get_synergy(jockey, trainer)
                if stats:
                    synergy_key = f"{jockey} + {trainer}"
                    synergy_data[synergy_key] = stats
        
        data["synergy"] = synergy_data

        # 2. Pedigree Intelligence
        pedigree_intel = {}
        for horse_data in data["racecard"].get("horses", []):
            horse_id = horse_data.get("horse_id") # Assuming horse_id is available in racecard horse data
            if horse_id:
                try:
                    # We do this sequentially for now, could be parallelized
                    intel = await self.pedigree.get_enriched_pedigree(horse_id)
                    if intel:
                        pedigree_intel[horse_id] = intel
                except Exception as e:
                    print(f"Warning: Could not get pedigree for horse {horse_id}: {e}")
                    continue
        data["pedigree_intel"] = pedigree_intel

        # 3. Load Hidden Form Tags
        hidden_form_data = {}
        for h in data["racecard"].get("horses", []):
            brand_id = h.get("brand_id")
            if brand_id:
                tags = self.steward.get_hidden_form(brand_id)
                if tags:
                    hidden_form_data[brand_id] = tags
        
        data["hidden_form"] = hidden_form_data

        # 7. Load Weather Intelligence
        weather_intel = {}
        intel_path = Path(f"data/weather/intel_{venue}_{date_str}.json")
        if intel_path.exists():
            with open(intel_path, "r", encoding="utf-8") as f:
                weather_intel = json.load(f)
        data["weather_intel"] = weather_intel

        return data

    async def generate_prediction(self, date_str: str, venue: str, race_no: int, use_ensemble: bool = False) -> Optional[Prediction]:
        """Generates a prediction using Gemini or Ensemble based on loaded race data."""
        data = await self.load_race_data(date_str, venue, race_no)
        
        if not data["racecard"]:
            print(f"Warning: No racecard found for {date_str} R{race_no}. Prediction may be incomplete.")
            if not data["results"] and not data["analytical"]:
                print(f"Error: Insufficient data for {date_str} R{race_no}.")
                return None

        # Retrieve contextual weights for this specific meeting
        self.bias_correction = self.optimizer.get_weights(date_str, venue)
        print(f"[INFO] Using contextual biases for {date_str} {venue}: {self.bias_correction}")

        # Construct the prompt
        prompt = self._construct_prompt(data)

        if use_ensemble:
            print(f"[ENSEMBLE] Generating ensemble prediction for {date_str} {venue} R{race_no}...")
            return await self._generate_ensemble_prediction(date_str, venue, race_no, prompt, data)
        else:
            print(f"Generating prediction for {date_str} {venue} R{race_no}...")
            return await self._generate_single_prediction(date_str, venue, race_no, prompt, data)
    
    async def _generate_single_prediction(self, date_str: str, venue: str, race_no: int, prompt: str, data: Dict) -> Optional[Prediction]:
        """Generate prediction using single model (original logic)"""
        try:
            # Define dynamic probability properties for the schema
            racecard = data.get("racecard", {})
            horses = racecard.get("horses", [])
            prob_props = {
                str(h.get("saddle_number") or h.get("horse_no")): {"type": "number"}
                for h in horses
            }

            response_schema = {
                "type": "object",
                "properties": {
                    "confidence_score": {"type": "number"},
                    "is_best_bet": {"type": "boolean"},
                    "recommended_bet": {"type": "string"},
                    "probabilities": {
                        "type": "object",
                        "properties": prob_props,
                        "required": list(prob_props.keys())
                    },
                    "analysis_markdown": {"type": "string"}
                },
                "required": ["confidence_score", "is_best_bet", "recommended_bet", "probabilities", "analysis_markdown"]
            }

            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    cached_content=self.cache_id
                )
            )
            
            prediction_dict = json.loads(response.text)
            
            # Calculate Kelly Stakes
            win_odds = data.get("odds", {}).get("win_odds", {})
            probs = prediction_dict.get("probabilities", {})
            
            # CRITICAL FIX: Normalize probabilities to strictly sum to 1.0 (prevents Hallucinated EV)
            total_prob = sum(probs.values()) if probs else 0.0
            if total_prob > 0:
                probs = {h: p / total_prob for h, p in probs.items()}
                prediction_dict["probabilities"] = probs
            
            # Apply RL Bias Correction to probabilities before Kelly calculation
            # If the AI is overconfident, we scale down the probabilities to be more conservative
            conf_bias = self.bias_correction.get("confidence_bias", 0.0)
            if conf_bias > 0:
                # Simple linear de-biasing
                probs = {h: p * (1 - conf_bias) for h, p in probs.items()}
            
            # Apply Stewards Report Analysis
            stewards_analyzer = get_stewards_analyzer()
            stewards_reports = self._extract_stewards_reports_from_racecard(racecard)
            
            if stewards_reports:
                print(f"[STEWARDS] Analyzing {len(stewards_reports)} horse reports...")
                probs = stewards_analyzer.adjust_probabilities(probs, stewards_reports)
                
                # Log summary of adjustments
                for horse_no in list(probs.keys())[:3]:  # Show top 3
                    original_prob = prediction_dict.get("probabilities", {}).get(horse_no, 0)
                    adjusted_prob = probs.get(horse_no, 0)
                    if original_prob > 0 and adjusted_prob < original_prob:
                        reduction = (original_prob - adjusted_prob) / original_prob
                        print(f"[STEWARDS] Horse #{horse_no}: {original_prob:.1%} → {adjusted_prob:.1%} ({reduction:.1%} reduction)")
            
            # Update probabilities with stewards-adjusted values
            prediction_dict["probabilities"] = probs
            
            # Apply Live Odds Integration
            live_odds_monitor = get_live_odds_monitor()
            race_id = f"{date_str}_{venue}_R{race_no}"
            
            # Load current odds state
            odds_state = live_odds_monitor.update_race_state(date_str, venue, race_no)
            
            if odds_state and odds_state.movements:
                print(f"[LIVE ODDS] Analyzing odds movements for {race_id}")
                print(f"  Market confidence: {odds_state.market_confidence:.1%}")
                print(f"  Late money horses: {odds_state.late_money_horses}")
                
                # Adjust probabilities based on odds
                probs = live_odds_monitor.adjust_probabilities(probs, race_id)
                
                # Log significant adjustments
                for horse_no, movement in odds_state.movements.items():
                    if movement.trend != 'stable':
                        print(f"  Horse #{horse_no}: {movement.trend} ({movement.movement_pct:+.1%})")
            else:
                print(f"[LIVE ODDS] No odds data available for {race_id}")
            
            # Apply Race Pace Analysis
            try:
                race_pace_analyzer = get_race_pace_analyzer()
                horse_list = list(probs.keys())
                
                if horse_list:
                    pace_analysis, profiles = race_pace_analyzer.analyze_race(race_id, horse_list)
                    
                    if pace_analysis.pace_confidence > 0.5:
                        print(f"[RACE PACE] Analyzing pace scenario for {race_id}")
                        print(f"  Predicted pace: {pace_analysis.predicted_pace.value}")
                        print(f"  Confidence: {pace_analysis.pace_confidence:.1%}")
                        
                        # Adjust probabilities based on pace
                        probs = race_pace_analyzer.adjust_probabilities_for_pace(probs, pace_analysis, profiles)
                        
                        # Log beneficiaries and victims
                        if pace_analysis.pace_beneficiaries:
                            print(f"  Pace beneficiaries: {pace_analysis.pace_beneficiaries}")
                        if pace_analysis.pace_victims:
                            print(f"  Pace victims: {pace_analysis.pace_victims}")
                    else:
                        print(f"[RACE PACE] Low confidence pace analysis for {race_id}, skipping")
            except Exception as e:
                logger.warning(f"[RACE PACE] Error in pace analysis: {e}")
            
            # Apply distance filter
            distance = racecard.get("distance", 0)
            if distance < Config.MIN_DISTANCE or distance > Config.MAX_DISTANCE:
                print(f"Skipping race {date_str}_{venue}_R{race_no}: distance {distance}m outside range [{Config.MIN_DISTANCE}-{Config.MAX_DISTANCE}]")
                probs = {}  # Clear probabilities to prevent betting
            
            # Calculate and log dynamic confidence threshold
            race_class = racecard.get('race_class')
            field_size = len(racecard.get('horses', []))
            track_condition = racecard.get('track_condition', 'GOOD')
            
            dynamic_confidence = Config.get_dynamic_confidence(
                race_class=race_class,
                field_size=field_size,
                track_condition=track_condition,
                distance=distance
            )
            
            print(f"[DYNAMIC CONFIDENCE] {date_str}_{venue}_R{race_no}: {dynamic_confidence:.2f} (class={race_class}, field={field_size}, track={track_condition}, dist={distance}m)")
            
            # Apply track-specific Kelly adjustment
            track_multiplier = Config.TRACK_KELLY_MULTIPLIERS.get(venue, 1.0)
            adjusted_kelly_fraction = self.kelly.fractional_kelly * track_multiplier
            
            # Fetch dynamic bankroll before calculating stakes
            self.kelly.bankroll = self.bankroll_manager.get_current_bankroll()
            
            # Temporarily adjust Kelly fraction for this race
            original_fraction = self.kelly.fractional_kelly
            self.kelly.fractional_kelly = adjusted_kelly_fraction
            
            prediction_dict["kelly_stakes"] = self.kelly.calculate_race_stakes(
                probs, 
                win_odds,
                racecard
            )
            
            # Restore original fraction
            self.kelly.fractional_kelly = original_fraction
            prediction_dict["market_odds"] = win_odds
            
            # Create Prediction object
            prediction = Prediction(
                race_id=f"{date_str}_{venue}_R{race_no}",
                gemini_model=Config.GEMINI_MODEL,
                **prediction_dict
            )
            
            self._save_prediction(prediction)
            
            # Send Push Notification for High Confidence / High EV bets
            has_stakes = any(v > 0 for v in prediction.kelly_stakes.values())
            if prediction.confidence_score >= 0.8 or has_stakes:
                # Identify the top horse ID
                top_horse_id = "Multiple"
                if prediction.kelly_stakes:
                    top_horse_id = max(prediction.kelly_stakes, key=prediction.kelly_stakes.get)
                
                # We don't have EV stored in the simple dict, so we use the stake as a proxy for 'value' here
                max_stake = max(prediction.kelly_stakes.values()) if prediction.kelly_stakes else 0.0
                
                self.notifications.send_bet_alert(
                    race_id=prediction.race_id,
                    horse_name=f"Horse {top_horse_id}",
                    confidence=prediction.confidence_score,
                    ev=max_stake # Using stake as a proxy since EV isn't in this schema
                )

            # ELITE FEATURE: Double-Model Consensus Strategy
            # Runs Gemini 2.5 Pro and Gemini 2.0 Flash in parallel. Beta only if they agree.
            if Config.SHADOW_MODEL and Config.SHADOW_MODEL != self.model_id:
                try:
                    shadow_probs = self._run_shadow_prediction(
                        prompt, response_schema, data,
                        date_str, venue, race_no
                    )
                    
                    # Validate model agreement before finalizing stakes
                    if shadow_probs and prediction_dict.get("kelly_stakes"):
                        main_probs = prediction_dict.get("probabilities", {})
                        disagreement = self._check_model_disagreement(main_probs, shadow_probs)
                        
                        if disagreement:
                            logger.warning(f"❌ CONSENSUS FAILED for {date_str}_{venue}_R{race_no}: {disagreement}")
                            logger.warning("Clearing stakes due to model disagreement.")
                            prediction_dict["kelly_stakes"] = {}
                            prediction_dict["model_agreement"] = False
                        else:
                            logger.info(f"✅ CONSENSUS PASSED for {date_str}_{venue}_R{race_no}")
                            prediction_dict["model_agreement"] = True
                    
                except Exception as e:
                    logger.error(f"[SHADOW] Shadow prediction failed: {e}")
                    # If shadow fails, we default to conservative: clear stakes
                    prediction_dict["kelly_stakes"] = {}
                    prediction_dict["model_agreement"] = False

            # Create Prediction object
            prediction = Prediction(
                race_id=f"{date_str}_{venue}_R{race_no}",
                gemini_model=Config.GEMINI_MODEL,
                **prediction_dict
            )
            
            # ELITE FEATURE: Deep-Dive Agent
            # Triggered for High-Confidence or High-Stake bets (> $150 or > 0.85 Confidence)
            max_stake = max(prediction.kelly_stakes.values()) if prediction.kelly_stakes else 0.0
            if prediction.confidence_score >= 0.85 or max_stake >= 150.0:
                # Identify the top horse
                top_horse_id = max(prediction.kelly_stakes, key=prediction.kelly_stakes.get) if prediction.kelly_stakes else None
                if not top_horse_id and prediction.probabilities:
                    top_horse_id = max(prediction.probabilities, key=prediction.probabilities.get)
                
                if top_horse_id:
                    # Non-blocking async call (conceptual, we'll wait for now for this audit)
                    await self.deep_dive_agent.analyze_top_horse_history(
                        f"{date_str}_{venue}_R{race_no}", 
                        top_horse_id, 
                        data
                    )

            self._save_prediction(prediction)
            
            return prediction
            
        except Exception as e:
            print(f"Error generating prediction: {e}")
            return None

    def _run_shadow_prediction(self, prompt, response_schema, data, date_str, venue, race_no):
        """Run the same prompt through the shadow model for A/B comparison."""
        shadow_id = Config.SHADOW_MODEL
        print(f"[SHADOW] Running A/B shadow prediction with {shadow_id}...")

        shadow_resp = self.client.models.generate_content(
            model=shadow_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
            )
        )

        shadow_dict = json.loads(shadow_resp.text)

        # Calculate Kelly for shadow too
        win_odds = data.get("odds", {}).get("win_odds", {})
        shadow_probs = shadow_dict.get("probabilities", {})
        
        # CRITICAL FIX: Normalize shadow probabilities
        total_prob = sum(shadow_probs.values()) if shadow_probs else 0.0
        if total_prob > 0:
            shadow_probs = {h: p / total_prob for h, p in shadow_probs.items()}
            shadow_dict["probabilities"] = shadow_probs

        self.kelly.bankroll = self.bankroll_manager.get_current_bankroll()
        shadow_dict["kelly_stakes"] = self.kelly.calculate_race_stakes(shadow_probs, win_odds)
        shadow_dict["market_odds"] = win_odds

        shadow_pred = Prediction(
            race_id=f"{date_str}_{venue}_R{race_no}",
            gemini_model=shadow_id,
            **shadow_dict
        )

        # Save shadow prediction with _shadow suffix
        shadow_file = self.predictions_dir / f"prediction_{date_str}_{venue}_R{race_no}_shadow.json"
        with open(shadow_file, "w", encoding="utf-8") as f:
            f.write(shadow_pred.model_dump_json(indent=2))
        print(f"[SHADOW] Shadow prediction saved to {shadow_file}")
        
        # Return shadow probabilities for agreement check
        return shadow_probs

        # Sync shadow to Firestore under separate collection
        try:
            self.firestore.upsert(
                "predictions_shadow",
                f"{date_str}_{venue}_R{race_no}",
                shadow_pred
            )
        except Exception as e:
            print(f"[SHADOW] Firestore sync failed: {e}")

    def _check_model_disagreement(self, main_probs: Dict, shadow_probs: Dict) -> str:
        """Check if main and shadow models disagree significantly on top picks."""
        if not main_probs or not shadow_probs:
            return ""
        
        # Find top 2 picks from each model
        main_top = sorted(main_probs.items(), key=lambda x: x[1], reverse=True)[:2]
        shadow_top = sorted(shadow_probs.items(), key=lambda x: x[1], reverse=True)[:2]
        
        # Check if top picks differ significantly
        for horse, main_prob in main_top:
            shadow_prob = shadow_probs.get(horse, 0)
            prob_diff = abs(main_prob - shadow_prob)
            
            if prob_diff > Config.SHADOW_AGREEMENT_THRESHOLD:
                return f"Horse {horse}: Main={main_prob:.2%}, Shadow={shadow_prob:.2%} (diff={prob_diff:.2%})"
        
        return ""  # Models agree

    def _construct_prompt(self, data: Dict[str, Any]) -> str:
        racecard = data.get("racecard", {})
        results = data.get("results", {})
        analytical = data.get("analytical", {})
        odds = data.get("odds", {})
        
        racecard_horses = racecard.get('horses', [])
        horse_nos = [str(h.get('saddle_number', '')) for h in racecard_horses if h.get('saddle_number')]
        if not horse_nos and racecard_horses:
            # Fallback for different data structures
            horse_nos = [str(h.get('horse_no', '')) for h in racecard_horses if h.get('horse_no')]
        
        horse_nos_str = ", ".join(horse_nos)
        
        # Check if we have actual winners (Audit Mode)
        actual_winner = ""
        for div in results.get("dividends", {}).get("WIN", []):
            actual_winner = div.get("combination")
            break
            
        is_audit = bool(actual_winner)

        prompt = f"""
Act as a professional Hong Kong horse racing analyst. 
{ 'You are performing a POST-RACE AUDIT.' if is_audit else 'Your task is to analyze race data and provide a winning prediction.' }
"""

        if is_audit:
            prompt += f"""
### ACTUAL RESULTS (Audit Context)
RACE OVER: The actual winner was Horse #{actual_winner}.
Dividends: {json.dumps(results.get('dividends', {}), indent=2)}

INSTRUCTION: Since the race is already finished, your analysis must reflect the actual outcome. 
If your predicted probabilities (based on form) favored a horse that lost, explain what went wrong (e.g., using Stewards' incidents).
Do NOT claim you won if the result shows you lost.
"""

        prompt += f"""
### RACE CONTEXT
Race ID: {racecard.get('id', 'N/A')}
Distance: {racecard.get('distance', 'N/A')}m
Track: {racecard.get('track_type', 'N/A')}
Class: {racecard.get('race_class', 'N/A')}

### HORSE ENTRIES (Race Card)
{json.dumps(racecard.get('horses', []), indent=2)}

### ANALYTICAL DATA (Sectional Times & Positions)
{json.dumps(analytical, indent=2)}

### MARKET ODDS
{json.dumps(odds, indent=2)}

### STEWARDS' REPORTS & INCIDENTS (Human Context)
{json.dumps(results.get('incidents', []), indent=2)}
Overall Report: {results.get('stewards_report', 'None available')}

### BARRIER TRIALS (Pre-race Fitness)
{json.dumps(analytical.get('trials', []), indent=2)}

### HORSE NUMBERS TO PREDICT
{horse_nos_str}

### JOCKEY-TRAINER SYNERGY STATS (Historical Combo Performance)
{json.dumps(data.get('synergy', {}), indent=2)}

### HIDDEN FORM & FORGIVENESS TAGS (Qualitative Excuses for Past Runs)
{json.dumps(data.get('hidden_form', {}), indent=2)}

### WEATHER INTELLIGENCE (Probabilistic Forecasting)
{json.dumps(data.get('weather_intel', {}), indent=2)}

### PEDIGREE INTELLIGENCE (Heritage & Track Suitability)
{json.dumps(data.get('pedigree_intel', {}), indent=2)}

AI Instruction: 
1. Correlate rainfall probability with track condition stability and heat stress probability with horse weight/fitness performance.
2. Cross-reference Weather Intelligence with Pedigree Intelligence. If P(Rain) is high, prioritize horses with 'wet_track_index' > 0.75.

### SYSTEM BIASES (Historical Error Correction)
Your past performance shows specific biases. Adjust your reasoning accordingly:
- Sectional Weighting: Multiply your perceived importance of sectional times by {self.bias_correction.get('sectional_weight_multiplier', 1.0)}.
- Synergy Weighting: Multiply your perceived importance of Jockey-Trainer synergy by {self.bias_correction.get('synergy_weight_multiplier', 1.0)}.
- Confidence Adjustment: { "Decrease" if self.bias_correction.get('confidence_bias', 0) > 0.2 else "Maintain" } your confidence score as you have shown a tendency to be over-confident.

### HISTORICAL CONTEXT (Past Performance Analysis)
Analyze the horses' recent forms (last_6_runs), their sectional positions (sectional_pos) in this race (if available as a recap), and how they handled weights (act_weight).

Detected Patterns: 
1. 'Flying Finishers': Horses that gained significant ground in the final sectional.
2. 'Pace Victims': Horses that led but faded due to fast early pace.
3. 'Forgiveable Losses': Use Stewards' Reports to identify horses that were hampered, raced wide, or had legitimate excuses for losing.
4. 'Trial Stars': Use Barrier Trial data to identify horses showing peak fitness in recent trials.

### OUTPUT REQUIREMENTS
Provide a JSON object following this structure:
{{
  "confidence_score": (float between 0.0 and 1.0),
  "is_best_bet": (boolean),
  "recommended_bet": (string, MUST include horse number, e.g., "WIN 5", "PLACE 2", "QUINELLA 1-4"),
  "probabilities": {{
    "1": 0.15,
    "2": 0.05,
    ...
  }},
  "analysis_markdown": (A detailed markdown analysis justifying your choice)
}}

CRITICAL: You MUST provide a win probability for EACH of these horse numbers: {horse_nos_str}. The sum of all probabilities MUST be 1.0.
"""
        return prompt

    async def _generate_ensemble_prediction(self, date_str: str, venue: str, race_no: int, prompt: str, data: Dict) -> Optional[Prediction]:
        """Generate prediction using ensemble of multiple models"""
        ensemble_predictor = get_ensemble_predictor()
        
        # Define response schema
        racecard = data.get("racecard", {})
        horses = racecard.get("horses", [])
        prob_props = {
            str(h.get("saddle_number") or h.get("horse_no")): {"type": "number"}
            for h in horses
        }
        
        response_schema = {
            "type": "object",
            "properties": {
                "confidence_score": {"type": "number"},
                "is_best_bet": {"type": "boolean"},
                "recommended_bet": {"type": "string"},
                "probabilities": {
                    "type": "object",
                    "properties": prob_props,
                    "required": list(prob_props.keys())
                },
                "analysis_markdown": {"type": "string"}
            },
            "required": ["confidence_score", "is_best_bet", "recommended_bet", "probabilities", "analysis_markdown"]
        }
        
        try:
            # Run ensemble prediction
            ensemble_result = await ensemble_predictor.predict_ensemble(
                prompt, response_schema, data, date_str, venue, race_no
            )
            
            # Check if ensemble should be skipped due to disagreement
            should_skip, reason = ensemble_predictor.should_skip_ensemble(ensemble_result)
            if should_skip:
                print(f"[ENSEMBLE] SKIPPED: {reason}")
                print("[ENSEMBLE] Falling back to single model prediction")
                return await self._generate_single_prediction(date_str, venue, race_no, prompt, data)
            
            # Create prediction dict from ensemble result
            prediction_dict = {
                "confidence_score": ensemble_result.ensemble_confidence,
                "is_best_bet": ensemble_result.ensemble_confidence > 0.7,
                "recommended_bet": ensemble_result.ensemble_bet,
                "probabilities": ensemble_result.ensemble_probabilities,
                "analysis_markdown": f"### Ensemble Prediction\n\n**Models Used:** {', '.join([p.model_name for p in ensemble_result.model_predictions])}\n\n**Agreement Score:** {ensemble_result.agreement_score:.2f}\n\n**Consensus Horses:** {', '.join(ensemble_result.consensus_horses) if ensemble_result.consensus_horses else 'None'}\n\n**Model Weights:** {', '.join([f'{k}: {v:.2f}' for k, v in ensemble_result.weighting_used.items()])}\n\n",
                "ensemble_metadata": ensemble_predictor.get_ensemble_summary(ensemble_result)
            }
            
            # Apply all existing enhancements (Stewards, Live Odds, etc.)
            probs = prediction_dict["probabilities"]
            
            # Apply Stewards Report Analysis
            stewards_analyzer = get_stewards_analyzer()
            racecard = data.get("racecard", {})
            stewards_reports = self._extract_stewards_reports_from_racecard(racecard)
            
            if stewards_reports:
                print(f"[STEWARDS] Analyzing {len(stewards_reports)} horse reports...")
                probs = stewards_analyzer.adjust_probabilities(probs, stewards_reports)
            
            # Apply Live Odds Integration
            live_odds_monitor = get_live_odds_monitor()
            race_id = f"{date_str}_{venue}_R{race_no}"
            odds_state = live_odds_monitor.update_race_state(date_str, venue, race_no)
            
            if odds_state and odds_state.movements:
                print(f"[LIVE ODDS] Analyzing odds movements for {race_id}")
                probs = live_odds_monitor.adjust_probabilities(probs, race_id)
            
            # Update probabilities
            prediction_dict["probabilities"] = probs
            
            # Apply distance filter
            distance = racecard.get("distance", 0)
            if distance < Config.MIN_DISTANCE or distance > Config.MAX_DISTANCE:
                print(f"Skipping race {race_id}: distance {distance}m outside range")
                probs = {}
                prediction_dict["probabilities"] = probs
            
            # Calculate Kelly stakes
            win_odds = data.get("odds", {}).get("win_odds", {})
            kelly = KellyCriterion(bankroll=self.bankroll_manager.get_current_bankroll())
            prediction_dict["kelly_stakes"] = kelly.calculate_race_stakes(probs, win_odds, racecard)
            
            # Create Prediction object
            prediction = Prediction(
                race_id=race_id,
                gemini_model="ensemble",
                **prediction_dict
            )
            
            self._save_prediction(prediction)
            return prediction
            
        except Exception as e:
            print(f"[ENSEMBLE] Error: {e}")
            print("[ENSEMBLE] Falling back to single model prediction")
            return await self._generate_single_prediction(date_str, venue, race_no, prompt, data)

    def _extract_stewards_reports_from_racecard(self, racecard: Dict) -> Dict[str, str]:
        """Extract stewards reports for each horse from racecard data"""
        stewards_reports = {}
        
        # Try to get stewards reports from racecard
        horses = racecard.get('horses', [])
        for horse in horses:
            horse_no = str(horse.get('horse_no', ''))
            # Look for stewards report in horse data
            stewards_text = horse.get('stewards_report') or horse.get('incident') or horse.get('comments', '')
            if stewards_text:
                stewards_reports[horse_no] = stewards_text
        
        # If no reports in racecard, try to get from recent results
        if not stewards_reports:
            # This would require fetching recent race results
            # For now, return empty dict
            pass
        
        return stewards_reports

    def _save_prediction(self, prediction: Prediction):
        filename = self.predictions_dir / f"prediction_{prediction.race_id}.json"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(prediction.model_dump_json(indent=2))
        print(f"Prediction saved to {filename}")
        
        # Cloud Sync (GCS Vault)
        try:
            self.storage.upload_prediction(prediction.race_id, str(filename))
        except Exception as e:
            print(f"[WARNING] GCS sync failed: {e}")

        # Cloud Sync (Firestore)
        self.firestore.upsert(Config.COL_PREDICTIONS, prediction.race_id, prediction)
        
        # Cloud Sync (BigQuery)
        try:
            # Extract basic metrics for BQ analytics
            bq_data = {
                "race_id": prediction.race_id,
                "date": prediction.race_id.split("_")[0],
                "confidence_score": float(prediction.confidence_score),
                "recommended_bet": str(prediction.recommended_bet),
                "is_best_bet": bool(prediction.is_best_bet),
                "created_at": datetime.now().isoformat()
            }
            self.bigquery.upsert_prediction(bq_data)
        except Exception as e:
            print(f"[WARNING] BigQuery sync failed: {e}")

    # Removed legacy internal Kelly logic in favor of services.kelly_criterion

if __name__ == "__main__":
    import argparse
    import asyncio
    
    parser = argparse.ArgumentParser(description="HKJC Prediction Engine")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"), help="Date in YYYY-MM-DD format")
    parser.add_argument("--venue", type=str, default="ST", help="Venue (ST or HV)")
    parser.add_argument("--race", type=int, default=1, help="Race number")
    args = parser.parse_args()

    engine = PredictionEngine()
    asyncio.run(engine.generate_prediction(args.date, args.venue, args.race))
