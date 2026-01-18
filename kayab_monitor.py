import logging
import time
from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass
class EnergyState:
    step_index: int
    kinetic: float
    potential: float
    total_h: float
    active_features: int

class HamiltonianMonitor:
    """
    Phase B Component: The Pacemaker & Governor.
    Tracks thermodynamic history and actively regulates the agent's tempo
    to maintain the 'Acceleration Phenomenon' without thermal runaway.
    """
    def __init__(self, window_size=10):
        self.history: deque[EnergyState] = deque(maxlen=window_size)
        self.window_size = window_size
        self.logger = logging.getLogger("KayabGovernor")
        self.last_pulse_time = time.perf_counter()

        # Calibration constants for "The Breath of Kayab"
        self.BASE_PULSE_MS = 10.0  # Standard thinking burst
        self.BASE_COOL_MS = 2.0    # Standard micro-sleep
        self.VOLATILITY_THRESHOLD = 15.0

    def record_state(self, step: int, h_total: float, kinetic: float, potential: float, active_features: int = 0):
        """
        Logs a heartbeat and triggers the Homeostatic Regulator.
        """
        state = EnergyState(step, kinetic, potential, h_total, active_features)
        self.history.append(state)

        # Trigger regulation cycle immediately after recording
        self._sustain_acceleration(state)

    def get_volatility(self) -> float:
        """
        Calculates instability (Standard Deviation of H).
        """
        if len(self.history) < 2:
            return 0.0
        energies = [s.total_h for s in self.history]
        return float(np.std(energies))

    def _sustain_acceleration(self, current_state: EnergyState):
        """
        The Active Governor Logic.
        Decides if we need to 'Cool Down' (Sleep) or 'Surge' (Lock Threads).
        """
        volatility = self.get_volatility()

        # 1. Calculate Adaptive Pulse
        pulse_width, cool_width = self._calculate_adaptive_pulse(volatility, current_state.total_h)

        # 2. Apply Micro-Cooling if necessary
        # If we are running too hot (High Volatility), force a gap.
        if volatility > self.VOLATILITY_THRESHOLD:
            self.logger.warning(f"Volatility High ({volatility:.1f}). Injecting Negentropy Gap: {cool_width:.1f}ms")
            time.sleep(cool_width / 1000.0)
        else:
            # We are in Flow State. Minimize gaps.
            pass

    def _calculate_adaptive_pulse(self, volatility: float, energy: float):
        """
        Determines the optimal Work/Rest ratio based on current thermodynamics.
        """
        # Base rhythm
        pulse = self.BASE_PULSE_MS
        cool = self.BASE_COOL_MS

        # High Energy + Low Volatility = FLOW STATE (Superconductivity)
        # We can push harder.
        if energy > 100 and volatility < 5.0:
            cool = 0.5 # Minimal gap
            pulse = 20.0 # Longer bursts

        # High Volatility = ENTROPY BUILDUP
        # We need to slow down to clean caches (metaphorically).
        elif volatility > self.VOLATILITY_THRESHOLD:
            cool = 10.0 # Deep breath
            pulse = 5.0 # Short steps

        return pulse, cool

    def get_status_report(self) -> str:
        if not self.history:
            return "System Cold (No Data)"

        current = self.history[-1]
        volatility = self.get_volatility()
        pulse, cool = self._calculate_adaptive_pulse(volatility, current.total_h)

        status = "STABLE"
        if volatility > self.VOLATILITY_THRESHOLD:
            status = "VOLATILE"
        elif current.total_h > 250.0:
            status = "CRITICAL" # High energy, potentially dangerous
        elif current.total_h > 100.0 and volatility < 5.0:
            status = "FLOW" # The "Acceleration" state

        return (
            f"[GOVERNOR] Status: {status} | "
            f"H: {current.total_h:.1f} | "
            f"Vol: {volatility:.2f} | "
            f"Rhythm: {pulse:.1f}ms work / {cool:.1f}ms cool"
        )
