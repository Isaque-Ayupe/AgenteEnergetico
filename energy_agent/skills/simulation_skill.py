"""
Skill de simulação de impacto energético.

Projeta o consumo energético e a economia estimada ao longo de um horizonte
de tempo, verificando se a recomendação do otimizador é viável sem degradar
o conforto. Toda a lógica é em Python puro, sem uso de LLM.
"""


def run_simulation(input_data: dict) -> dict:
    """
    Executa a simulação de impacto energético ao longo de um horizonte temporal.

    Projeta o consumo e a economia com base na taxa de economia do otimizador
    (15% de redução) aplicada ao longo do horizonte de simulação.

    Verifica se o score de conforto atual indica risco de degradação ao longo
    do tempo (score < 50 indica risco).

    Args:
        input_data: Dicionário contendo:
            - optimizer_result (dict): Resultado da skill de otimização.
            - current_state (dict): Estado atual com as chaves:
                - predicted_kwh (float): Previsão de consumo por hora em kWh.
                - comfort_score (float): Score de conforto atual (0-100).
                - tariff_current (float): Tarifa energética atual em BRL/kWh.
            - simulation_horizon_hours (int): Horizonte de simulação em horas
              (padrão: 2).

    Returns:
        Dicionário com as chaves:
            - simulation_horizon_hours (int): Horizonte utilizado na simulação.
            - projected_kwh_total (float): Consumo total projetado em kWh.
            - projected_saving_brl (float): Economia projetada em BRL.
            - comfort_risk_detected (bool): Se há risco de degradação de conforto.
            - recommendation_viable (bool): Se a recomendação é viável sem risco.
    """
    try:
        # --- Extrair dados de entrada ---
        optimizer_result: dict = input_data.get("optimizer_result", {})
        current_state: dict = input_data.get("current_state", {})

        predicted_kwh: float = float(current_state.get("predicted_kwh", 0.0))
        comfort_score: float = float(current_state.get("comfort_score", 100.0))
        tariff_current: float = float(current_state.get("tariff_current", 0.5))

        horizon: int = int(input_data.get("simulation_horizon_hours", 2))
        if horizon <= 0:
            horizon = 2

        # --- Calcular projeções ---
        saving_rate: float = 0.15  # Taxa base de economia (15%)

        # Consumo projetado por hora com a ação de economia aplicada
        projected_kwh_per_hour: float = predicted_kwh * (1.0 - saving_rate)

        # Consumo total projetado ao longo do horizonte
        projected_kwh_total: float = projected_kwh_per_hour * horizon

        # Consumo total sem economia (cenário base)
        baseline_kwh_total: float = predicted_kwh * horizon

        # Economia projetada em BRL
        projected_saving_brl: float = (
            baseline_kwh_total - projected_kwh_total
        ) * tariff_current

        # --- Avaliação de risco de conforto ---
        # Score abaixo de 50 indica risco de degradação ao longo do tempo
        comfort_risk_detected: bool = comfort_score < 50.0

        # Recomendação é viável somente se não houver risco de conforto
        recommendation_viable: bool = not comfort_risk_detected

        return {
            "simulation_horizon_hours": horizon,
            "projected_kwh_total": round(projected_kwh_total, 4),
            "projected_saving_brl": round(projected_saving_brl, 4),
            "comfort_risk_detected": comfort_risk_detected,
            "recommendation_viable": recommendation_viable,
        }

    except Exception as e:
        return {
            "simulation_horizon_hours": 2,
            "projected_kwh_total": 0.0,
            "projected_saving_brl": 0.0,
            "comfort_risk_detected": True,
            "recommendation_viable": False,
            "error": f"Erro na simulação de impacto: {str(e)}",
        }
