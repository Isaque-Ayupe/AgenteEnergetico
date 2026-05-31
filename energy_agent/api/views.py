import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from crew.crew_runner import run_energy_crew

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def optimize_environment(request):
    """
    Endpoint para otimizar as configurações energéticas de um ambiente predial.
    
    Recebe um payload JSON contendo o estado atual do ambiente,
    executa a Crew de agentes especialistas e retorna a decisão
    operacional final do juiz.
    """
    try:
        # 1. Carregar payload JSON
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao decodificar JSON: {e}")
        return JsonResponse(
            {"error": "Payload inválido. Certifique-se de enviar um JSON válido."},
            status=400
        )

    # 2. Executar a CrewAI
    try:
        result = run_energy_crew(data)
        return JsonResponse(result, status=200)
    except ValueError as e:
        logger.warning(f"Erro de validação dos dados: {e}")
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        logger.error(f"Erro interno no processamento da Crew: {e}", exc_info=True)
        return JsonResponse(
            {"error": f"Erro interno durante a otimização energética: {str(e)}"},
            status=500
        )
