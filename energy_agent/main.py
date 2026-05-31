"""
Ponto de entrada do Sistema de Controle Energético com CrewAI.

Este módulo inicializa e executa o pipeline completo utilizando a orquestração do CrewAI:
1. Otimizador analisa e invoca ferramentas de previsão, conforto e simulação.
2. Juiz valida o resultado e define a decisão operacional final.
3. A decisão enriquecida é salva em disco.
"""

import json
import sys
from pathlib import Path
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env
load_dotenv(Path(__file__).resolve().parent / '.env')

from crew.crew_runner import run_energy_crew


def main():
    """
    Função principal que executa o pipeline de controle energético com CrewAI.
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
    print('SISTEMA DE CONTROLE ENERGÉTICO (CREWAI)')
    print('=' * 60)

    print('\nExecutando a Crew de Otimização e Validação...')
    try:
        final_output = run_energy_crew(sample_input)
        
        print('\n' + '=' * 60)
        print('DECISÃO FINAL DO JUIZ')
        print('=' * 60)
        print(json.dumps(final_output, indent=2, ensure_ascii=False))
        print('=' * 60)
        print(f"Decisão: {final_output.get('decision')}")
        print(f"Arquivo salvo: {final_output.get('_saved_filepath')}")
        print('=' * 60)
    except Exception as e:
        print(f"\nErro durante a execução: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
