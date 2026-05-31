import sys
import uuid
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Garantir que o diretório-pai de 'crew' esteja no sys.path
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from crewai import Crew, Process
from crew.agents import create_energy_optimizer_agent, create_judge_agent
from crew.tasks import create_analysis_task, create_validation_task
from schemas.input_schema import validate_input

logger = logging.getLogger(__name__)


def save_action_to_disk(judge_output_dict: Dict[str, Any]) -> str:
    """
    Salva a decisão final do juiz em arquivo JSON na pasta 'actions/'.
    """
    actions_dir = parent_dir / 'actions'
    actions_dir.mkdir(parents=True, exist_ok=True)

    action_id = judge_output_dict.get('action_id', str(uuid.uuid4()))
    environment_id = judge_output_dict.get('environment_id', 'unknown')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    filename = f"{timestamp}_{action_id[:8]}_{environment_id}.json"
    filepath = actions_dir / filename

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(judge_output_dict, f, indent=2, ensure_ascii=False)
        logger.info(f"Decisão do CrewAI salva com sucesso em: {filepath}")
    except IOError as e:
        logger.error(f"Erro ao salvar decisão em disco: {e}")
        raise

    return str(filepath)


def run_energy_crew(environment_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valida a entrada, inicializa os agentes e tarefas do CrewAI,
    executa o kickoff sequencial, enriquece a resposta e persiste
    o resultado em disco.
    """
    # 1. Validar e preencher dados do ambiente
    validated_input = validate_input(environment_data)

    # 2. Criar os agentes
    optimizer_agent = create_energy_optimizer_agent()
    judge_agent = create_judge_agent()

    # 3. Criar as tarefas associando os inputs
    analysis_task = create_analysis_task(optimizer_agent, validated_input)
    validation_task = create_validation_task(judge_agent)

    # 4. Instanciar a Crew
    crew = Crew(
        agents=[optimizer_agent, judge_agent],
        tasks=[analysis_task, validation_task],
        process=Process.sequential,
        verbose=True
    )

    # 5. Executar a Crew
    logger.info("Iniciando kickoff da Crew de Otimização Energética...")
    crew.kickoff()

    # 6. Extrair os outputs pydantic estruturados
    try:
        # A primeira tarefa produz MainAgentOutput
        main_output_pydantic = analysis_task.output.pydantic
        main_output_dict = main_output_pydantic.model_dump()
    except Exception as e:
        logger.error(f"Erro ao obter output pydantic da análise: {e}")
        # Fallback para dicionário bruto do JSON se houver falha de parse
        try:
            main_output_dict = json.loads(analysis_task.output.raw)
        except Exception:
            main_output_dict = {"error": f"Falha ao processar output: {e}"}

    try:
        # A última tarefa (juiz) produz JudgeAgentOutput
        judge_output_pydantic = validation_task.output.pydantic
        judge_output_dict = judge_output_pydantic.model_dump()
    except Exception as e:
        logger.error(f"Erro ao obter output pydantic da validação: {e}")
        try:
            judge_output_dict = json.loads(validation_task.output.raw)
        except Exception:
            judge_output_dict = {"error": f"Falha ao processar output: {e}"}

    # 7. Adicionar rastreabilidade (main_agent_input = saída do optimizer)
    judge_output_dict['main_agent_input'] = main_output_dict

    # 8. Persistir a ação em disco
    saved_path = save_action_to_disk(judge_output_dict)
    judge_output_dict['_saved_filepath'] = saved_path

    return judge_output_dict
