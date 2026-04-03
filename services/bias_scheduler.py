"""
Bias Optimization Scheduler
Runs bias optimization at scheduled times and after meetings
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional
from loguru import logger
import asyncio
from dataclasses import dataclass

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.auto_bias_optimizer import get_auto_bias_optimizer
from config.settings import Config

@dataclass
class ScheduleConfig:
    """Configuration for scheduled optimization runs"""
    enabled: bool = True
    run_after_meeting: bool = True
    run_daily_at: Optional[time] = time(23, 30)  # 11:30 PM
    run_weekly_at: Optional[time] = time(22, 0)   # 10:00 PM
    weekly_day: int = 0  # Monday = 0
    min_races_threshold: int = 3

class BiasScheduler:
    """
    Scheduler for automated bias optimization.
    Runs optimization at configured times and after meetings complete.
    """
    
    def __init__(self, config: Optional[ScheduleConfig] = None):
        self.config = config or ScheduleConfig()
        self.auto_optimizer = get_auto_bias_optimizer()
        self.base_dir = Config.BASE_DIR
        self.config_file = self.base_dir / "data/bias_scheduler_config.json"
        
        # Load configuration
        self.load_config()
        
        # State tracking
        self.last_daily_run: Optional[datetime] = None
        self.last_weekly_run: Optional[datetime] = None
        self.running = False
        
        logger.info("Bias Scheduler initialized")
    
    def load_config(self):
        """Load scheduler configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                
                # Update config with loaded values
                if 'enabled' in data:
                    self.config.enabled = data['enabled']
                if 'run_after_meeting' in data:
                    self.config.run_after_meeting = data['run_after_meeting']
                if 'run_daily_at' in data:
                    if data['run_daily_at']:
                        hour, minute = map(int, data['run_daily_at'].split(':'))
                        self.config.run_daily_at = time(hour, minute)
                    else:
                        self.config.run_daily_at = None
                if 'run_weekly_at' in data:
                    if data['run_weekly_at']:
                        hour, minute = map(int, data['run_weekly_at'].split(':'))
                        self.config.run_weekly_at = time(hour, minute)
                    else:
                        self.config.run_weekly_at = None
                if 'weekly_day' in data:
                    self.config.weekly_day = data['weekly_day']
                if 'min_races_threshold' in data:
                    self.config.min_races_threshold = data['min_races_threshold']
                
                logger.info(f"Loaded scheduler config from {self.config_file}")
                
            except Exception as e:
                logger.warning(f"Failed to load scheduler config: {e}")
    
    def save_config(self):
        """Save scheduler configuration to file"""
        try:
            data = {
                'enabled': self.config.enabled,
                'run_after_meeting': self.config.run_after_meeting,
                'run_daily_at': self.config.run_daily_at.strftime('%H:%M') if self.config.run_daily_at else None,
                'run_weekly_at': self.config.run_weekly_at.strftime('%H:%M') if self.config.run_weekly_at else None,
                'weekly_day': self.config.weekly_day,
                'min_races_threshold': self.config.min_races_threshold
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved scheduler config to {self.config_file}")
            
        except Exception as e:
            logger.error(f"Failed to save scheduler config: {e}")
    
    async def start(self):
        """Start the scheduler"""
        if not self.config.enabled:
            logger.info("Bias scheduler is disabled")
            return
        
        self.running = True
        logger.info("Starting bias scheduler")
        
        # Start different scheduler components
        tasks = []
        
        if self.config.run_after_meeting:
            tasks.append(asyncio.create_task(self._meeting_monitor()))
        
        if self.config.run_daily_at:
            tasks.append(asyncio.create_task(self._daily_scheduler()))
        
        if self.config.run_weekly_at:
            tasks.append(asyncio.create_task(self._weekly_scheduler()))
        
        # Run all tasks
        await asyncio.gather(*tasks)
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        logger.info("Bias scheduler stopped")
    
    async def _meeting_monitor(self):
        """Monitor for completed meetings and run optimization"""
        logger.info("Starting meeting monitor (runs every 5 minutes)")
        
        while self.running:
            try:
                # Check for completed meetings
                await self.auto_optimizer.check_and_optimize()
                await asyncio.sleep(5 * 60)  # Check every 5 minutes
            except Exception as e:
                logger.error(f"Error in meeting monitor: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def _daily_scheduler(self):
        """Run daily optimization at specified time"""
        logger.info(f"Starting daily scheduler (runs at {self.config.run_daily_at})")
        
        while self.running:
            try:
                now = datetime.now()
                scheduled_time = datetime.combine(now.date(), self.config.run_daily_at)
                
                # If scheduled time has passed today, schedule for tomorrow
                if now > scheduled_time:
                    scheduled_time += timedelta(days=1)
                
                # Wait until scheduled time
                sleep_seconds = (scheduled_time - now).total_seconds()
                logger.debug(f"Daily optimization scheduled in {sleep_seconds/3600:.1f} hours")
                
                await asyncio.sleep(sleep_seconds)
                
                # Run daily optimization
                if self.running:
                    await self._run_daily_optimization()
                
            except Exception as e:
                logger.error(f"Error in daily scheduler: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour before retrying
    
    async def _weekly_scheduler(self):
        """Run weekly optimization at specified time and day"""
        logger.info(f"Starting weekly scheduler (runs {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][self.config.weekly_day]} at {self.config.run_weekly_at})")
        
        while self.running:
            try:
                now = datetime.now()
                
                # Find next scheduled day/time
                days_until_weekly = (self.config.weekly_day - now.weekday()) % 7
                if days_until_weekly == 0 and now.time() > self.config.run_weekly_at:
                    days_until_weekly = 7  # Next week
                
                next_run = now + timedelta(days=days_until_weekly)
                scheduled_time = datetime.combine(next_run.date(), self.config.run_weekly_at)
                
                # Wait until scheduled time
                sleep_seconds = (scheduled_time - now).total_seconds()
                logger.debug(f"Weekly optimization scheduled in {sleep_seconds/86400:.1f} days")
                
                await asyncio.sleep(sleep_seconds)
                
                # Run weekly optimization
                if self.running:
                    await self._run_weekly_optimization()
                
            except Exception as e:
                logger.error(f"Error in weekly scheduler: {e}")
                await asyncio.sleep(86400)  # Wait 1 day before retrying
    
    async def _run_daily_optimization(self):
        """Run daily optimization"""
        logger.info("Running daily bias optimization")
        
        try:
            success = await self.auto_optimizer.optimize_now(days=7)
            
            if success:
                self.last_daily_run = datetime.now()
                logger.info("Daily optimization completed successfully")
            else:
                logger.warning("Daily optimization failed")
                
        except Exception as e:
            logger.error(f"Error in daily optimization: {e}")
    
    async def _run_weekly_optimization(self):
        """Run weekly optimization with more data"""
        logger.info("Running weekly bias optimization (30-day window)")
        
        try:
            success = await self.auto_optimizer.optimize_now(days=30)
            
            if success:
                self.last_weekly_run = datetime.now()
                logger.info("Weekly optimization completed successfully")
            else:
                logger.warning("Weekly optimization failed")
                
        except Exception as e:
            logger.error(f"Error in weekly optimization: {e}")
    
    def get_status(self) -> Dict:
        """Get current scheduler status"""
        return {
            'enabled': self.config.enabled,
            'running': self.running,
            'run_after_meeting': self.config.run_after_meeting,
            'daily_time': self.config.run_daily_at.strftime('%H:%M') if self.config.run_daily_at else None,
            'weekly_time': self.config.run_weekly_at.strftime('%H:%M') if self.config.run_weekly_at else None,
            'weekly_day': ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][self.config.weekly_day],
            'last_daily_run': self.last_daily_run.isoformat() if self.last_daily_run else None,
            'last_weekly_run': self.last_weekly_run.isoformat() if self.last_weekly_run else None,
            'min_races_threshold': self.config.min_races_threshold
        }
    
    def update_config(self, **kwargs):
        """Update scheduler configuration"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"Updated scheduler config: {key} = {value}")
        
        self.save_config()

# Singleton instance
_scheduler = None

def get_bias_scheduler() -> BiasScheduler:
    """Get the global bias scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = BiasScheduler()
    return _scheduler

# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Bias Optimization Scheduler")
    parser.add_argument("--start", action="store_true", help="Start the scheduler")
    parser.add_argument("--status", action="store_true", help="Show scheduler status")
    parser.add_argument("--enable", action="store_true", help="Enable scheduler")
    parser.add_argument("--disable", action="store_true", help="Disable scheduler")
    parser.add_argument("--config", help="Update config (key=value format)")
    
    args = parser.parse_args()
    
    scheduler = get_bias_scheduler()
    
    if args.start:
        asyncio.run(scheduler.start())
    elif args.status:
        status = scheduler.get_status()
        print("Scheduler Status:")
        for key, value in status.items():
            print(f"  {key}: {value}")
    elif args.enable:
        scheduler.update_config(enabled=True)
        print("Scheduler enabled")
    elif args.disable:
        scheduler.update_config(enabled=False)
        print("Scheduler disabled")
    elif args.config:
        if '=' in args.config:
            key, value = args.config.split('=', 1)
            try:
                # Convert value to appropriate type
                if value.lower() in ['true', 'false']:
                    value = value.lower() == 'true'
                elif ':' in value:
                    hour, minute = map(int, value.split(':'))
                    value = time(hour, minute)
                elif value.isdigit():
                    value = int(value)
                
                scheduler.update_config(**{key: value})
                print(f"Updated {key} = {value}")
            except Exception as e:
                print(f"Error updating config: {e}")
        else:
            print("Config must be in key=value format")
    else:
        print("Please specify an action: --start, --status, --enable, --disable, --config")
