"""
Modelos Django para persistência dos dados operacionais do sistema.

Estes modelos substituem as listas em memória que existiam em views.py,
garantindo consistência de dados em ambientes multi-process e entre reinicializações.
"""

from django.db import models


class Zone(models.Model):
    """Zona climática monitorada (sala, laboratório, bloco administrativo)."""

    class Status(models.TextChoices):
        OPTIMAL = 'OPTIMAL', 'Optimal'
        INEFFICIENT = 'INEFFICIENT', 'Inefficient Use'
        CRITICAL = 'CRITICAL', 'Critical Error'

    zone_id = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    category = models.CharField(max_length=128)
    occupancy_label = models.CharField(max_length=32, default='Low (0%)')
    occupancy_value = models.IntegerField(default=0)
    temp = models.FloatField(default=22.0)
    temp_set = models.FloatField(default=22.0)
    humidity = models.FloatField(default=50.0)
    consumption_label = models.CharField(max_length=32, default='Expected (0kW)')
    consumption_value = models.IntegerField(default=0)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.OPTIMAL
    )
    status_label = models.CharField(max_length=32, default='Optimal')
    ai_recommendation = models.TextField(default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'api_zone'
        ordering = ['zone_id']

    def __str__(self) -> str:
        return f"{self.name} ({self.zone_id})"


class Agent(models.Model):
    """Agente de controle predial (spending, network, etc.)."""

    class Status(models.TextChoices):
        OPTIMIZING = 'OPTIMIZING', 'Optimizing'
        MONITORING = 'MONITORING', 'Monitoring'
        INACTIVE = 'INACTIVE', 'Inactive'

    agent_id = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    agent_type = models.CharField(max_length=32)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.MONITORING
    )
    # Campos específicos de spending
    est_savings = models.CharField(max_length=16, blank=True, default='')
    active_rules = models.IntegerField(default=0)
    # Campos específicos de resilience
    failure_risk = models.IntegerField(default=0)
    failure_risk_label = models.CharField(max_length=32, blank=True, default='')
    backup_status = models.CharField(max_length=16, blank=True, default='')
    network_stability = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'api_agent'
        ordering = ['agent_id']

    def __str__(self) -> str:
        return f"{self.name} ({self.agent_id})"


class AgentControl(models.Model):
    """Controle individual de um agente (toggle de funcionalidade)."""

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='controls')
    control_id = models.CharField(max_length=64)
    name = models.CharField(max_length=128)
    description = models.TextField(default='')
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = 'api_agent_control'
        unique_together = ('agent', 'control_id')
        ordering = ['control_id']

    def __str__(self) -> str:
        return f"{self.agent.agent_id} / {self.control_id}"


class Alert(models.Model):
    """Alerta de anomalia ou evento operacional."""

    class AlertType(models.TextChoices):
        ERROR = 'error', 'Error'
        WARN = 'warn', 'Warning'
        INFO = 'info', 'Info'

    alert_id = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=256)
    description = models.TextField(default='')
    alert_type = models.CharField(
        max_length=8, choices=AlertType.choices, default=AlertType.INFO
    )
    timestamp_label = models.CharField(max_length=64, default='Just now')
    is_simulated = models.BooleanField(default=False)
    ai_diagnostic = models.TextField(blank=True, default='')
    ai_resolution = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'api_alert'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"[{self.alert_type.upper()}] {self.title}"


class Report(models.Model):
    """Relatório gerado pelo sistema."""

    class FileType(models.TextChoices):
        PDF = 'PDF', 'PDF'
        CSV = 'CSV', 'CSV'

    report_id = models.CharField(max_length=64, unique=True)
    report_type = models.CharField(max_length=128)
    date_generated = models.CharField(max_length=64)
    tags = models.JSONField(default=list)
    file_type = models.CharField(
        max_length=4, choices=FileType.choices, default=FileType.PDF
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'api_report'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.report_type} ({self.date_generated})"
