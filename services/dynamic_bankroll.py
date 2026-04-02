"""
Dynamic Bankroll Adjustment Module

Automatically adjusts Kelly fraction based on recent performance.
If bankroll grows significantly, slightly increase Kelly for compound growth.
If bankroll shrinks, reduce Kelly for capital preservation.
"""
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.settings import Config
from services.bankroll_manager import BankrollManager


class DynamicBankrollAdjuster:
    def __init__(self):
        self.bankroll_manager = BankrollManager()
        self.initial_bankroll = Config.INITIAL_BANKROLL
        self.base_kelly = Config.KELLY_FRACTION
        
    def get_adjusted_kelly_fraction(self) -> float:
        """
        Returns dynamically adjusted Kelly fraction based on bankroll performance.
        
        Rules:
        - If bankroll > initial * 1.3: Increase Kelly by 20% (max 0.15)
        - If bankroll > initial * 1.1: Increase Kelly by 10% (max 0.12)
        - If bankroll < initial * 0.8: Decrease Kelly by 30% (min 0.05)
        - If bankroll < initial * 0.9: Decrease Kelly by 15% (min 0.07)
        - Otherwise: Use base Kelly
        """
        current = self.bankroll_manager.get_current_bankroll()
        ratio = current / self.initial_bankroll
        
        if ratio >= 1.3:
            # Strong performance - compound growth
            adjusted = min(0.15, self.base_kelly * 1.2)
            print(f"[DYNAMIC KELLY] Bankroll up {(ratio-1)*100:.1f}% → Kelly increased to {adjusted:.3f}")
            return adjusted
        
        elif ratio >= 1.1:
            # Good performance - slight increase
            adjusted = min(0.12, self.base_kelly * 1.1)
            print(f"[DYNAMIC KELLY] Bankroll up {(ratio-1)*100:.1f}% → Kelly increased to {adjusted:.3f}")
            return adjusted
        
        elif ratio <= 0.8:
            # Poor performance - capital preservation
            adjusted = max(0.05, self.base_kelly * 0.7)
            print(f"[DYNAMIC KELLY] Bankroll down {(1-ratio)*100:.1f}% → Kelly reduced to {adjusted:.3f}")
            return adjusted
        
        elif ratio <= 0.9:
            # Slight drawdown - reduce risk
            adjusted = max(0.07, self.base_kelly * 0.85)
            print(f"[DYNAMIC KELLY] Bankroll down {(1-ratio)*100:.1f}% → Kelly reduced to {adjusted:.3f}")
            return adjusted
        
        else:
            # Normal range - use base Kelly
            return self.base_kelly
    
    def should_pause_betting(self) -> bool:
        """
        Returns True if bankroll has dropped significantly and betting should pause.
        """
        current = self.bankroll_manager.get_current_bankroll()
        ratio = current / self.initial_bankroll
        
        if ratio < 0.5:
            print(f"[DYNAMIC KELLY] BETTING PAUSED: Bankroll down {(1-ratio)*100:.1f}%")
            return True
        
        return False


if __name__ == "__main__":
    adjuster = DynamicBankrollAdjuster()
    kelly = adjuster.get_adjusted_kelly_fraction()
    paused = adjuster.should_pause_betting()
    
    print(f"\nCurrent bankroll: ${adjuster.bankroll_manager.get_current_bankroll():,.2f}")
    print(f"Initial bankroll: ${adjuster.initial_bankroll:,.2f}")
    print(f"Adjusted Kelly: {kelly:.3f}")
    print(f"Betting paused: {paused}")
