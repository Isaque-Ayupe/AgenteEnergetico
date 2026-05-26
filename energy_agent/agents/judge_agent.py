"""
Agente Juiz do Sistema de Controle Energético.

Este módulo implementa o Agente Juiz que recebe a análise e recomendação
do Agente Principal e decide se a ação deve ser executada, mantida em
espera ou sobrescrita. Utiliza o SDK google-genai com o modelo Gemini 2.5 Pro
em uma única chamada (sem chamadas de função).
"""

import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Garantir que o diretório raiz do projeto esteja no sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google import genai
from google.genai import types

from schemas.output_schema import validate_judge_output

logger = logging.getLogger(__name__)


class JudgeAgent:
    """
    Agente Juiz de Controle Energético.

    Responsável por validar as recomendações do Agente Principal,
    verificando conforto, coerência e urgência antes de autorizar,
    reter ou sobrescrever a ação recomendada.
    """

    SYSTEM_PROMPT = (
        "Você é o Agente Juiz do sistema de controle energético. "
        "Você recebe a análise e recomendação do Agente Principal e "
        "decide se a ação deve ser executada, mantida em espera ou "
        "sobrescrita.\n\n"
        "Suas responsabilidades:\n"
        "1. Verificar se a recomendação respeita o conforto mínimo dos "
        "ocupantes (comfort_score >= 40)\n"
        "2. Verificar se a ação é coerente com o estado atual descrito "
        "(ex: não desligar AC se há ocupação e temperatura alta)\n"
        "3. Verificar se a urgência declarada condiz com o risk_level "
        "informado\n"
        "4. Se tudo estiver consistente: decisão = \"execute\"\n"
        "5. Se a ação for desnecessária ou prematura: decisão = \"hold\"\n"
        "6. Se houver incoerência ou risco ao conforto: decisão = "
        "\"override\" com ação alternativa segura\n\n"
        "Regras absolutas:\n"
        "- NUNCA autorize uma ação que reduza comfort_score abaixo de 40\n"
        "- Se operating_hours == true e occupancy_count > 0, sempre "
        "preserve AC mínimo (não desligue)\n"
        "- Se risk_level == \"low\" e tariff_peak == false: decisão "
        "padrão é \"hold\" ou \"no_action\"\n\n"
        "Seu retorno DEVE ser sempre um JSON válido e completo conforme "
        "o schema JudgeAgentOutput."
    )

    def __init__(self):
        """Inicializa o cliente genai e configura o modelo."""
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise EnvironmentError(
                "Variável de ambiente 'GEMINI_API_KEY' não encontrada. "
                "Defina-a antes de executar o agente."
            )
        self.client = genai.Client(api_key=api_key)
        self.model = 'gemini-2.5-flash'

    def _extract_json(self, text: str) -> dict:
        """
        Extrai um objeto JSON de uma resposta textual do modelo.

        Tenta as seguintes estratégias em ordem:
        1. json.loads no texto completo
        2. Bloco de código ```json ... ```
        3. Primeiro objeto JSON entre { e }

        Args:
            text: Texto bruto da resposta do modelo.

        Retorna:
            Dicionário Python extraído do JSON.

        Raises:
            ValueError: Se não for possível extrair JSON válido.
        """
        # Estratégia 1: texto completo
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        # Estratégia 2: bloco ```json ... ```
        match = re.search(r'```json\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Estratégia 3: primeiro objeto { ... }
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        raise ValueError(
            "Não foi possível extrair JSON válido da resposta do modelo. "
            f"Resposta recebida: {text[:500]}"
        )

    def save_action(self, judge_output: dict) -> str:
        """
        Persiste a decisão do Agente Juiz em arquivo JSON no diretório de ações.

        O arquivo é salvo em 'actions/' relativo à raiz do projeto, com
        nomenclatura: {timestamp}_{action_id[:8]}_{environment_id}.json

        Args:
            judge_output: Dicionário com a saída completa do Agente Juiz.

        Retorna:
            Caminho absoluto do arquivo salvo como string.
        """
        # Diretório de ações relativo à raiz do projeto
        actions_dir = Path(__file__).resolve().parent.parent / 'actions'
        actions_dir.mkdir(parents=True, exist_ok=True)

        # Extrair ou gerar action_id
        action_id = judge_output.get('action_id', str(uuid.uuid4()))

        # Extrair environment_id (pode estar no output ou no main_agent_input)
        environment_id = judge_output.get('environment_id', 'unknown')
        if environment_id == 'unknown':
            main_input = judge_output.get('main_agent_input', {})
            environment_id = main_input.get('environment_id', 'unknown')

        # Gerar timestamp para o nome do arquivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Montar nome do arquivo
        filename = f"{timestamp}_{action_id[:8]}_{environment_id}.json"
        filepath = actions_dir / filename

        # Salvar arquivo
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(judge_output, f, indent=2, ensure_ascii=False)
            logger.info("Ação salva em: %s", filepath)
        except IOError as e:
            logger.error("Erro ao salvar ação em disco: %s", e)
            raise

        return str(filepath)

    def run(self, main_agent_output: dict) -> dict:
        """
        Executa o Agente Juiz para validar a recomendação do Agente Principal.

        Envia a saída do Agente Principal ao Gemini em uma única chamada
        (sem ferramentas) e retorna a decisão do juiz. Inclui retry
        automático caso a extração de JSON falhe na primeira tentativa.

        Args:
            main_agent_output: Dicionário com a saída do Agente Principal
                               (conforme MainAgentOutput schema).

        Retorna:
            Dicionário com a decisão do Agente Juiz, incluindo
            rastreabilidade via campo 'main_agent_input' e o caminho
            do arquivo salvo em '_saved_filepath'.
        """
        # Construir mensagem do usuário com os dados do Agente Principal
        user_prompt = (
            "Analise a recomendação do Agente Principal abaixo e emita "
            "sua decisão como Agente Juiz. Retorne um JSON válido conforme "
            "o schema JudgeAgentOutput.\n\n"
            "Saída do Agente Principal:\n"
            f"{json.dumps(main_agent_output, indent=2, ensure_ascii=False)}"
        )

        messages = [
            types.Content(
                role='user',
                parts=[types.Part.from_text(text=user_prompt)],
            )
        ]

        # Primeira tentativa
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=messages,
                config=types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_PROMPT,
                    temperature=0,
                ),
            )
        except Exception as e:
            logger.error("Erro na chamada ao modelo Gemini (Juiz): %s", e)
            raise RuntimeError(
                f"Erro ao comunicar com o modelo Gemini (Agente Juiz): {e}"
            ) from e

        # Tentar extrair JSON da resposta
        try:
            judge_output = self._extract_json(response.text)
        except ValueError:
            logger.warning(
                "Primeira tentativa de extração de JSON falhou. "
                "Realizando retry com instrução de correção."
            )

            # Retry: adicionar resposta original e mensagem de correção
            messages.append(response.candidates[0].content)
            messages.append(
                types.Content(
                    role='user',
                    parts=[types.Part.from_text(
                        text='Seu retorno não é um JSON válido. Corrija e '
                        'retorne apenas o JSON, sem markdown, sem explicações.'
                    )],
                )
            )

            try:
                retry_response = self.client.models.generate_content(
                    model=self.model,
                    contents=messages,
                    config=types.GenerateContentConfig(
                        system_instruction=self.SYSTEM_PROMPT,
                        temperature=0,
                    ),
                )
                judge_output = self._extract_json(retry_response.text)
            except Exception as e:
                logger.error(
                    "Falha na segunda tentativa de extração de JSON: %s", e
                )
                raise ValueError(
                    "Não foi possível obter JSON válido do Agente Juiz "
                    f"após retry: {e}"
                ) from e

        # Adicionar rastreabilidade: entrada do agente principal
        judge_output['main_agent_input'] = main_agent_output

        # Validar saída do juiz
        try:
            validate_judge_output(judge_output)
        except Exception as e:
            logger.warning(
                "Saída do Agente Juiz não passou na validação do schema: %s", e
            )

        # Salvar ação em disco
        try:
            saved_filepath = self.save_action(judge_output)
            judge_output['_saved_filepath'] = saved_filepath
        except Exception as e:
            logger.error("Erro ao salvar ação: %s", e)
            judge_output['_saved_filepath'] = f"Erro ao salvar: {e}"

        logger.info("Agente Juiz concluiu com sucesso.")
        return judge_output
