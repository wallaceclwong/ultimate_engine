"""
Automated Bias Optimizer Service
Automatically runs bias optimization after each meeting completes
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from loguru import logger
import asyncio
from dataclasses import dataclass

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Config
from services.rl_optimizer import RLOptimizer
from services.firestore_service import FirestoreService

@dataclass
class MeetingInfo:
    """Information about a race meeting"""
    date: str
    venue: str
    total_races: int
    completed_races: int
    status: str  # 'in_progress', 'completed', 'scheduled'

class AutoBiasOptimizer:
    """
    Automatically optimizes biases after race meetings complete.
    Monitors race completion and triggers optimization.
    """
    
    def __init__(self):
        self.base_dir = Config.BASE_DIR
        self.predictions_dir = self.base_dir / "data/predictions"
        self.results_dir = self.base_dir / "data/results"
        self.rl_optimizer = RLOptimizer()
        self.firestore = FirestoreService()
        
        # Configuration
        self.min_races_for_optimization = 3  # Minimum races to trigger optimization
        self.optimization_window_days = 7   # Days of data to analyze
        
        # Tracking
        self.last_check_time = datetime.now()
        self.processed_meetings: Set[str] = set()
        
        logger.info("Auto Bias Optimizer initialized")
    
    async def start_monitoring(self, check_interval_minutes: int = 5):
        """
        Start continuous monitoring for completed meetings.
        
        Args:
            check_interval_minutes: How often to check for completed meetings
        """
        logger.info(f"Starting auto bias optimization monitoring (check every {check_interval_minutes} minutes)")
        
        while True:
            try:
                await self.check_and_optimize()
                await asyncio.sleep(check_interval_minutes * 60)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def check_and_optimize(self):
        """Check for completed meetings and run optimization if needed"""
        logger.debug("Checking for completed meetings...")
        
        # Get all recent meetings
        meetings = await self.get_recent_meetings()
        
        for meeting in meetings:
            meeting_key = f"{meeting.date}_{meeting.venue}"
            
            # Skip if already processed
            if meeting_key in self.processed_meetings:
                continue
            
            # Check if meeting is complete
            if meeting.status == 'completed' and meeting.completed_races >= self.min_races_for_optimization:
                logger.info(f"Meeting completed: {meeting.date} {meeting.venue} ({meeting.completed_races} races)")
                
                # Run optimization
                success = await self.optimize_for_meeting(meeting)
                
                if success:
                    self.processed_meetings.add(meeting_key)
                    logger.info(f"Successfully optimized biases for {meeting_key}")
                else:
                    logger.warning(f"Failed to optimize biases for {meeting_key}")
    
    async def get_recent_meetings(self) -> List[MeetingInfo]:
        """Get information about recent race meetings"""
        meetings = []
        
        # Get recent dates (last 3 days)
        dates = []
        for i in range(3):
            date = datetime.now() - timedelta(days=i)
            dates.append(date.strftime("%Y-%m-%d"))
        
        for date_str in dates:
            # Check both venues
            for venue in ["ST", "HV"]:
                meeting = await self.get_meeting_info(date_str, venue)
                if meeting:
                    meetings.append(meeting)
        
        return meetings
    
    async def get_meeting_info(self, date_str: str, venue: str) -> Optional[MeetingInfo]:
        """Get detailed information about a specific meeting"""
        try:
            # Count prediction files
            pred_pattern = f"prediction_{date_str}_{venue}_R*.json"
            prediction_files = list(self.predictions_dir.glob(pred_pattern))
            
            # Count result files
            result_pattern = f"results_{date_str}_{venue}_R*.json"
            result_files = list(self.results_dir.glob(result_pattern))
            
            total_races = len(prediction_files)
            completed_races = len(result_files)
            
            # Determine status
            if completed_races == 0:
                status = 'scheduled'
            elif completed_races < total_races:
                status = 'in_progress'
            else:
                status = 'completed'
            
            return MeetingInfo(
                date=date_str,
                venue=venue,
                total_races=total_races,
                completed_races=completed_races,
                status=status
            )
            
        except Exception as e:
            logger.debug(f"Error getting meeting info for {date_str} {venue}: {e}")
            return None
    
    async def optimize_for_meeting(self, meeting: MeetingInfo) -> bool:
        """
        Run bias optimization for a specific meeting.
        
        Args:
            meeting: The meeting information
            
        Returns:
            True if optimization succeeded, False otherwise
        """
        try:
            logger.info(f"Running bias optimization for {meeting.date} {meeting.venue}")
            
            # Get prediction files for the optimization window
            prediction_files = self.get_prediction_files_for_window(self.optimization_window_days)
            
            if not prediction_files:
                logger.warning("No prediction files found for optimization window")
                return False
            
            # Run the optimization
            self.rl_optimizer.optimize_from_subset(prediction_files)
            
            # Log results
            await self.log_optimization_results(meeting)
            
            return True
            
        except Exception as e:
            logger.error(f"Error optimizing for meeting {meeting.date} {meeting.venue}: {e}")
            return False
    
    def get_prediction_files_for_window(self, days: int) -> List[Path]:
        """Get prediction files within the optimization window"""
        prediction_files = []
        
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            
            # Get files for both venues
            for venue in ["ST", "HV"]:
                pattern = f"prediction_{date_str}_{venue}_R*.json"
                files = list(self.predictions_dir.glob(pattern))
                prediction_files.extend(files)
        
        return prediction_files
    
    async def log_optimization_results(self, meeting: MeetingInfo):
        """Log optimization results to Firestore for monitoring"""
        try:
            # Read current bias data
            with open(self.rl_optimizer.bias_path, 'r') as f:
                bias_data = json.load(f)
            
            # Create log entry
            log_entry = {
                'meeting_date': meeting.date,
                'venue': meeting.venue,
                'races_completed': meeting.completed_races,
                'optimization_time': datetime.now().isoformat(),
                'bias_adjustments': bias_data.get('adjustments', {}),
                'contextual_adjustments': bias_data.get('contextual', {}),
                'metadata': bias_data.get('metadata', {})
            }
            
            # Save to Firestore
            self.firestore.upsert(
                collection='bias_optimization_logs',
                document_id=f"{meeting.date}_{meeting.venue}",
                data=log_entry
            )
            
            logger.info(f"Optimization results logged to Firestore")
            
        except Exception as e:
            logger.warning(f"Failed to log optimization results: {e}")
    
    async def optimize_now(self, days: int = 7) -> bool:
        """
        Manually trigger optimization for the past N days.
        
        Args:
            days: Number of past days to analyze
            
        Returns:
            True if optimization succeeded
        """
        logger.info(f"Manual optimization triggered for past {days} days")
        
        try:
            self.rl_optimizer.optimize_from_past_days(days)
            logger.info("Manual optimization completed successfully")
            return True
        except Exception as e:
            logger.error(f"Manual optimization failed: {e}")
            return False

# Singleton instance
_auto_optimizer = None

def get_auto_bias_optimizer() -> AutoBiasOptimizer:
    """Get the global auto bias optimizer instance"""
    global _auto_optimizer
    if _auto_optimizer is None:
        _auto_optimizer = AutoBiasOptimizer()
    return _auto_optimizer

# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Automated Bias Optimizer")
    parser.add_argument("--monitor", action="store_true", help="Start continuous monitoring")
    parser.add_argument("--interval", type=int, default=5, help="Check interval in minutes (for --monitor)")
    parser.add_argument("--optimize", action="store_true", help="Run optimization now")
    parser.add_argument("--days", type=int, default=7, help="Days to analyze (for --optimize)")
    
    args = parser.parse_args()
    
    async def main():
        optimizer = get_auto_bias_optimizer()
        
        if args.monitor:
            await optimizer.start_monitoring(args.interval)
        elif args.optimize:
            success = await optimizer.optimize_now(args.days)
            if success:
                print("✓ Optimization completed successfully")
            else:
                print("✗ Optimization failed")
        else:
            print("Please specify either --monitor or --optimize")
    
    asyncio.run(main())
