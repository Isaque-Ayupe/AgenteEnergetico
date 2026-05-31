import json
import sys
from pathlib import Path
from typing import List, Optional

# Garantir que o diretório-pai de 'crew' esteja no sys.path para importar skills
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from crewai.tools import tool
from skills.forecast_skill import run_forecast
from skills.comfort_skill import run_comfort
from skills.optimizer_skill import run_optimizer
from skills.simulation_skill import run_simulation


@tool("forecast_skill")
def forecast_skill(
    energy_kwh_last_24h: List[float],
    external_temp_celsius: float = 25.0,
    calendar_event: Optional[str] = None,
    tariff_peak: bool = False
) -> str:
    """Prevê o consumo de energia (kWh) para a próxima hora com base no histórico das últimas 24h, temperatura externa, eventos de calendário e pico de tarifa.
    Retorna um JSON string com predicted_kwh_next_hour, confidence, peak_risk e baseline_avg_kwh.
    """
    input_data = {
        "energy_kwh_last_24h": energy_kwh_last_24h,
        "external_temp_celsius": external_temp_celsius,
        "calendar_event": calendar_event,
        "tariff_peak": tariff_peak
    }
    result = run_forecast(input_data)
    return json.dumps(result, ensure_ascii=False)


@tool("comfort_skill")
def comfort_skill(
    environment_type: str = "office",
    internal_temp_celsius: float = 23.0,
    humidity_percent: float = 50.0,
    occupancy_count: int = 0
) -> str:
    """Calcula o índice de conforto térmico do ambiente.
    Retorna um JSON string com comfort_score, comfort_violation, min_acceptable_setpoint e ideal_temp_celsius.
    """
    input_data = {
        "environment_type": environment_type,
        "internal_temp_celsius": internal_temp_celsius,
        "humidity_percent": humidity_percent,
        "occupancy_count": occupancy_count
    }
    result = run_comfort(input_data)
    return json.dumps(result, ensure_ascii=False)


@tool("optimizer_skill")
def optimizer_skill(
    forecast_result_json: str,
    comfort_result_json: str,
    tariff_current: float = 0.5,
    tariff_peak: bool = False,
    ac_active: bool = False,
    lighting_active: bool = False,
    ac_setpoint_celsius: float = 24.0,
    operating_hours: bool = True
) -> str:
    """Gera a recomendação de ação de menor custo energético que ainda preserve o conforto mínimo.
    Recebe os resultados anteriores de forecast_skill e comfort_skill em formato JSON string.
    Retorna um JSON string com recommended_action, ac_setpoint_target, lighting_target, urgency, estimated_saving_brl e constraints_respected.
    """
    try:
        forecast_result = json.loads(forecast_result_json)
    except Exception:
        forecast_result = {}
    try:
        comfort_result = json.loads(comfort_result_json)
    except Exception:
        comfort_result = {}

    input_data = {
        "forecast_result": forecast_result,
        "comfort_result": comfort_result,
        "tariff_current": tariff_current,
        "tariff_peak": tariff_peak,
        "ac_active": ac_active,
        "lighting_active": lighting_active,
        "ac_setpoint_celsius": ac_setpoint_celsius,
        "operating_hours": operating_hours
    }
    result = run_optimizer(input_data)
    return json.dumps(result, ensure_ascii=False)


@tool("simulation_skill")
def simulation_skill(
    optimizer_result_json: str,
    predicted_kwh: float,
    comfort_score: float,
    tariff_current: float,
    simulation_horizon_hours: int = 2
) -> str:
    """Simula o impacto da ação recomendada pelo optimizer antes da execução real.
    Deve ser usada apenas quando urgency for 'immediate' ou a ação recomendada for de desligamento ou ajuste crítico.
    Retorna um JSON string com simulation_horizon_hours, projected_kwh_total, projected_saving_brl, comfort_risk_detected e recommendation_viable.
    """
    try:
        optimizer_result = json.loads(optimizer_result_json)
    except Exception:
        optimizer_result = {}

    input_data = {
        "optimizer_result": optimizer_result,
        "current_state": {
            "predicted_kwh": predicted_kwh,
            "comfort_score": comfort_score,
            "tariff_current": tariff_current
        },
        "simulation_horizon_hours": simulation_horizon_hours
    }
    result = run_simulation(input_data)
    return json.dumps(result, ensure_ascii=False)
