"""
Agente Principal do Sistema de Controle Energético.

Este módulo implementa o Agente Principal que utiliza o SDK google-genai
com o modelo Gemini 2.5 Pro para orquestrar quatro skills de energia
(previsão, conforto, otimização e simulação) via chamadas de função
em um loop agêntico.
"""

import json
import logging
import os
import re
import sys
from pathlib import Path

# Garantir que o diretório raiz do projeto esteja no sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google import genai
from google.genai import types

from skills.forecast_skill import run_forecast
from skills.comfort_skill import run_comfort
from skills.optimizer_skill import run_optimizer
from skills.simulation_skill import run_simulation
from schemas.input_schema import validate_input
from schemas.output_schema import validate_main_output

logger = logging.getLogger(__name__)


class MainAgent:
    """
    Agente Principal de Controle Energético.

    Responsável por analisar os dados de cada ambiente e produzir
    recomendações de ação utilizando quatro skills especializadas
    via chamadas de função do Gemini.
    """

    SYSTEM_PROMPT = (
        "Você é o Agente de Controle Energético responsável por otimizar "
        "o consumo de energia em edifícios institucionais.\n\n"
        "Seu objetivo é analisar os dados recebidos de cada ambiente e "
        "produzir uma recomendação precisa de ação.\n\n"
        "Você possui 4 skills disponíveis como ferramentas:\n"
        "- forecast_skill: prevê o consumo de energia para a próxima hora "
        "com base no histórico\n"
        "- comfort_skill: calcula o índice de conforto térmico PMV do ambiente\n"
        "- optimizer_skill: gera a recomendação de menor custo que preserva "
        "conforto mínimo\n"
        "- simulation_skill: simula o impacto da ação antes de recomendá-la "
        "(use apenas quando urgency for \"immediate\" ou risk_level for \"high\")\n\n"
        "Regras de decisão:\n"
        "1. Sempre execute forecast_skill e comfort_skill antes das demais\n"
        "2. Execute optimizer_skill após obter os resultados de forecast e comfort\n"
        "3. Execute simulation_skill somente se o risco for alto ou a ação for imediata\n"
        "4. Se os dados estiverem incompletos, assuma valores conservadores "
        "(conforto = 50, previsão = média histórica disponível)\n"
        "5. Nunca recomende ações que violem o conforto mínimo (comfort_score < 40)\n"
        "6. Seu retorno DEVE ser sempre um JSON válido e completo conforme "
        "o schema MainAgentOutput"
    )

    MAX_ITERATIONS = 10

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

    def _build_tools(self) -> list:
        """
        Constrói e retorna as declarações de ferramentas (tools) do agente.

        Retorna:
            Lista de types.Tool com as 4 skills declaradas.
        """
        tools = [
            types.Tool(function_declarations=[
                types.FunctionDeclaration(
                    name='forecast_skill',
                    description=(
                        'Prevê o consumo de energia (kWh) para a próxima hora '
                        'com base no histórico das últimas 24h, temperatura '
                        'externa, tipo de sala e calendário.'
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            'energy_kwh_last_24h': types.Schema(
                                type=types.Type.ARRAY,
                                items=types.Schema(type=types.Type.NUMBER),
                            ),
                            'external_temp_celsius': types.Schema(
                                type=types.Type.NUMBER,
                            ),
                            'environment_type': types.Schema(
                                type=types.Type.STRING,
                            ),
                            'calendar_event': types.Schema(
                                type=types.Type.STRING,
                            ),
                            'tariff_peak': types.Schema(
                                type=types.Type.BOOLEAN,
                            ),
                        },
                        required=['energy_kwh_last_24h'],
                    ),
                ),
                types.FunctionDeclaration(
                    name='comfort_skill',
                    description=(
                        'Calcula o índice de conforto térmico PMV do ambiente. '
                        'Retorna score de 0 a 100 e flag de violação.'
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            'internal_temp_celsius': types.Schema(
                                type=types.Type.NUMBER,
                            ),
                            'humidity_percent': types.Schema(
                                type=types.Type.NUMBER,
                            ),
                            'occupancy_count': types.Schema(
                                type=types.Type.INTEGER,
                            ),
                            'ac_setpoint_celsius': types.Schema(
                                type=types.Type.NUMBER,
                            ),
                            'environment_type': types.Schema(
                                type=types.Type.STRING,
                            ),
                        },
                        required=['internal_temp_celsius', 'humidity_percent'],
                    ),
                ),
                types.FunctionDeclaration(
                    name='optimizer_skill',
                    description=(
                        'Gera a recomendação de ação de menor custo energético '
                        'que ainda preserve o conforto mínimo. Recebe resultado '
                        'do forecast e comfort.'
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            'forecast_result': types.Schema(
                                type=types.Type.OBJECT,
                                properties={},
                            ),
                            'comfort_result': types.Schema(
                                type=types.Type.OBJECT,
                                properties={},
                            ),
                            'tariff_current': types.Schema(
                                type=types.Type.NUMBER,
                            ),
                            'tariff_peak': types.Schema(
                                type=types.Type.BOOLEAN,
                            ),
                            'ac_active': types.Schema(
                                type=types.Type.BOOLEAN,
                            ),
                            'lighting_active': types.Schema(
                                type=types.Type.BOOLEAN,
                            ),
                            'ac_setpoint_celsius': types.Schema(
                                type=types.Type.NUMBER,
                            ),
                            'operating_hours': types.Schema(
                                type=types.Type.BOOLEAN,
                            ),
                        },
                        required=[
                            'forecast_result',
                            'comfort_result',
                            'tariff_current',
                        ],
                    ),
                ),
                types.FunctionDeclaration(
                    name='simulation_skill',
                    description=(
                        'Simula o impacto da ação recomendada pelo optimizer '
                        'antes da execução real. Use apenas quando '
                        'urgency=immediate ou risk_level=high.'
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            'optimizer_result': types.Schema(
                                type=types.Type.OBJECT,
                                properties={},
                            ),
                            'current_state': types.Schema(
                                type=types.Type.OBJECT,
                                properties={},
                            ),
                            'simulation_horizon_hours': types.Schema(
                                type=types.Type.INTEGER,
                            ),
                        },
                        required=['optimizer_result', 'current_state'],
                    ),
                ),
            ])
        ]
        return tools

    def _dispatch_tool(self, name: str, args: dict) -> dict:
        """
        Despacha a chamada de ferramenta para a skill correspondente.

        Args:
            name: Nome da ferramenta a ser executada.
            args: Argumentos da chamada de ferramenta.

        Retorna:
            Resultado da execução da skill como dicionário.

        Raises:
            ValueError: Se o nome da ferramenta for desconhecido.
        """
        dispatch_map = {
            'forecast_skill': run_forecast,
            'comfort_skill': run_comfort,
            'optimizer_skill': run_optimizer,
            'simulation_skill': run_simulation,
        }

        if name not in dispatch_map:
            raise ValueError(f"Ferramenta desconhecida: '{name}'")

        logger.info("Executando skill: %s", name)
        try:
            result = dispatch_map[name](args)
            logger.info("Skill '%s' executada com sucesso.", name)
            return result
        except Exception as e:
            error_msg = f"Erro ao executar skill '{name}': {e}"
            logger.error(error_msg)
            return {'error': error_msg}

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

    def run(self, input_data: dict) -> dict:
        """
        Executa o loop agêntico principal do Agente de Controle Energético.

        Valida os dados de entrada, envia ao modelo Gemini com as ferramentas
        disponíveis e processa chamadas de função iterativamente até obter
        a resposta final em JSON.

        Args:
            input_data: Dados do ambiente a ser analisado.

        Retorna:
            Dicionário com a saída do agente conforme MainAgentOutput schema.

        Raises:
            RuntimeError: Se o loop agêntico exceder o máximo de iterações.
        """
        # 1. Validar entrada
        try:
            validated_input = validate_input(input_data)
        except Exception as e:
            raise ValueError(
                f"Erro na validação dos dados de entrada: {e}"
            ) from e

        # 2. Construir prompt do usuário
        user_prompt = (
            "Analise os dados do ambiente abaixo e produza a recomendação "
            "de ação energética. Retorne um JSON válido conforme o schema "
            "MainAgentOutput.\n\n"
            f"Dados do ambiente:\n{json.dumps(validated_input, indent=2, ensure_ascii=False)}"
        )

        # 3. Inicializar mensagens
        messages = [
            types.Content(
                role='user',
                parts=[types.Part.from_text(text=user_prompt)],
            )
        ]

        # 4. Construir ferramentas
        tools = self._build_tools()

        # 5. Loop agêntico
        for iteration in range(self.MAX_ITERATIONS):
            logger.info(
                "Iteração %d/%d do loop agêntico",
                iteration + 1,
                self.MAX_ITERATIONS,
            )

            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=messages,
                    config=types.GenerateContentConfig(
                        system_instruction=self.SYSTEM_PROMPT,
                        tools=tools,
                        temperature=0,
                    ),
                )
            except Exception as e:
                logger.error("Erro na chamada ao modelo Gemini: %s", e)
                raise RuntimeError(
                    f"Erro ao comunicar com o modelo Gemini: {e}"
                ) from e

            # 5a. Verificar chamadas de função
            if response.function_calls:
                # Adicionar resposta do modelo ao histórico
                messages.append(response.candidates[0].content)

                # Processar cada chamada de função
                function_response_parts = []
                for call in response.function_calls:
                    tool_name = call.name
                    tool_args = dict(call.args)
                    logger.info(
                        "Modelo solicitou ferramenta: %s", tool_name
                    )

                    result = self._dispatch_tool(tool_name, tool_args)
                    function_response_parts.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response={'result': result},
                        )
                    )

                # Adicionar resultados das funções ao histórico
                messages.append(
                    types.Content(role='user', parts=function_response_parts)
                )
                continue

            # 5b. Sem chamadas de função → resposta final
            try:
                output = self._extract_json(response.text)
            except ValueError as e:
                logger.error("Falha ao extrair JSON da resposta: %s", e)
                raise

            # Validar saída
            try:
                validate_main_output(output)
            except Exception as e:
                logger.warning(
                    "Saída do agente não passou na validação do schema: %s", e
                )

            logger.info("Agente Principal concluiu com sucesso.")
            return output

        # Loop esgotado
        raise RuntimeError(
            f"O loop agêntico excedeu o limite de {self.MAX_ITERATIONS} "
            "iterações sem produzir uma resposta final."
        )
