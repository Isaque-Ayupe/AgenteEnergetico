"""
Skill de otimização energética.

Combina os resultados de previsão e conforto para recomendar ações de
economia de energia respeitando as restrições de conforto, horário de
operação e tarifação. Toda a lógica é em Python puro, sem uso de LLM.
"""

from typing import Optional


def run_optimizer(input_data: dict) -> dict:
    """
    Executa a otimização energética com base nos resultados de previsão e conforto.

    Lógica de decisão (em ordem de prioridade):
        1. Se há violação de conforto: prioriza conforto, não reduz AC.
           Ação: 'no_action', urgência: 'none'.
        2. Se fora do horário de operação: recomenda desligamento.
           Ação: 'shutdown_equipment', urgência: 'immediate'.
        3. Se risco de pico e score de conforto ≥ 60: reduz setpoint em 1°C.
           Ação: 'adjust_ac', urgência: 'moderate'.
        4. Se risco de pico e score de conforto < 60: reduz iluminação.
           Ação: 'adjust_lighting', urgência: 'moderate'.
        5. Caso padrão: nenhuma ação necessária.
           Ação: 'no_action', urgência: 'none'.

    Economia estimada: predicted_kwh × 0.15 × tariff_current.

    Args:
        input_data: Dicionário contendo:
            - forecast_result (dict): Resultado da skill de previsão.
            - comfort_result (dict): Resultado da skill de conforto.
            - tariff_current (float): Tarifa energética atual em BRL/kWh.
            - tariff_peak (bool): Indicador de horário de pico tarifário.
            - ac_active (bool): Estado atual do ar-condicionado.
            - lighting_active (bool): Estado atual da iluminação.
            - ac_setpoint_celsius (float): Setpoint atual do AC em °C.
            - operating_hours (bool): Se o ambiente está em horário de operação.

    Returns:
        Dicionário com as chaves:
            - recommended_action (str): Ação recomendada.
            - ac_setpoint_target (float|None): Novo setpoint do AC, se aplicável.
            - lighting_target (bool|None): Novo estado da iluminação, se aplicável.
            - urgency (str): Nível de urgência ('none', 'scheduled', 'immediate').
            - estimated_saving_brl (float): Economia estimada em BRL.
            - constraints_respected (bool): Se as restrições de conforto foram respeitadas.
    """
    try:
        # --- Extrair resultados das skills anteriores ---
        forecast_result: dict = input_data.get("forecast_result", {})
        comfort_result: dict = input_data.get("comfort_result", {})

        # --- Extrair parâmetros de operação ---
        tariff_current: float = float(input_data.get("tariff_current", 0.5))
        tariff_peak: bool = bool(input_data.get("tariff_peak", False))
        ac_active: bool = bool(input_data.get("ac_active", False))
        lighting_active: bool = bool(input_data.get("lighting_active", False))
        ac_setpoint: float = float(input_data.get("ac_setpoint_celsius", 24.0))
        operating_hours: bool = bool(input_data.get("operating_hours", True))

        # --- Extrair métricas das skills ---
        predicted_kwh: float = float(forecast_result.get("predicted_kwh_next_hour", 0.0))
        peak_risk: bool = bool(forecast_result.get("peak_risk", False))
        comfort_score: float = float(comfort_result.get("comfort_score", 100.0))
        comfort_violation: bool = bool(comfort_result.get("comfort_violation", False))

        # --- Valores padrão para a resposta ---
        recommended_action: str = "no_action"
        ac_setpoint_target: Optional[float] = None
        lighting_target: Optional[bool] = None
        urgency: str = "none"
        constraints_respected: bool = True

        # --- Lógica de decisão por prioridade ---

        # 1. Violação de conforto: priorizar conforto, não reduzir AC
        if comfort_violation:
            recommended_action = "no_action"
            urgency = "none"
            constraints_respected = True

        # 2. Fora do horário de operação: desligar equipamentos
        elif not operating_hours:
            recommended_action = "shutdown_equipment"
            urgency = "immediate"
            ac_setpoint_target = None
            lighting_target = False
            constraints_respected = True

        # 3. Risco de pico com conforto adequado (≥ 60): ajustar AC
        elif peak_risk and comfort_score >= 60.0:
            recommended_action = "adjust_ac"
            ac_setpoint_target = ac_setpoint - 1.0
            urgency = "scheduled"
            constraints_respected = True

        # 4. Risco de pico com conforto baixo (< 60): ajustar iluminação
        elif peak_risk and comfort_score < 60.0:
            if lighting_active:
                recommended_action = "adjust_lighting"
                lighting_target = False
                urgency = "scheduled"
                constraints_respected = True
            else:
                # Iluminação já desligada, sem ação possível sem violar conforto
                recommended_action = "no_action"
                urgency = "none"
                constraints_respected = True

        # 5. Caso padrão: sem ação necessária
        else:
            recommended_action = "no_action"
            urgency = "none"
            constraints_respected = True

        # --- Calcular economia estimada ---
        saving_rate: float = 0.15
        estimated_saving_brl: float = predicted_kwh * saving_rate * tariff_current

        return {
            "recommended_action": recommended_action,
            "ac_setpoint_target": ac_setpoint_target,
            "lighting_target": lighting_target,
            "urgency": urgency,
            "estimated_saving_brl": round(estimated_saving_brl, 4),
            "constraints_respected": constraints_respected,
        }

    except Exception as e:
        return {
            "recommended_action": "no_action",
            "ac_setpoint_target": None,
            "lighting_target": None,
            "urgency": "none",
            "estimated_saving_brl": 0.0,
            "constraints_respected": True,
            "error": f"Erro na otimização energética: {str(e)}",
        }
