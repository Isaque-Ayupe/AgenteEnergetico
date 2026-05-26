"""
Skill de avaliação de conforto térmico.

Calcula um score de conforto de 0 a 100 com base na diferença entre a
temperatura interna e a ideal para o tipo de ambiente, penalidades de
umidade e ocupação, e determina o setpoint mínimo aceitável. Toda a
lógica é em Python puro, sem uso de LLM.
"""

from typing import Dict


# Temperaturas ideais por tipo de ambiente (em °C)
IDEAL_TEMPS: Dict[str, float] = {
    "classroom": 22.0,
    "lab": 21.0,
    "office": 23.0,
    "corridor": 25.0,
}

# Score mínimo aceitável para não haver violação de conforto
COMFORT_THRESHOLD: float = 40.0

# Peso da diferença de temperatura no cálculo do score
TEMP_WEIGHT: float = 8.0


def run_comfort(input_data: dict) -> dict:
    """
    Executa a avaliação de conforto térmico do ambiente.

    Calcula o score de conforto (0-100) baseado em:
        - Diferença absoluta entre temperatura interna e ideal.
        - Penalidade de umidade (10 pontos se umidade > 70%).
        - Penalidade de ocupação (5 pontos se ocupação > 30 pessoas).

    Fórmula:
        score = 100 - (delta_t × 8) - humidity_penalty - occupancy_penalty
        O score é limitado ao intervalo [0, 100].

    Violação de conforto é detectada quando o score cai abaixo de 40.

    O setpoint mínimo aceitável é calculado como o maior desvio de
    temperatura em relação ao ideal que ainda mantém o score ≥ 40.

    Args:
        input_data: Dicionário com os dados validados de entrada do ambiente.
                    Campos utilizados: environment_type, internal_temp_celsius,
                    humidity_percent, occupancy_count.

    Returns:
        Dicionário com as chaves:
            - comfort_score (float): Score de conforto de 0 a 100.
            - comfort_violation (bool): True se o score estiver abaixo de 40.
            - min_acceptable_setpoint (float): Setpoint mínimo aceitável em °C.
            - ideal_temp_celsius (float): Temperatura ideal para o tipo de ambiente.
    """
    try:
        # --- Extrair dados de entrada ---
        environment_type: str = str(
            input_data.get("environment_type", "office")
        ).lower()
        internal_temp: float = float(input_data.get("internal_temp_celsius", 23.0))
        humidity: float = float(input_data.get("humidity_percent", 50.0))
        occupancy: int = int(input_data.get("occupancy_count", 0))

        # --- Determinar temperatura ideal ---
        ideal_temp: float = IDEAL_TEMPS.get(environment_type, 23.0)

        # --- Calcular componentes do score ---
        delta_t: float = abs(internal_temp - ideal_temp)
        humidity_penalty: float = 10.0 if humidity > 70.0 else 0.0
        occupancy_penalty: float = 5.0 if occupancy > 30 else 0.0

        # --- Calcular score de conforto ---
        score: float = 100.0 - (delta_t * TEMP_WEIGHT) - humidity_penalty - occupancy_penalty

        # --- Limitar ao intervalo [0, 100] ---
        score = max(0.0, min(100.0, score))

        # --- Verificar violação de conforto ---
        comfort_violation: bool = score < COMFORT_THRESHOLD

        # --- Calcular setpoint mínimo aceitável ---
        # O setpoint mínimo aceitável é o desvio máximo que mantém score >= 40
        # score = 100 - (delta_t * 8) - humidity_penalty - occupancy_penalty >= 40
        # delta_t <= (100 - 40 - humidity_penalty - occupancy_penalty) / 8
        max_acceptable_delta: float = (
            100.0 - COMFORT_THRESHOLD - humidity_penalty - occupancy_penalty
        ) / TEMP_WEIGHT
        max_acceptable_delta = max(max_acceptable_delta, 0.0)

        # O setpoint mínimo aceitável é o limite superior do intervalo
        min_acceptable_setpoint: float = round(ideal_temp + max_acceptable_delta, 2)

        return {
            "comfort_score": round(score, 2),
            "comfort_violation": comfort_violation,
            "min_acceptable_setpoint": min_acceptable_setpoint,
            "ideal_temp_celsius": ideal_temp,
        }

    except Exception as e:
        return {
            "comfort_score": 0.0,
            "comfort_violation": True,
            "min_acceptable_setpoint": 23.0,
            "ideal_temp_celsius": 23.0,
            "error": f"Erro na avaliação de conforto: {str(e)}",
        }
