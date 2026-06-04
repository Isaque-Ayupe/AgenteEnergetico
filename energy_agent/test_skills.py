"""Script de teste unitário das skills."""
import sys
import json
sys.path.insert(0, '.')

from skills.forecast_skill import run_forecast
from skills.comfort_skill import run_comfort
from skills.optimizer_skill import run_optimizer
from skills.simulation_skill import run_simulation
from schemas.input_schema import validate_input
from schemas.output_schema import validate_main_output, validate_judge_output

sample_input = {
    'environment_id': 'sala_101',
    'environment_type': 'classroom',
    'timestamp': '2025-05-25T14:30:00-03:00',
    'internal_temp_celsius': 27.5,
    'external_temp_celsius': 32.0,
    'humidity_percent': 68.0,
    'occupancy_count': 35,
    'energy_kwh_current_hour': 4.2,
    'energy_kwh_last_24h': [1.1, 0.9, 0.8, 0.7, 0.6, 0.8, 1.2, 2.1, 3.5, 4.0,
                             4.3, 4.1, 3.9, 4.2, 4.5, 4.3, 3.8, 3.2, 2.5, 2.0,
                             1.8, 1.5, 1.3, 1.1],
    'ac_active': True,
    'lighting_active': True,
    'ac_setpoint_celsius': 24.0,
    'tariff_current': 0.85,
    'tariff_peak': True,
    'calendar_event': 'class',
    'operating_hours': True
}

print("=" * 50)
print("TESTE DAS SKILLS")
print("=" * 50)

# 1. Validate input
validated = validate_input(sample_input)
print("\n[OK] validate_input executado")

# 2. Forecast
forecast = run_forecast(validated)
print("\n=== FORECAST ===")
print(json.dumps(forecast, indent=2))
assert "predicted_kwh_next_hour" in forecast
assert "confidence" in forecast
assert forecast["confidence"] == "high"  # 24 data points
assert forecast["peak_risk"] == True
print("[OK] forecast_skill validado")

# 3. Comfort
comfort = run_comfort(validated)
print("\n=== COMFORT ===")
print(json.dumps(comfort, indent=2))
assert "comfort_score" in comfort
assert "comfort_violation" in comfort
assert "max_setpoint_celsius" in comfort
assert comfort["ideal_temp_celsius"] == 22.0  # classroom
print("[OK] comfort_skill validado")

# 4. Optimizer
optimizer_input = {
    'forecast_result': forecast,
    'comfort_result': comfort,
    'tariff_current': validated['tariff_current'],
    'tariff_peak': validated['tariff_peak'],
    'ac_active': validated['ac_active'],
    'lighting_active': validated['lighting_active'],
    'ac_setpoint_celsius': validated['ac_setpoint_celsius'],
    'operating_hours': validated['operating_hours']
}
optimizer = run_optimizer(optimizer_input)
print("\n=== OPTIMIZER ===")
print(json.dumps(optimizer, indent=2))
assert "recommended_action" in optimizer
assert optimizer["urgency"] in ("immediate", "scheduled", "none")
print("[OK] optimizer_skill validado")

# 5. Simulation
sim_input = {
    'optimizer_result': optimizer,
    'current_state': {
        'predicted_kwh': forecast['predicted_kwh_next_hour'],
        'comfort_score': comfort['comfort_score'],
        'tariff_current': validated['tariff_current']
    },
    'simulation_horizon_hours': 2
}
simulation = run_simulation(sim_input)
print("\n=== SIMULATION ===")
print(json.dumps(simulation, indent=2))
assert "recommendation_viable" in simulation
assert "projected_saving_brl" in simulation
print("[OK] simulation_skill validado")

print("\n" + "=" * 50)
print("TODOS OS TESTES PASSARAM!")
print("=" * 50)
