import json
from crewai import Task
from schemas.output_schema import MainAgentOutput, JudgeAgentOutput


def create_analysis_task(agent, environment_data: dict) -> Task:
    formatted_env = json.dumps(environment_data, indent=2, ensure_ascii=False)
    description = (
        "Você deve analisar os seguintes dados do ambiente:\n"
        f"{formatted_env}\n\n"
        "Execute o seguinte protocolo de ferramentas em ordem:\n\n"
        "1. Chame `forecast_skill` com: energy_kwh_last_24h, external_temp_celsius, "
        "calendar_event, tariff_peak.\n\n"
        "2. Chame `comfort_skill` com: environment_type, internal_temp_celsius, "
        "humidity_percent, occupancy_count.\n"
        "   ATENÇÃO: o retorno inclui 'max_setpoint_celsius' — este é o LIMITE MÁXIMO "
        "de setpoint que ainda preserva conforto mínimo (score >= 40). "
        "Nunca recomende um setpoint acima desse valor.\n\n"
        "3. Chame `optimizer_skill` com os JSONs retornados pelas duas skills acima, "
        "e com: tariff_current, tariff_peak, ac_active, lighting_active, "
        "ac_setpoint_celsius, operating_hours.\n"
        "   O campo 'urgency' no retorno será sempre um de: 'none', 'scheduled', 'immediate'.\n\n"
        "4. Chame `simulation_skill` SE E SOMENTE SE o campo 'urgency' retornado pelo "
        "optimizer for 'immediate' OU 'scheduled'. Para urgency='none', pule esta etapa.\n"
        "   Passe: optimizer_result_json (JSON do passo 3), predicted_kwh (do forecast), "
        "comfort_score (do comfort), tariff_current.\n\n"
        "5. Preencha o objeto MainAgentOutput com todos os campos:\n"
        "   - agent: 'EnergyOptimizerAgent'\n"
        "   - model: 'gemini-2.5-flash'\n"
        "   - timestamp: timestamp do ambiente\n"
        "   - environment_id: ID do ambiente\n"
        "   - skills_invoked: lista das skills efetivamente chamadas\n"
        "   - analysis: raciocínio técnico detalhado explicando cada decisão com base "
        "nos valores numéricos retornados pelas skills\n"
        "   - recommendation: objeto com os campos do optimizer (recommended_action, "
        "ac_setpoint_target, lighting_target, urgency, estimated_saving_brl, constraints_respected)\n"
        "   - skills_output: dicionário com chaves 'forecast', 'comfort', 'optimizer' e "
        "opcionalmente 'simulation', contendo os retornos brutos de cada skill chamada\n"
    )

    expected_output = (
        "Um objeto Pydantic MainAgentOutput contendo a análise completa do ambiente, "
        "a recomendação de ação energética e os retornos brutos de todas as skills executadas."
    )

    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
        output_pydantic=MainAgentOutput,
    )


def create_validation_task(agent) -> Task:
    description = (
        "Revise a análise e recomendação geradas pelo EnergyOptimizerAgent na tarefa anterior.\n\n"
        "Dados disponíveis na saída anterior:\n"
        "- skills_output.comfort.comfort_score: score de conforto (0-100)\n"
        "- skills_output.comfort.max_setpoint_celsius: limite máximo de setpoint seguro\n"
        "- skills_output.forecast.peak_risk: se há risco de pico tarifário\n"
        "- recommendation.urgency: 'none', 'scheduled' ou 'immediate'\n"
        "- recommendation.ac_setpoint_target: novo setpoint proposto (pode ser null)\n"
        "- skills_output.simulation: resultado da simulação, se disponível\n\n"
        "Regras de decisão obrigatórias:\n\n"
        "1. EXECUTE: comfort_score >= 40 E a ação não viola max_setpoint_celsius "
        "E a recomendação é coerente com o estado do ambiente.\n\n"
        "2. HOLD: a ação é prematura (urgency='none' com tarifa fora de pico) "
        "ou a simulation indicou recommendation_viable=False.\n\n"
        "3. OVERRIDE: comfort_score < 40 OU ac_setpoint_target > max_setpoint_celsius "
        "OU a recomendação é incoerente com ocupação ativa em horário de funcionamento. "
        "Neste caso, defina uma ação alternativa segura em action_taken e explique "
        "detalhadamente em override_reason.\n\n"
        "Preencha o objeto JudgeAgentOutput:\n"
        "   - agent: 'JudgeAgent'\n"
        "   - model: 'gemini-2.5-flash'\n"
        "   - timestamp: ISO atual\n"
        "   - environment_id: ID do ambiente\n"
        "   - action_id: UUID único gerado por você\n"
        "   - decision: 'execute', 'hold' ou 'override'\n"
        "   - action_taken: ação final autorizada (recommended_action, ac_setpoint_target, lighting_target)\n"
        "   - justification: texto com raciocínio baseado nos valores numéricos das skills\n"
        "   - main_agent_recommendation_accepted: True se não houve override\n"
        "   - override_reason: motivo detalhado se decision='override', senão string vazia\n"
        "   - estimated_impact: estimated_saving_brl e comfort_risk_detected\n"
    )

    expected_output = (
        "Um objeto Pydantic JudgeAgentOutput com a decisão operacional final validada, "
        "incluindo justificativa baseada em dados numéricos das skills."
    )

    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
        output_pydantic=JudgeAgentOutput,
    )
