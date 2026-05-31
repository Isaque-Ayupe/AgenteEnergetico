import json
from crewai import Task
from schemas.output_schema import MainAgentOutput, JudgeAgentOutput


def create_analysis_task(agent, environment_data: dict) -> Task:
    formatted_env = json.dumps(environment_data, indent=2, ensure_ascii=False)
    description = (
        "Você deve analisar os seguintes dados do ambiente:\n"
        f"{formatted_env}\n\n"
        "Sua missão é gerar uma análise energética otimizada seguindo este protocolo de execução de ferramentas:\n"
        "1. Chame a ferramenta `forecast_skill` passando as chaves correspondentes aos parâmetros do ambiente "
        "(energy_kwh_last_24h, external_temp_celsius, calendar_event, tariff_peak).\n"
        "2. Chame a ferramenta `comfort_skill` passando as chaves do ambiente "
        "(environment_type, internal_temp_celsius, humidity_percent, occupancy_count).\n"
        "3. Chame a ferramenta `optimizer_skill` com as strings JSON completas retornadas por `forecast_skill` e `comfort_skill`, "
        "junto com as demais chaves do ambiente: tariff_current, tariff_peak, ac_active, lighting_active, ac_setpoint_celsius, operating_hours.\n"
        "4. Se a urgência (urgency) retornada pelo optimizer for 'immediate' ou a recomendação indicar uma ação crítica, "
        "chame a ferramenta `simulation_skill` com a string JSON do optimizer, predicted_kwh da previsão, comfort_score do conforto, "
        "e a tarifa atual.\n"
        "5. Reúna todos os resultados e estruture a resposta final utilizando o formato Pydantic especificado em MainAgentOutput.\n\n"
        "Certifique-se de preencher todos os campos do modelo MainAgentOutput corretamente:\n"
        "- `agent`: 'EnergyOptimizerAgent'\n"
        "- `model`: 'gemini-2.5-flash'\n"
        "- `timestamp`: o mesmo timestamp fornecido nos dados do ambiente\n"
        "- `environment_id`: o ID do ambiente\n"
        "- `skills_invoked`: a lista de nomes das ferramentas que você realmente chamou\n"
        "- `analysis`: seu texto de justificativa e raciocínio físico/técnico detalhado\n"
        "- `recommendation`: a recomendação final de ação conforme retornado pelo optimizer\n"
        "- `skills_output`: um dicionário contendo os dados de retorno das ferramentas executadas "
        "(ex: chave 'forecast' com o retorno da forecast_skill, chave 'comfort' com o retorno da comfort_skill, etc.)"
    )
    
    expected_output = (
        "Um objeto Pydantic MainAgentOutput contendo a análise do ambiente, "
        "recomendações de setpoint/iluminação e o retorno das ferramentas utilizadas."
    )
    
    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
        output_pydantic=MainAgentOutput
    )


def create_validation_task(agent) -> Task:
    description = (
        "Revisar a recomendação e a análise propostas na tarefa anterior de otimização.\n\n"
        "Como Agente Juiz, você deve emitir a sua decisão operacional baseada em regras rígidas de controle predial:\n"
        "1. Decisão ('decision'):\n"
        "   - 'execute': se a recomendação for segura e benéfica (comfort_score >= 40 e sem riscos operacionais).\n"
        "   - 'hold': se a ação for prematura ou desnecessária (ex: tarifa fora de pico, sem urgência).\n"
        "   - 'override': se a recomendação violar o conforto térmico mínimo (conforto < 40) ou for incoerente "
        "com a ocupação em horário de funcionamento. Neste caso, você DEVE propor uma ação alternativa em `action_taken` "
        "e detalhar o motivo do desvio em `override_reason`.\n"
        "2. Certifique-se de preencher os campos do modelo JudgeAgentOutput:\n"
        "   - `agent`: 'JudgeAgent'\n"
        "   - `model`: 'gemini-2.5-flash'\n"
        "   - `timestamp`: timestamp atual no formato ISO\n"
        "   - `environment_id`: ID do ambiente em análise\n"
        "   - `action_id`: UUID único gerado para esta ação\n"
        "   - `decision`: sua decisão ('execute', 'hold', 'override')\n"
        "   - `action_taken`: dicionário com as configurações finais autorizadas (recommended_action, ac_setpoint_target, lighting_target)\n"
        "   - `justification`: texto fundamentado justificando sua decisão final\n"
        "   - `main_agent_recommendation_accepted`: se você aceitou a proposta do optimizer sem alterações\n"
        "   - `override_reason`: texto justificando a mudança caso a decisão seja 'override', senão None ou vazio\n"
        "   - `estimated_impact`: dicionário com a economia projetada e se há risco detectado de conforto (comfort_risk_detected)"
    )
    
    expected_output = (
        "Um objeto Pydantic JudgeAgentOutput formalizando a validação final da recomendação, "
        "incluindo a decisão ('execute', 'hold' ou 'override') e a ação tomada definitiva."
    )
    
    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
        output_pydantic=JudgeAgentOutput
    )
