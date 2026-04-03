#!/usr/bin/env python3
"""
Startup script for Bias Optimization Scheduler
Can be run as a service or standalone
"""

import sys
import os
import signal
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from services.bias_scheduler import get_bias_scheduler

class BiasSchedulerService:
    """Service wrapper for bias scheduler"""
    
    def __init__(self):
        self.scheduler = get_bias_scheduler()
        self.running = False
    
    async def start(self):
        """Start the scheduler service"""
        print("Starting Bias Optimization Scheduler Service...")
        print("Press Ctrl+C to stop")
        print("-" * 50)
        
        self.running = True
        
        # Set up signal handlers
        def signal_handler(signum, frame):
            print("\nReceived stop signal, shutting down...")
            self.running = False
            self.scheduler.stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            # Start the scheduler
            await self.scheduler.start()
        except KeyboardInterrupt:
            print("\nStopped by user")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            print("Bias Scheduler Service stopped")
    
    def stop(self):
        """Stop the scheduler service"""
        self.running = False
        self.scheduler.stop()

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Bias Scheduler Service")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--config", help="Update configuration")
    
    args = parser.parse_args()
    
    scheduler = get_bias_scheduler()
    
    if args.status:
        status = scheduler.get_status()
        print("Bias Scheduler Status:")
        print("=" * 50)
        for key, value in status.items():
            print(f"{key:20}: {value}")
        return
    
    if args.config:
        if '=' in args.config:
            key, value = args.config.split('=', 1)
            scheduler.update_config(**{key: value})
            print(f"Updated configuration: {key} = {value}")
        else:
            print("Config must be in key=value format")
        return
    
    # Start the service
    service = BiasSchedulerService()
    
    if args.daemon:
        # TODO: Implement daemon mode for production
        print("Daemon mode not yet implemented")
        sys.exit(1)
    else:
        # Run in foreground
        asyncio.run(service.start())

if __name__ == "__main__":
    main()
