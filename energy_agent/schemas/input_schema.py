"""
Módulo de validação de dados de entrada do sistema de controle energético.

Define os valores padrão conservadores e a função de validação que preenche
campos ausentes ou nulos com valores seguros para operação do sistema.
"""

from typing import Optional
from datetime import datetime, timezone


DEFAULTS: dict = {
    "environment_id": None,
    "environment_type": "office",
    "timestamp": None,
    "internal_temp_celsius": 23.0,
    "external_temp_celsius": 25.0,
    "humidity_percent": 50.0,
    "occupancy_count": 0,
    "energy_kwh_current_hour": 0.0,
    "energy_kwh_last_24h": [0.0] * 24,
    "ac_active": False,
    "lighting_active": False,
    "ac_setpoint_celsius": 24.0,
    "tariff_current": 0.5,
    "tariff_peak": False,
    "calendar_event": None,
    "operating_hours": True,
}


def validate_input(data: dict) -> dict:
    """
    Valida e preenche os dados de entrada com valores padrão conservadores.

    Para cada campo definido em DEFAULTS, verifica se o valor está presente
    e não é None no dicionário de entrada. Caso esteja ausente ou seja None,
    o valor padrão correspondente é utilizado.

    O campo 'timestamp' recebe o horário atual em ISO 8601 (UTC) caso não
    seja fornecido.

    O campo 'energy_kwh_last_24h' é garantido como lista; caso o valor
    fornecido não seja uma lista, o padrão é utilizado.

    Args:
        data: Dicionário com os dados brutos de entrada. Todos os campos
              são opcionais e podem ser None.

    Returns:
        Dicionário validado com todos os campos preenchidos e valores
        seguros para processamento pelo sistema.
    """
    validated: dict = {}

    for field, default_value in DEFAULTS.items():
        value = data.get(field)

        if value is None:
            # Caso especial: timestamp recebe o horário atual se ausente
            if field == "timestamp":
                validated[field] = datetime.now(timezone.utc).isoformat()
            # Caso especial: energy_kwh_last_24h precisa ser uma cópia nova
            elif field == "energy_kwh_last_24h":
                validated[field] = list(default_value)
            else:
                validated[field] = default_value
        else:
            # Validação de tipo para energy_kwh_last_24h
            if field == "energy_kwh_last_24h" and not isinstance(value, list):
                validated[field] = list(DEFAULTS["energy_kwh_last_24h"])
            else:
                validated[field] = value

    return validated
