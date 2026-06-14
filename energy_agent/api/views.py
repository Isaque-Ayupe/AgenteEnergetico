import json
import logging
import random
import time
import uuid
from datetime import datetime, timezone

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from api.models import Zone, Agent, AgentControl, Alert, Report, Anomaly
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
# 5. Error simulation — ANOMALIAS REAIS
# ---------------------------------------------------------------------------

def _zone_snapshot(z: Zone) -> dict:
    """Captura snapshot dos valores atuais de uma zona."""
    return {
        "temp": z.temp,
        "tempSet": z.temp_set,
        "humidity": z.humidity,
        "consumptionValue": z.consumption_value,
        "consumptionLabel": z.consumption_label,
        "occupancyValue": z.occupancy_value,
        "occupancyLabel": z.occupancy_label,
        "status": z.status,
        "statusLabel": z.status_label,
    }


def _apply_real_anomaly(zone_obj: Zone, anomaly_type: str, severity: str):
    """Aplica alterações realistas nos sensores da zona conforme o tipo de anomalia."""
    severity_multiplier = {
        "low": 0.5, "medium": 0.75, "high": 1.0, "critical": 1.5,
    }.get(severity, 1.0)

    if "HVAC" in anomaly_type or "Temperatura" in anomaly_type:
        delta_temp = random.uniform(4, 8) * severity_multiplier
        delta_consumption = random.randint(40, 80)
        zone_obj.temp = round(zone_obj.temp + delta_temp, 1)
        zone_obj.consumption_value += int(delta_consumption * severity_multiplier)
        zone_obj.humidity = min(95, zone_obj.humidity + random.randint(5, 15))

    elif "Surto" in anomaly_type or "Consumo" in anomaly_type:
        delta_consumption = random.randint(60, 120)
        zone_obj.consumption_value += int(delta_consumption * severity_multiplier)
        zone_obj.temp = round(zone_obj.temp + random.uniform(1, 3), 1)

    elif "Sensor" in anomaly_type:
        zone_obj.temp = 99.9 if random.random() > 0.5 else -1.0
        zone_obj.humidity = 0.0
        zone_obj.consumption_value += random.randint(10, 30)

    elif "Luz" in anomaly_type or "Iluminação" in anomaly_type:
        delta_consumption = random.randint(15, 30)
        zone_obj.consumption_value += int(delta_consumption * severity_multiplier)
        zone_obj.occupancy_value = max(0, zone_obj.occupancy_value - random.randint(20, 50))
        zone_obj.occupancy_label = _make_occupancy_label(zone_obj.occupancy_value)

    elif "Umidade" in anomaly_type:
        delta_humidity = random.uniform(25, 40) * severity_multiplier
        zone_obj.humidity = min(99, round(zone_obj.humidity + delta_humidity, 1))
        zone_obj.consumption_value += random.randint(10, 25)

    elif "Fator" in anomaly_type or "Potência" in anomaly_type or "Transformador" in anomaly_type:
        delta_consumption = random.randint(50, 100)
        zone_obj.consumption_value += int(delta_consumption * severity_multiplier)
        zone_obj.temp = round(zone_obj.temp + random.uniform(2, 5), 1)

    else:
        zone_obj.consumption_value += int(30 * severity_multiplier)
        zone_obj.temp = round(zone_obj.temp + random.uniform(1, 4), 1)

    # Atualizar labels
    zone_obj.consumption_label = f"Alerta ({zone_obj.consumption_value}kW)"
    if severity in ("critical", "high"):
        zone_obj.status = Zone.Status.CRITICAL
        zone_obj.status_label = "Critical Error"
    else:
        zone_obj.status = Zone.Status.INEFFICIENT
        zone_obj.status_label = "Inefficient Use"


def _serialize_anomaly(a: Anomaly) -> dict:
    return {
        "id": a.anomaly_id,
        "anomalyType": a.anomaly_type,
        "zoneId": a.zone.zone_id if a.zone else None,
        "zoneName": a.zone.name if a.zone else None,
        "severity": a.severity,
        "status": a.status,
        "notes": a.notes,
        "diagnostic": a.diagnostic,
        "actionTaken": a.action_taken,
        "savingsImpact": a.savings_impact,
        "alertId": a.alert.alert_id if a.alert else None,
        "snapshotBefore": a.zone_snapshot_before,
        "snapshotAfter": a.zone_snapshot_after,
        "createdAt": a.created_at.isoformat() if a.created_at else None,
    }


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

    # Snapshot ANTES da anomalia
    snapshot_before = _zone_snapshot(zone_obj) if zone_obj else {}

    # Aplicar alterações REAIS na zona
    if zone_obj:
        _apply_real_anomaly(zone_obj, anomaly_type, severity)

    # Snapshot DEPOIS da anomalia
    snapshot_after = _zone_snapshot(zone_obj) if zone_obj else {}

    alert_id = f"anomaly-{int(time.time() * 1000)}"
    anomaly_id = f"anom-{int(time.time() * 1000)}"

    # Diagnóstico via IA
    default_diagnostic = (
        f"Anomalia real detectada na zona {zone_name}. Os parâmetros de telemetria "
        "ultrapassaram os limiares operacionais aceitáveis, indicando degradação "
        "de eficiência e potencial desgaste acelerado do equipamento."
    )
    default_resolution = (
        "Ajuste preventivo automático realizado via agente EnergiAI. "
        "Redução de ganho de damper e monitoramento térmico ativo habilitado."
    )
    default_savings = (
        f"Estimativa de economia de {random.randint(8, 22)}% na carga da zona "
        f"{zone_name} após aplicação das ações corretivas coordenadas."
    )
    ai_data = {
        "diagnostic": default_diagnostic,
        "actionTaken": default_resolution,
        "savingsImpact": default_savings,
    }
    used_ai = False

    # Tentar Gemini para diagnóstico real
    import os
    from google import genai as google_genai
    api_key = os.getenv("GEMINI_API_KEY", "")
    if api_key:
        try:
            client = google_genai.Client(api_key=api_key)
            prompt = (
                "Analise a seguinte ANOMALIA REAL em um prédio inteligente e gere:\n"
                "1. Um diagnóstico de engenharia detalhado (em português).\n"
                "2. Uma resolução/ação imediata executada automaticamente.\n"
                "3. O impacto estimado na economia de energia.\n\n"
                f"Parâmetros:\n"
                f"- Tipo de anomalia: {anomaly_type}\n"
                f"- Zona: {zone_name} ({zone_category})\n"
                f"- Severidade: {severity}\n"
                f"- Notas: {notes or 'Nenhuma'}\n"
                f"- Valores ANTES: temp={snapshot_before.get('temp', 'N/A')}°C, "
                f"umidade={snapshot_before.get('humidity', 'N/A')}%, "
                f"consumo={snapshot_before.get('consumptionValue', 'N/A')}kW\n"
                f"- Valores DEPOIS: temp={snapshot_after.get('temp', 'N/A')}°C, "
                f"umidade={snapshot_after.get('humidity', 'N/A')}%, "
                f"consumo={snapshot_after.get('consumptionValue', 'N/A')}kW\n\n"
                'Retorne EXCLUSIVAMENTE JSON: '
                '{"diagnostic": "...", "actionTaken": "...", "savingsImpact": "..."}'
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            if response and response.text:
                ai_data = json.loads(response.text.strip())
                # Garantir que savingsImpact exista
                if "savingsImpact" not in ai_data:
                    ai_data["savingsImpact"] = default_savings
                used_ai = True
        except Exception as exc:
            logger.error("Erro ao chamar Gemini API: %s", exc)

    if not used_ai:
        if "AC" in anomaly_type or "HVAC" in anomaly_type or "Temperatura" in anomaly_type:
            ai_data["diagnostic"] = (
                f"Superaquecimento real detectado no fan coil principal do {zone_name}. "
                f"Temperatura subiu de {snapshot_before.get('temp', 'N/A')}°C para "
                f"{snapshot_after.get('temp', 'N/A')}°C. "
                "Taxa de ocupação não justifica a demanda extrema medida."
            )
            ai_data["actionTaken"] = (
                "Modulação de válvula fracionária executada. "
                "Redução de vazão de água gelada em 30%. Alerta enviado à manutenção."
            )
        elif "Iluminação" in anomaly_type or "Luz" in anomaly_type:
            ai_data["diagnostic"] = (
                f"Iluminação de {zone_name} detectada ativa fora do horário operacional. "
                "Sensores de presença indicam zero movimentação nos últimos 45 minutos."
            )
            ai_data["actionTaken"] = (
                "Override automático aplicado: ciclo noturno em 10% da potência."
            )
        elif "Sensor" in anomaly_type:
            ai_data["diagnostic"] = (
                f"Falha crítica de sensor térmico em {zone_name}. "
                f"Leitura absurda de {snapshot_after.get('temp', 'N/A')}°C detectada. "
                "Possível defeito de hardware no termopar ou na interface RS-485."
            )
            ai_data["actionTaken"] = (
                "Sensor isolado do loop de controle. Sistema operando com valor "
                "estimado baseado em zonas adjacentes. Ticket de manutenção aberto."
            )
        elif "Umidade" in anomaly_type:
            ai_data["diagnostic"] = (
                f"Pico de umidade severo em {zone_name}. "
                f"Umidade subiu de {snapshot_before.get('humidity', 'N/A')}% para "
                f"{snapshot_after.get('humidity', 'N/A')}%. "
                "Risco de condensação em equipamentos eletrônicos."
            )
            ai_data["actionTaken"] = (
                "Desumidificador de emergência acionado. Ventilação forçada em modo turbo."
            )

    # Criar Alert REAL (não simulado)
    alert_type = "error" if severity in ("critical", "high") else "warn"
    alert = Alert.objects.create(
        alert_id=alert_id,
        title=f"Anomalia: {anomaly_type}",
        description=(
            f"Anomalia real detectada em {zone_name} ({zone_category}). "
            f"Severidade: {severity}."
        ),
        alert_type=alert_type,
        timestamp_label="Agora",
        is_simulated=False,
        ai_diagnostic=ai_data["diagnostic"],
        ai_resolution=ai_data.get("actionTaken", ai_data.get("action_taken", "")),
    )

    # Salvar recomendação na zona
    if zone_obj:
        zone_obj.ai_recommendation = ai_data.get("actionTaken", ai_data.get("action_taken", ""))
        zone_obj.save()

    # Criar registro persistente da Anomalia
    anomaly_record = Anomaly.objects.create(
        anomaly_id=anomaly_id,
        anomaly_type=anomaly_type,
        zone=zone_obj,
        severity=severity,
        status=Anomaly.Status.ACTIVE,
        notes=notes,
        diagnostic=ai_data["diagnostic"],
        action_taken=ai_data.get("actionTaken", ai_data.get("action_taken", "")),
        savings_impact=ai_data.get("savingsImpact", ""),
        alert=alert,
        zone_snapshot_before=snapshot_before,
        zone_snapshot_after=snapshot_after,
    )

    return JsonResponse({
        "success": True,
        "alert": _serialize_alert(alert),
        "anomaly": _serialize_anomaly(anomaly_record),
        "aiFeedback": {
            "diagnostic": ai_data["diagnostic"],
            "actionTaken": ai_data.get("actionTaken", ai_data.get("action_taken", "")),
            "savingsImpact": ai_data.get("savingsImpact", ""),
        },
    })


# ---------------------------------------------------------------------------
# 5b. Anomalies CRUD
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["GET"])
def list_anomalies(request):
    """Lista todas as anomalias registradas."""
    anomalies = Anomaly.objects.select_related('zone', 'alert').all()
    status_filter = request.GET.get("status")
    if status_filter:
        anomalies = anomalies.filter(status=status_filter)
    return JsonResponse({
        "anomalies": [_serialize_anomaly(a) for a in anomalies],
        "total": anomalies.count(),
    })


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def anomaly_detail(request, anomaly_id):
    """Detalhe, atualização ou remoção de uma anomalia."""
    try:
        anomaly = Anomaly.objects.select_related('zone', 'alert').get(anomaly_id=anomaly_id)
    except Anomaly.DoesNotExist:
        return JsonResponse({"error": "Anomalia não encontrada"}, status=404)

    if request.method == "GET":
        return JsonResponse({"anomaly": _serialize_anomaly(anomaly)})

    if request.method == "DELETE":
        anomaly.delete()
        return JsonResponse({"success": True})

    # PUT — atualizar status, notas
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if "status" in body:
        new_status = body["status"]
        if new_status in dict(Anomaly.Status.choices):
            anomaly.status = new_status
            # Se resolvida, restaurar zona ao estado anterior
            if new_status == "resolved" and anomaly.zone and anomaly.zone_snapshot_before:
                snap = anomaly.zone_snapshot_before
                zone = anomaly.zone
                zone.temp = snap.get("temp", zone.temp)
                zone.temp_set = snap.get("tempSet", zone.temp_set)
                zone.humidity = snap.get("humidity", zone.humidity)
                zone.consumption_value = snap.get("consumptionValue", zone.consumption_value)
                zone.consumption_label = snap.get("consumptionLabel", zone.consumption_label)
                zone.occupancy_value = snap.get("occupancyValue", zone.occupancy_value)
                zone.occupancy_label = snap.get("occupancyLabel", zone.occupancy_label)
                zone.status = snap.get("status", zone.status)
                zone.status_label = snap.get("statusLabel", zone.status_label)
                zone.ai_recommendation = "Zona restaurada após resolução de anomalia."
                zone.save()

    if "notes" in body:
        anomaly.notes = body["notes"]

    anomaly.save()
    return JsonResponse({"success": True, "anomaly": _serialize_anomaly(anomaly)})


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
