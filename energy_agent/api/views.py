import json
import logging
import time
import uuid
from datetime import datetime, timezone

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from api.models import Zone, Agent, AgentControl, Alert, Report
from crew.crew_runner import run_energy_crew

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers de serialização
# ---------------------------------------------------------------------------

def _serialize_zone(z: Zone) -> dict:
    return {
        "id": z.zone_id,
        "name": z.name,
        "category": z.category,
        "occupancyLabel": z.occupancy_label,
        "occupancyValue": z.occupancy_value,
        "temp": z.temp,
        "tempSet": z.temp_set,
        "humidity": z.humidity,
        "consumptionLabel": z.consumption_label,
        "consumptionValue": z.consumption_value,
        "status": z.status,
        "statusLabel": z.status_label,
        "aiRecommendation": z.ai_recommendation,
    }


def _serialize_agent(a: Agent) -> dict:
    controls = [
        {
            "id": c.control_id,
            "name": c.name,
            "description": c.description,
            "enabled": c.enabled,
        }
        for c in a.controls.all()
    ]
    base = {
        "id": a.agent_id,
        "name": a.name,
        "type": a.agent_type,
        "status": a.status,
        "controls": controls,
    }
    if a.agent_type == "spending":
        base["estSavings"] = a.est_savings
        base["activeRules"] = a.active_rules
    elif a.agent_type == "network":
        base["failureRisk"] = a.failure_risk
        base["failureRiskLabel"] = a.failure_risk_label
        base["backupStatus"] = a.backup_status
        base["networkStability"] = a.network_stability
    return base


def _serialize_alert(al: Alert) -> dict:
    return {
        "id": al.alert_id,
        "title": al.title,
        "description": al.description,
        "type": al.alert_type,
        "timestamp": al.timestamp_label,
        "isSimulated": al.is_simulated,
        "aiDiagnostic": al.ai_diagnostic,
        "aiResolution": al.ai_resolution,
    }


def _serialize_report(r: Report) -> dict:
    return {
        "id": r.report_id,
        "reportType": r.report_type,
        "dateGenerated": r.date_generated,
        "tags": r.tags,
        "fileType": r.file_type,
    }


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
# Dynamic Database Seeder
# ---------------------------------------------------------------------------

def _auto_seed_db():
    """Populates the database dynamically if it is empty (no agents defined)."""
    if Agent.objects.exists():
        return

    # Create agents and controls
    spending_agent = Agent.objects.create(
        agent_id="agent-spending",
        name="Spending Control Agent",
        agent_type="spending",
        status=Agent.Status.OPTIMIZING,
        est_savings="15.4%",
        active_rules=12
    )
    AgentControl.objects.create(
        agent=spending_agent,
        control_id="ctrl-ac",
        name="Automated AC Adjustment",
        description="Modulate based on occupancy & outside temp",
        enabled=True
    )
    AgentControl.objects.create(
        agent=spending_agent,
        control_id="ctrl-lights",
        name="Dynamic Lighting Schedules",
        description="Sync with academic/operational calendar",
        enabled=True
    )
    AgentControl.objects.create(
        agent=spending_agent,
        control_id="ctrl-economy",
        name="Max Economy Mode",
        description="Prioritize savings over strict thermal comfort",
        enabled=False
    )

    resilience_agent = Agent.objects.create(
        agent_id="agent-resilience",
        name="Network Resilience Agent",
        agent_type="network",
        status=Agent.Status.MONITORING,
        failure_risk=12,
        failure_risk_label="Low/Moderate",
        backup_status="STANDBY",
        network_stability=[60, 75, 65, 85, 70, 95, 90, 99.9]
    )
    AgentControl.objects.create(
        agent=resilience_agent,
        control_id="ctrl-backup",
        name="Intelligent Generator Dispatch",
        description="Pre-empt power sag with backup launch",
        enabled=True
    )
    AgentControl.objects.create(
        agent=resilience_agent,
        control_id="ctrl-microgrid",
        name="Microgrid Peak Shaving",
        description="Switch to battery during critical campus peaks",
        enabled=False
    )

    if not Zone.objects.exists():
        Zone.objects.create(
            zone_id="zone-1",
            name="Admin Block A",
            category="Administrative Offices",
            occupancy_label="Low (12%)",
            occupancy_value=12,
            temp=21.0,
            temp_set=20.0,
            humidity=45.0,
            consumption_label="High (45kW)",
            consumption_value=45,
            status=Zone.Status.INEFFICIENT,
            status_label="Inefficient Use",
            ai_recommendation="Reduce HVAC load — zone is mostly empty."
        )
        Zone.objects.create(
            zone_id="zone-2",
            name="Lab Complex C",
            category="Research Laboratories",
            occupancy_label="Med (65%)",
            occupancy_value=65,
            temp=22.0,
            temp_set=22.0,
            humidity=50.0,
            consumption_label="Expected (78kW)",
            consumption_value=78,
            status=Zone.Status.OPTIMAL,
            status_label="Optimal",
            ai_recommendation="Schedule matches occupancy. Maintaining optimal setpoint."
        )
        Zone.objects.create(
            zone_id="zone-3",
            name="Lecture Hall 101",
            category="Main Classrooms",
            occupancy_label="High (95%)",
            occupancy_value=95,
            temp=20.0,
            temp_set=20.0,
            humidity=55.0,
            consumption_label="Expected (60kW)",
            consumption_value=60,
            status=Zone.Status.OPTIMAL,
            status_label="Optimal",
            ai_recommendation="Class in progress. Ventilation operating at standard high-occupancy mode."
        )

    if not Alert.objects.exists():
        Alert.objects.create(
            alert_id="alert-1",
            title="Spike Detected: Lab 3",
            description="Unusual consumption pattern detected outside academic calendar hours.",
            alert_type=Alert.AlertType.ERROR,
            timestamp_label="10 mins ago",
            is_simulated=False,
            ai_diagnostic="High load detected inside the cleanroom. Possibly cleanroom HVAC ventilation stuck at 100% duty cycle while lab is unoccupied.",
            ai_resolution="Command sent to throttle cleanroom fan speeds to occupied level after 18:00."
        )
        Alert.objects.create(
            alert_id="alert-2",
            title="Maintenance Suggested: AHU-2",
            description="AC Unit B on Floor 2 showing decreased efficiency indices.",
            alert_type=Alert.AlertType.INFO,
            timestamp_label="2 hours ago",
            is_simulated=False,
            ai_diagnostic="Coil temperature gradient indicates filter throttling. Energy efficiency index dropped by 8%.",
            ai_resolution="Maintenance ticket scheduled for routine air filter replacement."
        )

    if not Report.objects.exists():
        Report.objects.create(
            report_id="rep-1",
            report_type="Managerial Overview",
            date_generated="Oct 24, 2023 • 08:00 AM",
            tags=["Monthly"],
            file_type=Report.FileType.PDF
        )
        Report.objects.create(
            report_id="rep-2",
            report_type="Consumption Details",
            date_generated="Oct 20, 2023 • 14:30 PM",
            tags=["Weekly"],
            file_type=Report.FileType.CSV
        )
        Report.objects.create(
            report_id="rep-3",
            report_type="Savings & Cost Reduction",
            date_generated="Oct 15, 2023 • 09:15 AM",
            tags=["Simulation"],
            file_type=Report.FileType.PDF
        )


# ---------------------------------------------------------------------------
# 1. Health
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["GET"])
def health_view(request):
    return JsonResponse({"status": "ok", "time": datetime.now(timezone.utc).isoformat()})


# ---------------------------------------------------------------------------
# 2. Telemetry
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["GET"])
def telemetry_view(request):
    _auto_seed_db()

    zones = Zone.objects.all()
    agents = Agent.objects.prefetch_related('controls').all()
    alerts = Alert.objects.all()
    reports = Report.objects.all()

    error_or_warn_count = alerts.filter(alert_type__in=['error', 'warn']).count()
    total_consumption = sum(z.consumption_value for z in zones)

    return JsonResponse({
        "zones": [_serialize_zone(z) for z in zones],
        "agents": [_serialize_agent(a) for a in agents],
        "alerts": [_serialize_alert(al) for al in alerts],
        "reports": [_serialize_report(r) for r in reports],
        "stats": {
            "totalZones": zones.count() + 39,
            "optimizationCount": error_or_warn_count + 5,
            "currentLoadKw": total_consumption + 250,
            "comfortIndex": 92,
        },
    }, safe=False)


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
        return JsonResponse({"error": "Missing required fields: name, category"}, status=400)

    occupancy_value = int(body.get("occupancyValue", 0))
    temp = float(body.get("temp", 22))
    temp_set = float(body.get("tempSet", 22))
    humidity = float(body.get("humidity", 50))
    consumption_value = int(body.get("consumptionValue", 45))
    optimal = _is_optimal(temp, temp_set, occupancy_value)

    zone = Zone.objects.create(
        zone_id=f"zone-{int(time.time() * 1000)}",
        name=name,
        category=category,
        occupancy_label=_make_occupancy_label(occupancy_value),
        occupancy_value=occupancy_value,
        temp=temp,
        temp_set=temp_set,
        humidity=humidity,
        consumption_label=_make_consumption_label(consumption_value),
        consumption_value=consumption_value,
        status=Zone.Status.OPTIMAL if optimal else Zone.Status.INEFFICIENT,
        status_label="Optimal" if optimal else "Inefficient Use",
        ai_recommendation=(
            "Operating within range. Maintaining smart schedule."
            if optimal
            else "Adjust setpoint to match thermal load — possible waste."
        ),
    )
    return JsonResponse({"success": True, "zone": _serialize_zone(zone)}, status=201)


@csrf_exempt
@require_http_methods(["PUT", "DELETE"])
def zone_detail(request, zone_id):
    if request.method == "DELETE":
        deleted, _ = Zone.objects.filter(zone_id=zone_id).delete()
        if not deleted:
            return JsonResponse({"error": "Zone not found"}, status=404)
        return JsonResponse({"success": True})

    # PUT
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    name = body.get("name")
    category = body.get("category")
    if not name or not category:
        return JsonResponse({"error": "Missing required fields: name, category"}, status=400)

    try:
        zone = Zone.objects.get(zone_id=zone_id)
    except Zone.DoesNotExist:
        return JsonResponse({"error": "Zone not found"}, status=404)

    occupancy_value = int(body.get("occupancyValue", 0))
    temp = float(body.get("temp", 22))
    temp_set = float(body.get("tempSet", 22))
    humidity = float(body.get("humidity", 50))
    consumption_value = int(body.get("consumptionValue", 45))
    optimal = _is_optimal(temp, temp_set, occupancy_value)

    zone.name = name
    zone.category = category
    zone.occupancy_label = _make_occupancy_label(occupancy_value)
    zone.occupancy_value = occupancy_value
    zone.temp = temp
    zone.temp_set = temp_set
    zone.humidity = humidity
    zone.consumption_label = _make_consumption_label(consumption_value)
    zone.consumption_value = consumption_value
    zone.status = Zone.Status.OPTIMAL if optimal else Zone.Status.INEFFICIENT
    zone.status_label = "Optimal" if optimal else "Inefficient Use"
    zone.ai_recommendation = (
        "Operating within range. Maintaining smart schedule."
        if optimal
        else "Adjust setpoint to match thermal load — possible waste."
    )
    zone.save()

    return JsonResponse({"success": True, "zone": _serialize_zone(zone)})


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

    try:
        agent = Agent.objects.prefetch_related('controls').get(agent_id=agent_id)
    except Agent.DoesNotExist:
        return JsonResponse({"error": "Agent not found"}, status=404)

    try:
        ctrl = agent.controls.get(control_id=control_id)
    except AgentControl.DoesNotExist:
        return JsonResponse({"error": "Control setting not found"}, status=404)

    ctrl.enabled = enabled
    ctrl.save()

    # Recalcular métricas do agente após alteração de controle
    all_controls = agent.controls.all()

    if agent.agent_type == "spending":
        agent.active_rules = all_controls.filter(enabled=True).count() * 4
        economy_enabled = all_controls.filter(control_id='ctrl-economy', enabled=True).exists()
        agent.est_savings = "21.6%" if economy_enabled else "15.4%"
        agent.status = (
            Agent.Status.OPTIMIZING
            if all_controls.filter(enabled=True).exists()
            else Agent.Status.INACTIVE
        )

    elif agent.agent_type == "network":
        backup_enabled = all_controls.filter(control_id='ctrl-backup', enabled=True).exists()
        agent.backup_status = "STANDBY" if backup_enabled else "ACTIVE"
        agent.status = (
            Agent.Status.MONITORING
            if all_controls.filter(enabled=True).exists()
            else Agent.Status.INACTIVE
        )

    agent.save()
    return JsonResponse({"success": True, "agent": _serialize_agent(agent)})


# ---------------------------------------------------------------------------
# 5. Error simulation
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
        return JsonResponse({"error": "Faltando parâmetros: anomalyType ou zoneId"}, status=400)

    zone_obj = Zone.objects.filter(zone_id=zone_id).first()
    zone_name = zone_obj.name if zone_obj else "Zona Campus Geral"
    zone_category = zone_obj.category if zone_obj else "Serviços Gerais"

    alert_id = f"sim-alert-{int(time.time() * 1000)}"

    default_diagnostic = (
        "Simulação de Anomalia de telemetria geral. Os parâmetros estão fora das "
        "metas ambientais aceitáveis, gerando desperdício e potencial desgaste do equipamento."
    )
    default_resolution = (
        "Ajuste preventivo realizado via agente EnergiAI. "
        "Redução de ganho de damper e monitoramento térmico ativo."
    )
    ai_data = {"diagnostic": default_diagnostic, "actionTaken": default_resolution}
    used_ai = False

    # Tentar Gemini
    import os
    from google import genai as google_genai
    api_key = os.getenv("GEMINI_API_KEY", "")
    if api_key:
        try:
            client = google_genai.Client(api_key=api_key)
            prompt = (
                "Analise a seguinte simulação de erro/anomalia em um prédio inteligente e gere:\n"
                "1. Um diagnóstico de engenharia detalhado (em português).\n"
                "2. Uma resolução/ação imediata recomendada ou executada automaticamente.\n\n"
                f"Parâmetros:\n"
                f"- Tipo de anomalia: {anomaly_type}\n"
                f"- Zona: {zone_name} ({zone_category})\n"
                f"- Severidade: {severity}\n"
                f"- Notas: {notes or 'Nenhuma'}\n\n"
                'Retorne EXCLUSIVAMENTE JSON: {"diagnostic": "...", "actionTaken": "..."}'
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            if response and response.text:
                ai_data = json.loads(response.text.strip())
                used_ai = True
        except Exception as exc:
            logger.error("Erro ao chamar Gemini API: %s", exc)

    if not used_ai:
        if "AC" in anomaly_type or "HVAC" in anomaly_type:
            ai_data["diagnostic"] = (
                f"Superaquecimento no fan coil principal do {zone_name}. "
                "Taxa de ocupação não justifica a demanda extrema medida."
            )
            ai_data["actionTaken"] = (
                "Modulação de válvula fracionária enviada. Redução de vazão de água gelada em 30%."
            )
        elif "Iluminação" in anomaly_type or "Luz" in anomaly_type:
            ai_data["diagnostic"] = (
                f"Luzes de {zone_name} ativas fora de hora com zero movimentação no sensor."
            )
            ai_data["actionTaken"] = (
                "Override forçando ciclo noturno em 10% da potência de iluminação."
            )

    alert_type = "error" if severity in ("critical", "high") else "warn"
    alert = Alert.objects.create(
        alert_id=alert_id,
        title=f"Simulação: {anomaly_type} detectado",
        description=(
            f"Comportamento anômalo na instalação {zone_name} ({zone_category}). "
            f"severity: {severity}."
        ),
        alert_type=alert_type,
        timestamp_label="Just now",
        is_simulated=True,
        ai_diagnostic=ai_data["diagnostic"],
        ai_resolution=ai_data["actionTaken"],
    )

    if zone_obj:
        if severity in ("critical", "high"):
            zone_obj.status = Zone.Status.CRITICAL
            zone_obj.status_label = "Critical Error"
        else:
            zone_obj.status = Zone.Status.INEFFICIENT
            zone_obj.status_label = "Inefficient Use"
        zone_obj.consumption_value += 30
        zone_obj.consumption_label = f"Alert ({zone_obj.consumption_value}kW)"
        zone_obj.ai_recommendation = f"AI Rec: {ai_data['actionTaken']}"
        zone_obj.save()

    return JsonResponse({
        "success": True,
        "alert": _serialize_alert(alert),
        "aiFeedback": ai_data,
    })


# ---------------------------------------------------------------------------
# 6. Optimize environment (CrewAI)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def optimize_environment(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        logger.error("Erro ao decodificar JSON: %s", e)
        return JsonResponse(
            {"error": "Payload inválido. Certifique-se de enviar um JSON válido."},
            status=400,
        )
    try:
        result = run_energy_crew(data)
        return JsonResponse(result, status=200)
    except ValueError as e:
        logger.warning("Erro de validação dos dados: %s", e)
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        logger.error("Erro interno na Crew: %s", e, exc_info=True)
        return JsonResponse(
            {"error": f"Erro interno durante a otimização energética: {str(e)}"},
            status=500,
        )


# ---------------------------------------------------------------------------
# 7. Dynamic API routes for creating Agents, Alerts and Reports (no fixtures)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def create_agent(request):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    agent_id = body.get("agent_id")
    name = body.get("name")
    agent_type = body.get("agent_type")
    
    if not agent_id or not name or not agent_type:
        return JsonResponse({"error": "Missing required fields: agent_id, name, agent_type"}, status=400)

    agent, created = Agent.objects.update_or_create(
        agent_id=agent_id,
        defaults={
            "name": name,
            "agent_type": agent_type,
            "status": body.get("status", Agent.Status.MONITORING),
            "est_savings": body.get("est_savings", ""),
            "active_rules": int(body.get("active_rules", 0)),
            "failure_risk": int(body.get("failure_risk", 0)),
            "failure_risk_label": body.get("failure_risk_label", ""),
            "backup_status": body.get("backup_status", ""),
            "network_stability": body.get("network_stability", []),
        }
    )

    controls_data = body.get("controls", [])
    for ctrl in controls_data:
        AgentControl.objects.update_or_create(
            agent=agent,
            control_id=ctrl.get("control_id"),
            defaults={
                "name": ctrl.get("name"),
                "description": ctrl.get("description", ""),
                "enabled": ctrl.get("enabled", True),
            }
        )

    return JsonResponse({"success": True, "agent": _serialize_agent(agent)}, status=201)


@csrf_exempt
@require_http_methods(["POST"])
def create_alert(request):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    alert_id = body.get("alert_id")
    title = body.get("title")
    if not alert_id or not title:
        return JsonResponse({"error": "Missing required fields: alert_id, title"}, status=400)

    alert = Alert.objects.create(
        alert_id=alert_id,
        title=title,
        description=body.get("description", ""),
        alert_type=body.get("alert_type", Alert.AlertType.INFO),
        timestamp_label=body.get("timestamp_label", "Just now"),
        is_simulated=body.get("is_simulated", False),
        ai_diagnostic=body.get("ai_diagnostic", ""),
        ai_resolution=body.get("ai_resolution", ""),
    )
    return JsonResponse({"success": True, "alert": _serialize_alert(alert)}, status=201)


@csrf_exempt
@require_http_methods(["POST"])
def create_report(request):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    report_id = body.get("report_id")
    report_type = body.get("report_type")
    if not report_id or not report_type:
        return JsonResponse({"error": "Missing required fields: report_id, report_type"}, status=400)

    report = Report.objects.create(
        report_id=report_id,
        report_type=report_type,
        date_generated=body.get("date_generated", datetime.now().strftime("%b %d, %Y • %H:%M %p")),
        tags=body.get("tags", []),
        file_type=body.get("file_type", Report.FileType.PDF),
    )
    return JsonResponse({"success": True, "report": _serialize_report(report)}, status=201)
