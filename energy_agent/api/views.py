import json
import logging
import os
import time
from datetime import datetime, timezone

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from crew.crew_runner import run_energy_crew

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory data structures (migrated from server.ts)
# ---------------------------------------------------------------------------

zones_list = [
    {
        "id": "zone-1",
        "name": "Admin Block A",
        "category": "Administrative Offices",
        "occupancyLabel": "Low (12%)",
        "occupancyValue": 12,
        "temp": 21,
        "tempSet": 20,
        "humidity": 45,
        "consumptionLabel": "High (45kW)",
        "consumptionValue": 45,
        "status": "INEFFICIENT",
        "aiRecommendation": "Reduce HVAC load — zone is mostly empty.",
        "statusLabel": "Inefficient Use",
    },
    {
        "id": "zone-2",
        "name": "Lab Complex C",
        "category": "Research Laboratories",
        "occupancyLabel": "Med (65%)",
        "occupancyValue": 65,
        "temp": 22,
        "tempSet": 22,
        "humidity": 50,
        "consumptionLabel": "Expected (78kW)",
        "consumptionValue": 78,
        "status": "OPTIMAL",
        "aiRecommendation": "Schedule matches occupancy. Maintaining optimal setpoint.",
        "statusLabel": "Optimal",
    },
    {
        "id": "zone-3",
        "name": "Lecture Hall 101",
        "category": "Main Classrooms",
        "occupancyLabel": "High (95%)",
        "occupancyValue": 95,
        "temp": 20,
        "tempSet": 20,
        "humidity": 55,
        "consumptionLabel": "Expected (60kW)",
        "consumptionValue": 60,
        "status": "OPTIMAL",
        "aiRecommendation": "Class in progress. Ventilation operating at standard high-occupancy mode.",
        "statusLabel": "Optimal",
    },
]

agents_list = [
    {
        "id": "agent-spending",
        "name": "Spending Control Agent",
        "type": "spending",
        "status": "OPTIMIZING",
        "estSavings": "15.4%",
        "activeRules": 12,
        "controls": [
            {
                "id": "ctrl-ac",
                "name": "Automated AC Adjustment",
                "description": "Modulate based on occupancy & outside temp",
                "enabled": True,
            },
            {
                "id": "ctrl-lights",
                "name": "Dynamic Lighting Schedules",
                "description": "Sync with academic/operational calendar",
                "enabled": True,
            },
            {
                "id": "ctrl-economy",
                "name": "Max Economy Mode",
                "description": "Prioritize savings over strict thermal comfort",
                "enabled": False,
            },
        ],
    },
    {
        "id": "agent-resilience",
        "name": "Network Resilience Agent",
        "type": "network",
        "status": "MONITORING",
        "failureRisk": 12,
        "failureRiskLabel": "Low/Moderate",
        "controls": [
            {
                "id": "ctrl-backup",
                "name": "Intelligent Generator Dispatch",
                "description": "Pre-empt power sag with backup launch",
                "enabled": True,
            },
            {
                "id": "ctrl-microgrid",
                "name": "Microgrid Peak Shaving",
                "description": "Switch to battery during critical campus peaks",
                "enabled": False,
            },
        ],
        "networkStability": [60, 75, 65, 85, 70, 95, 90, 99.9],
        "backupStatus": "STANDBY",
    },
]

alerts_list = [
    {
        "id": "alert-1",
        "title": "Spike Detected: Lab 3",
        "description": "Unusual consumption pattern detected outside academic calendar hours.",
        "type": "error",
        "timestamp": "10 mins ago",
        "isSimulated": False,
        "aiDiagnostic": "High load detected inside the cleanroom. Possibly cleanroom HVAC ventilation stuck at 100% duty cycle while lab is unoccupied.",
        "aiResolution": "Command sent to throttle cleanroom fan speeds to occupied level after 18:00.",
    },
    {
        "id": "alert-2",
        "title": "Maintenance Suggested: AHU-2",
        "description": "AC Unit B on Floor 2 showing decreased efficiency indices.",
        "type": "info",
        "timestamp": "2 hours ago",
        "isSimulated": False,
        "aiDiagnostic": "Coil temperature gradient indicates filter throttling. Energy efficiency index dropped by 8%.",
        "aiResolution": "Maintenance ticket scheduled for routine air filter replacement.",
    },
]

reports_list = [
    {
        "id": "rep-1",
        "reportType": "Managerial Overview",
        "dateGenerated": "Oct 24, 2023 • 08:00 AM",
        "tags": ["Monthly"],
        "fileType": "PDF",
    },
    {
        "id": "rep-2",
        "reportType": "Consumption Details",
        "dateGenerated": "Oct 20, 2023 • 14:30 PM",
        "tags": ["Weekly"],
        "fileType": "CSV",
    },
    {
        "id": "rep-3",
        "reportType": "Savings & Cost Reduction",
        "dateGenerated": "Oct 15, 2023 • 09:15 AM",
        "tags": ["Simulation"],
        "fileType": "PDF",
    },
]

# ---------------------------------------------------------------------------
# Gemini AI client (lazy-loaded, for error-simulation)
# ---------------------------------------------------------------------------

_ai_client = None


def _get_gemini_client():
    """Lazy-load the Google GenAI client for error simulation."""
    global _ai_client
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key or key == "MY_GEMINI_API_KEY":
        return None
    if _ai_client is None:
        try:
            from google import genai
            _ai_client = genai.Client(api_key=key)
        except Exception as exc:
            logger.error("Failed to initialise Gemini client: %s", exc)
            return None
    return _ai_client


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _make_occupancy_label(value: int) -> str:
    if value < 20:
        return f"Low ({value}%)"
    elif value < 75:
        return f"Med ({value}%)"
    return f"High ({value}%)"


def _make_consumption_label(value: int) -> str:
    if value > 60:
        return f"High ({value}kW)"
    return f"Expected ({value}kW)"


def _is_optimal(temp: float, temp_set: float, occupancy: int) -> bool:
    return abs(temp - temp_set) <= 1 and occupancy > 15


# ---------------------------------------------------------------------------
# 1. Health endpoint
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["GET"])
def health_view(request):
    return JsonResponse({"status": "ok", "time": datetime.now(timezone.utc).isoformat()})


# ---------------------------------------------------------------------------
# 2. Telemetry endpoint
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["GET"])
def telemetry_view(request):
    error_or_warn_count = sum(
        1 for a in alerts_list if a["type"] in ("error", "warn")
    )
    total_consumption = sum(z["consumptionValue"] for z in zones_list)

    data = {
        "zones": zones_list,
        "agents": agents_list,
        "alerts": alerts_list,
        "reports": reports_list,
        "stats": {
            "totalZones": len(zones_list) + 39,
            "optimizationCount": error_or_warn_count + 5,
            "currentLoadKw": total_consumption + 250,
            "comfortIndex": 92,
        },
    }
    return JsonResponse(data, safe=False)


# ---------------------------------------------------------------------------
# 3. Zones CRUD
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def create_zone(request):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    name = body.get("name")
    category = body.get("category")
    if not name or not category:
        return JsonResponse(
            {"error": "Missing required fields: name, category"}, status=400
        )

    occupancy_value = int(body.get("occupancyValue", 0))
    temp = float(body.get("temp", 22))
    temp_set = float(body.get("tempSet", 22))
    humidity = float(body.get("humidity", 50))
    consumption_value = int(body.get("consumptionValue", 45))
    optimal = _is_optimal(temp, temp_set, occupancy_value)

    new_zone = {
        "id": f"zone-{int(time.time() * 1000)}",
        "name": name,
        "category": category,
        "occupancyLabel": _make_occupancy_label(occupancy_value),
        "occupancyValue": occupancy_value,
        "temp": temp,
        "tempSet": temp_set,
        "humidity": humidity,
        "consumptionLabel": _make_consumption_label(consumption_value),
        "consumptionValue": consumption_value,
        "status": "OPTIMAL" if optimal else "INEFFICIENT",
        "aiRecommendation": (
            "Operating within range. Maintaining smart schedule."
            if optimal
            else "Adjust setpoint to match thermal load — possible waste."
        ),
        "statusLabel": "Optimal" if optimal else "Inefficient Use",
    }

    zones_list.append(new_zone)
    return JsonResponse({"success": True, "zone": new_zone}, status=201)


@csrf_exempt
@require_http_methods(["PUT", "DELETE"])
def zone_detail(request, zone_id):
    if request.method == "DELETE":
        return _delete_zone(zone_id)
    return _update_zone(request, zone_id)


def _update_zone(request, zone_id):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    name = body.get("name")
    category = body.get("category")
    if not name or not category:
        return JsonResponse(
            {"error": "Missing required fields: name, category"}, status=400
        )

    zone_index = next(
        (i for i, z in enumerate(zones_list) if z["id"] == zone_id), None
    )
    if zone_index is None:
        return JsonResponse({"error": "Zone not found"}, status=404)

    occupancy_value = int(body.get("occupancyValue", 0))
    temp = float(body.get("temp", 22))
    temp_set = float(body.get("tempSet", 22))
    humidity = float(body.get("humidity", 50))
    consumption_value = int(body.get("consumptionValue", 45))
    optimal = _is_optimal(temp, temp_set, occupancy_value)

    zones_list[zone_index].update(
        {
            "name": name,
            "category": category,
            "occupancyLabel": _make_occupancy_label(occupancy_value),
            "occupancyValue": occupancy_value,
            "temp": temp,
            "tempSet": temp_set,
            "humidity": humidity,
            "consumptionLabel": _make_consumption_label(consumption_value),
            "consumptionValue": consumption_value,
            "status": "OPTIMAL" if optimal else "INEFFICIENT",
            "aiRecommendation": (
                "Operating within range. Maintaining smart schedule."
                if optimal
                else "Adjust setpoint to match thermal load — possible waste."
            ),
            "statusLabel": "Optimal" if optimal else "Inefficient Use",
        }
    )

    return JsonResponse({"success": True, "zone": zones_list[zone_index]})


def _delete_zone(zone_id):
    global zones_list
    zones_list = [z for z in zones_list if z["id"] != zone_id]
    return JsonResponse({"success": True})


# ---------------------------------------------------------------------------
# 4. Agent toggle
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def toggle_agent_control(request):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    agent_id = body.get("agentId")
    control_id = body.get("controlId")
    enabled = body.get("enabled")

    agent = next((a for a in agents_list if a["id"] == agent_id), None)
    if not agent:
        return JsonResponse({"error": "Agent not found"}, status=404)

    ctrl = next((c for c in agent["controls"] if c["id"] == control_id), None)
    if not ctrl:
        return JsonResponse({"error": "Control setting not found"}, status=404)

    ctrl["enabled"] = enabled

    # Dynamic rules recalculation (same logic as server.ts)
    if agent_id == "agent-spending":
        agent["activeRules"] = sum(1 for c in agent["controls"] if c["enabled"]) * 4
        economy_ctrl = next(
            (c for c in agent["controls"] if c["id"] == "ctrl-economy"), None
        )
        agent["estSavings"] = (
            "21.6%" if economy_ctrl and economy_ctrl["enabled"] else "15.4%"
        )
        agent["status"] = (
            "OPTIMIZING" if any(c["enabled"] for c in agent["controls"]) else "INACTIVE"
        )
    elif agent_id == "agent-resilience":
        backup_ctrl = next(
            (c for c in agent["controls"] if c["id"] == "ctrl-backup"), None
        )
        agent["backupStatus"] = (
            "STANDBY" if backup_ctrl and backup_ctrl["enabled"] else "ACTIVE"
        )
        agent["status"] = (
            "MONITORING"
            if any(c["enabled"] for c in agent["controls"])
            else "INACTIVE"
        )

    return JsonResponse({"success": True, "agent": agent})


# ---------------------------------------------------------------------------
# 5. Error simulation (with Gemini AI)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def error_simulation(request):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    anomaly_type = body.get("anomalyType")
    zone_id = body.get("zoneId")
    severity = body.get("severity", "high")
    notes = body.get("notes", "")

    if not anomaly_type or not zone_id:
        return JsonResponse(
            {"error": "Faltando parâmetros: anomalyType ou zoneId"}, status=400
        )

    # Find target zone or use a generic fallback
    zone = next(
        (z for z in zones_list if z["id"] == zone_id),
        {"name": "Zona Campus Geral", "category": "Serviços Gerais"},
    )

    alert_id = f"sim-alert-{int(time.time() * 1000)}"
    alert_title = f"Simulação: {anomaly_type} detectado"
    alert_desc = (
        f"Comportamento anômalo na instalação {zone['name']} "
        f"({zone['category']}). severity: {severity}."
    )

    # Default AI diagnostic data
    default_diagnostic = (
        "Simulação de Anomalia de telemetria geral. Os parâmetros estão fora das metas "
        "ambientais aceitáveis, gerando desperdício e potencial desgaste do equipamento."
    )
    default_resolution = (
        "Ajuste preventivo realizado via agente EnergiAI. Redução de ganho de damper "
        "e monitoramento térmico ativo."
    )
    default_impact = (
        "Aumento esperado de 15% na economia ao conter a quebra sazonal."
    )

    ai_data = {
        "diagnostic": default_diagnostic,
        "actionTaken": default_resolution,
        "savingsImpact": default_impact,
    }
    used_ai = False

    # Try Gemini AI
    client = _get_gemini_client()
    if client:
        try:
            prompt = (
                "Analise a seguinte simulação de erro/anomalia em um prédio inteligente e gere:\n"
                "1. Um diagnóstico de engenharia detalhado (em português).\n"
                "2. Uma resolução/ação imediata recomendada ou executada automaticamente "
                "pelo agente de IA (em português).\n"
                "3. O impacto estimado de consumo de energia ou economia (em português).\n\n"
                f"Parâmetros da simulação:\n"
                f"- Tipo de anomalia: {anomaly_type}\n"
                f"- Zona climatizada: {zone['name']} ({zone['category']})\n"
                f"- Severidade: {severity}\n"
                f"- Notas adicionais: {notes or 'Nenhuma'}\n\n"
                "Retorne a resposta EXCLUSIVAMENTE em formato JSON com esses campos:\n"
                '{\n  "diagnostic": "...",\n  "actionTaken": "...",\n  "savingsImpact": "..."\n}'
            )

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                },
            )

            if response and response.text:
                result = json.loads(response.text.strip())
                ai_data = result
                used_ai = True
        except Exception as exc:
            logger.error("Erro ao chamar o Gemini API: %s", exc)

    if not used_ai:
        # Specialised fallback simulations (same as server.ts)
        if "AC" in anomaly_type or "HVAC" in anomaly_type:
            ai_data["diagnostic"] = (
                f"Superaquecimento ou sobrecarga no fan coil principal do {zone['name']}. "
                "A taxa de ocupação não justifica a demanda extrema medida."
            )
            ai_data["actionTaken"] = (
                "Comando automático de modulação de válvula fracionária enviado. "
                "Redução de vazão de água gelada em 30%."
            )
            ai_data["savingsImpact"] = (
                "Economia de contenção de pico estimada em 12kW imediatamente."
            )
        elif "Iluminação" in anomaly_type or "Luz" in anomaly_type:
            ai_data["diagnostic"] = (
                f"Luzes de emergência e salas operacionais do {zone['name']} permanecem "
                "100% ativas fora de hora, com zero movimentação registrada pelo sensor de ocupação."
            )
            ai_data["actionTaken"] = (
                "Agente disparou override forçando ciclo noturno em 10% da potência de iluminação."
            )
            ai_data["savingsImpact"] = (
                "Redução contínua de 4.5kW de consumo contínuo."
            )
        else:
            ai_data["diagnostic"] = (
                f"Aumento inesperado detectado no perfil de consumo elétrico de "
                f"suporte elétrico em {zone['name']}."
            )
            ai_data["actionTaken"] = (
                "Instanciado ciclo de mitigação de carga secundária e relatórios "
                "emitidos para equipe técnica."
            )
            ai_data["savingsImpact"] = (
                "Estabilização do sistema principal para evitar sobrecarga sob "
                "risco de fator de potência."
            )

    # Create the alert
    alert_type = "error" if severity in ("critical", "high") else "warn"
    new_alert = {
        "id": alert_id,
        "title": alert_title,
        "description": alert_desc,
        "type": alert_type,
        "timestamp": "Just now",
        "isSimulated": True,
        "aiDiagnostic": ai_data["diagnostic"],
        "aiResolution": ai_data["actionTaken"],
    }

    alerts_list.insert(0, new_alert)

    # Update the corresponding zone status
    zone_index = next(
        (i for i, z in enumerate(zones_list) if z["id"] == zone_id), None
    )
    if zone_index is not None:
        z = zones_list[zone_index]
        if severity in ("critical", "high"):
            z["status"] = "CRITICAL"
            z["statusLabel"] = "Critical Error"
        else:
            z["status"] = "INEFFICIENT"
            z["statusLabel"] = "Inefficient Use"
        z["consumptionValue"] += 30
        z["consumptionLabel"] = f"Alert ({z['consumptionValue']}kW)"
        z["aiRecommendation"] = f"AI Rec: {ai_data['actionTaken']}"

    return JsonResponse(
        {"success": True, "alert": new_alert, "aiFeedback": ai_data}
    )


# ---------------------------------------------------------------------------
# 6. Optimize environment (existing CrewAI endpoint)
# ---------------------------------------------------------------------------

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
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao decodificar JSON: {e}")
        return JsonResponse(
            {"error": "Payload inválido. Certifique-se de enviar um JSON válido."},
            status=400,
        )

    try:
        result = run_energy_crew(data)
        return JsonResponse(result, status=200)
    except ValueError as e:
        logger.warning(f"Erro de validação dos dados: {e}")
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        logger.error(
            f"Erro interno no processamento da Crew: {e}", exc_info=True
        )
        return JsonResponse(
            {"error": f"Erro interno durante a otimização energética: {str(e)}"},
            status=500,
        )
