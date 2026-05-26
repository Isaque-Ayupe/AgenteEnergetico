"""
Ponto de entrada do Sistema de Controle Energético.

Este módulo inicializa e executa o pipeline completo:
1. Agente Principal analisa os dados do ambiente e gera recomendação
2. Agente Juiz valida a recomendação e decide a ação final
3. Resultado é salvo em disco para rastreabilidade
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env na raiz do projeto
load_dotenv(Path(__file__).resolve().parent / '.env')

from agents.main_agent import MainAgent
from agents.judge_agent import JudgeAgent   


def main():
    """
    Função principal que executa o pipeline de controle energético.

    Utiliza dados de exemplo de uma sala de aula (sala_101) para
    demonstrar o fluxo completo: análise pelo Agente Principal,
    validação pelo Agente Juiz e persistência da decisão.
    """
    sample_input = {
        'environment_id': 'sala_101',
        'environment_type': 'classroom',
        'timestamp': '2025-05-25T14:30:00-03:00',
        'internal_temp_celsius': 27.5,
        'external_temp_celsius': 32.0,
        'humidity_percent': 68.0,
        'occupancy_count': 35,
        'energy_kwh_current_hour': 4.2,
        'energy_kwh_last_24h': [
            1.1, 0.9, 0.8, 0.7, 0.6, 0.8, 1.2, 2.1, 3.5, 4.0,
            4.3, 4.1, 3.9, 4.2, 4.5, 4.3, 3.8, 3.2, 2.5, 2.0,
            1.8, 1.5, 1.3, 1.1,
        ],
        'ac_active': True,
        'lighting_active': True,
        'ac_setpoint_celsius': 24.0,
        'tariff_current': 0.85,
        'tariff_peak': True,
        'calendar_event': 'class',
        'operating_hours': True,
    }

    print('=' * 60)
    print('SISTEMA DE CONTROLE ENERGÉTICO')
    print('=' * 60)

    # Etapa 1: Agente Principal
    print('\n[1/3] Executando Agente Principal...')
    main_agent = MainAgent()
    main_output = main_agent.run(sample_input)
    print('\n--- MainAgentOutput ---')
    print(json.dumps(main_output, indent=2, ensure_ascii=False))

    # Etapa 2: Agente Juiz
    print('\n[2/3] Executando Agente Juiz...')
    judge_agent = JudgeAgent()
    judge_output = judge_agent.run(main_output)
    print('\n--- JudgeAgentOutput ---')
    print(json.dumps(judge_output, indent=2, ensure_ascii=False))

    # Etapa 3: Confirmação de salvamento
    print('\n[3/3] Ação registrada com sucesso!')
    print(f'Arquivo salvo em: {judge_output.get("_saved_filepath", "N/A")}')
    print('\n' + '=' * 60)


if __name__ == '__main__':
    main()
