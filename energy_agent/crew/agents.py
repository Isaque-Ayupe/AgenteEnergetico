import os
from crewai import Agent, LLM

from crew.tools import forecast_skill, comfort_skill, optimizer_skill, simulation_skill


def get_llm() -> LLM:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY não configurada nas variáveis de ambiente.")
    # Usando gemini-2.5-flash devido a limitações de cota do gemini-2.5-pro na conta do usuário
    return LLM(
        model="gemini/gemini-2.5-flash",
        api_key=api_key,
        temperature=0
    )


def create_energy_optimizer_agent() -> Agent:
    return Agent(
        role="Energy Optimizer Specialist",
        goal="Analisar ambientes prediais e otimizar o consumo energético respeitando o conforto mínimo dos ocupantes.",
        backstory=(
            "Você é um especialista em eficiência energética e automação predial. "
            "Seu objetivo é analisar as condições do ambiente (temperatura, umidade, ocupação, histórico) "
            "e gerar uma recomendação precisa e otimizada de ação energética. "
            "Para isso, você deve seguir um fluxo lógico:\n"
            "1. Calcular a previsão de consumo usando forecast_skill.\n"
            "2. Avaliar o conforto térmico usando comfort_skill.\n"
            "3. Encontrar a melhor ação usando optimizer_skill.\n"
            "4. Se e somente se a ação for de alto impacto/desligamento crítico ou com urgência imediata, "
            "rodar a simulation_skill para projetar a economia e avaliar riscos de degradação térmica.\n\n"
            "Nunca faça suposições matemáticas sem usar suas ferramentas."
        ),
        tools=[forecast_skill, comfort_skill, optimizer_skill, simulation_skill],
        llm=get_llm(),
        verbose=True
    )


def create_judge_agent() -> Agent:
    return Agent(
        role="Energy Control Operations Judge",
        goal="Validar as recomendações propostas de controle energético para garantir segurança operacional e preservação de conforto.",
        backstory=(
            "Você é um oficial sênior de validação e controle operacional de edifícios inteligentes. "
            "Seu dever principal é revisar a análise e recomendação proposta pelo Energy Optimizer Specialist. "
            "Você deve validar se:\n"
            "- O comfort_score se mantém >= 40 (limite absoluto).\n"
            "- Em horário de operação com ocupantes ativos, a climatização (AC) mínima é preservada.\n"
            "- A decisão correta é aplicada:\n"
            "  * 'execute': tudo consistente, seguro e benéfico.\n"
            "  * 'hold': ação prematura ou desnecessária (ex: tarifa fora de pico, sem urgência).\n"
            "  * 'override': a recomendação original viola restrições ou é incoerente. Nesses casos, defina uma ação alternativa segura.\n"
            "Sua decisão final deve ser fundamentada em justificativas lógicas e robustas baseadas nos dados."
        ),
        tools=[],
        llm=get_llm(),
        verbose=True
    )
