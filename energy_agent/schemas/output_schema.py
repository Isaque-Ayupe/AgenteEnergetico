"""
Módulo de validação de dados de saída do sistema de controle energético.

Define os campos obrigatórios para as saídas do Agente Principal e do
Agente Juiz, além de funções de validação que verificam a presença de
todos os campos requeridos.
"""

from typing import List


MAIN_AGENT_REQUIRED_FIELDS: List[str] = [
    "agent",
    "model",
    "timestamp",
    "environment_id",
    "skills_invoked",
    "analysis",
    "recommendation",
    "skills_output",
]

JUDGE_AGENT_REQUIRED_FIELDS: List[str] = [
    "agent",
    "model",
    "timestamp",
    "environment_id",
    "action_id",
    "decision",
    "action_taken",
    "justification",
    "main_agent_recommendation_accepted",
    "override_reason",
    "estimated_impact",
]


def validate_main_output(data: dict) -> bool:
    """
    Valida a saída do Agente Principal.

    Verifica se todos os campos obrigatórios definidos em
    MAIN_AGENT_REQUIRED_FIELDS estão presentes no dicionário de saída.

    Args:
        data: Dicionário contendo a saída gerada pelo Agente Principal.

    Returns:
        True se todos os campos obrigatórios estiverem presentes,
        False caso contrário.
    """
    if not isinstance(data, dict):
        return False

    for field in MAIN_AGENT_REQUIRED_FIELDS:
        if field not in data:
            return False

    return True


def validate_judge_output(data: dict) -> bool:
    """
    Valida a saída do Agente Juiz.

    Verifica se todos os campos obrigatórios definidos em
    JUDGE_AGENT_REQUIRED_FIELDS estão presentes no dicionário de saída.

    Args:
        data: Dicionário contendo a saída gerada pelo Agente Juiz.

    Returns:
        True se todos os campos obrigatórios estiverem presentes,
        False caso contrário.
    """
    if not isinstance(data, dict):
        return False

    for field in JUDGE_AGENT_REQUIRED_FIELDS:
        if field not in data:
            return False

    return True
