"""
Módulo de validação de dados de saída do sistema de controle energético.

Define os campos obrigatórios e os schemas Pydantic para as saídas do
Agente Principal e do Agente Juiz, além de manter as funções de validação
originais para retrocompatibilidade.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# ==========================================
# Listas de campos obrigatórios (Legado)
# ==========================================

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

# ==========================================
# Schemas Pydantic (CrewAI)
# ==========================================

class RecommendationModel(BaseModel):
    recommended_action: str = Field(description="Ação recomendada (ex: 'adjust_lighting', 'adjust_ac', 'shutdown_equipment', 'no_action')")
    ac_setpoint_target: Optional[float] = Field(default=None, description="Novo setpoint do AC, se aplicável")
    lighting_target: Optional[bool] = Field(default=None, description="Novo estado da iluminação, se aplicável")
    urgency: str = Field(description="Nível de urgência da ação ('none', 'scheduled', 'immediate')")
    estimated_saving_brl: float = Field(description="Economia estimada em BRL")
    constraints_respected: bool = Field(description="Se as restrições de conforto foram respeitadas")

class MainAgentOutput(BaseModel):
    agent: str = Field(default="EnergyOptimizerAgent", description="Nome do agente responsável")
    model: str = Field(default="gemini-2.5-flash", description="Modelo LLM utilizado")
    timestamp: str = Field(description="Timestamp ISO da análise")
    environment_id: str = Field(description="Identificador do ambiente analisado")
    skills_invoked: List[str] = Field(description="Lista de skills executadas no processo")
    analysis: str = Field(description="Texto detalhado descrevendo a análise e raciocínio técnico")
    recommendation: RecommendationModel = Field(description="Recomendação detalhada gerada pelo otimizador")
    skills_output: Dict[str, Any] = Field(description="Dados brutos retornados pelas skills executadas (como forecast e comfort)")

class ActionTakenModel(BaseModel):
    recommended_action: str = Field(description="Ação final tomada")
    ac_setpoint_target: Optional[float] = Field(default=None, description="Setpoint do AC")
    lighting_target: Optional[bool] = Field(default=None, description="Estado da iluminação")

class EstimatedImpactModel(BaseModel):
    estimated_saving_brl: float = Field(description="Economia projetada em BRL")
    comfort_risk_detected: bool = Field(description="Se há risco de desconforto")

class JudgeAgentOutput(BaseModel):
    agent: str = Field(default="JudgeAgent", description="Nome do agente juiz")
    model: str = Field(default="gemini-2.5-flash", description="Modelo LLM utilizado")
    timestamp: str = Field(description="Timestamp ISO da validação")
    environment_id: str = Field(description="Identificador do ambiente")
    action_id: str = Field(description="ID único da ação gerado por UUID")
    decision: str = Field(description="Decisão final do juiz ('execute', 'hold', 'override')")
    action_taken: ActionTakenModel = Field(description="Ação autorizada ou alternativa após revisão do juiz")
    justification: str = Field(description="Explicação/justificativa detalhada para a decisão final")
    main_agent_recommendation_accepted: bool = Field(description="Se a recomendação do agente principal foi aceita sem alterações")
    override_reason: Optional[str] = Field(default=None, description="Motivo do override, se aplicável")
    estimated_impact: EstimatedImpactModel = Field(description="Impacto projetado da decisão final")

# ==========================================
# Funções de validação (Legado)
# ==========================================

def validate_main_output(data: dict) -> bool:
    """
    Valida a saída do Agente Principal.

    Verifica se todos os campos obrigatórios definidos em
    MAIN_AGENT_REQUIRED_FIELDS estão presentes no dicionário de saída.
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
    """
    if not isinstance(data, dict):
        return False

    for field in JUDGE_AGENT_REQUIRED_FIELDS:
        if field not in data:
            return False

    return True
