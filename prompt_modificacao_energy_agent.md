# Prompt de Modificação — Sistema de Agentes de Controle Energético

Você receberá o repositório completo do projeto `energy_agent` (Django + CrewAI + Google Gemini).
Aplique **todas** as modificações descritas abaixo de forma integral. Não omita nenhum arquivo
e não altere comportamentos que não estejam listados. Ao final, todos os arquivos modificados
devem ser apresentados na íntegra.

---

## BLOCO 1 — Padronização de Versões

### 1.1 `energy_agent/requirements.txt`

Substitua o conteúdo completo por:

```
# Framework Web
Django==6.0.5
django-cors-headers==4.7.0

# Banco de dados PostgreSQL
psycopg2-binary==2.9.10

# Agentes e LLM
crewai==1.14.0
langchain-google-genai==2.1.5
google-genai==1.16.0

# Variáveis de ambiente
python-dotenv==1.1.0
```

**Critérios de escolha:**
- Todas as versões são pinadas (`==`) para garantir reprodutibilidade total em qualquer ambiente.
- `Django==6.0.5` alinha com o que o projeto já usa internamente (gerado via `django-admin startproject`).
- `crewai==1.14.0` corresponde à versão citada no `README.md`. A ausência de pin era o principal risco de breaking change.
- `psycopg2-binary==2.9.10` é adicionado para suporte ao PostgreSQL (Bloco 3).
- `google-genai==1.16.0` e `langchain-google-genai==2.1.5` são as versões estáveis compatíveis com Gemini 2.5 Flash.

### 1.2 `energy_agent/core/settings.py` — Anotação de versão

No topo do arquivo `settings.py`, atualize o comentário gerado automaticamente para:

```python
# Django 6.0.5 — configurações do projeto energy_agent
# Documentação: https://docs.djangoproject.com/en/6.0/topics/settings/
```

---

## BLOCO 2 — Segurança: Remover Valores Hardcoded

### 2.1 Criar `.env.example`

Crie o arquivo `energy_agent/.env.example` (modelo público, sem valores reais) com o seguinte conteúdo:

```env
# ============================================================
# VARIÁVEIS DE AMBIENTE — energy_agent
# Copie este arquivo para .env e preencha com seus valores reais.
# NUNCA versione o arquivo .env.
# ============================================================

# Django
DJANGO_SECRET_KEY=substitua-por-uma-chave-segura-de-50-chars-ou-mais
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Google Gemini
GEMINI_API_KEY=sua_chave_de_api_aqui

# PostgreSQL
DB_NAME=energy_agent_db
DB_USER=postgres
DB_PASSWORD=sua_senha_aqui
DB_HOST=localhost
DB_PORT=5432
```

### 2.2 `energy_agent/core/settings.py` — Ler segredos do ambiente

Substitua o bloco de configurações sensíveis. O arquivo final de `settings.py` deve ser:

```python
"""
Django 6.0.5 — configurações do projeto energy_agent
Documentação: https://docs.djangoproject.com/en/6.0/topics/settings/
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

# ------------------------------------------------------------------
# Segurança — valores obrigatoriamente lidos do ambiente
# ------------------------------------------------------------------
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']

DEBUG = os.getenv('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')

_raw_hosts = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(',') if h.strip()]

# ------------------------------------------------------------------
# Aplicações instaladas
# ------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# CORS — restringir em produção via DJANGO_CORS_ORIGINS no ambiente
CORS_ALLOW_ALL_ORIGINS = DEBUG

APPEND_SLASH = False

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# ------------------------------------------------------------------
# Banco de dados PostgreSQL (Bloco 3)
# ------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'energy_agent_db'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# ------------------------------------------------------------------
# Validação de senhas
# ------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ------------------------------------------------------------------
# Internacionalização
# ------------------------------------------------------------------
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
```

**Regras de segurança aplicadas:**
- `SECRET_KEY` usa `os.environ['DJANGO_SECRET_KEY']` (sem `getenv`): se a variável não existir, o servidor não sobe — comportamento intencional e seguro.
- `DEBUG` lê do ambiente e tem padrão `False` (seguro para deploy acidental).
- `ALLOWED_HOSTS` lê do ambiente; sem `['*']` em nenhuma circunstância.
- `CORS_ALLOW_ALL_ORIGINS` só é `True` quando `DEBUG=True`.

### 2.3 `energy_agent/crew/agents.py` — Sem alteração de lógica, validação reforçada

A leitura de `GEMINI_API_KEY` via `os.getenv` já estava correta. Adicione apenas uma mensagem de erro mais clara:

```python
def get_llm() -> LLM:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY não encontrada. "
            "Defina esta variável no arquivo .env antes de iniciar o servidor."
        )
    return LLM(
        model="gemini/gemini-2.5-flash",
        api_key=api_key,
        temperature=0
    )
```

---

## BLOCO 3 — Banco de Dados: SQLite → PostgreSQL com Modelos Django

### 3.1 Criar script utilitário de inicialização do banco

Crie o arquivo `energy_agent/core/db_init.py`:

```python
"""
Utilitário para criar o banco de dados PostgreSQL caso ele não exista.
Execute antes de 'manage.py migrate' em um ambiente novo:

    python energy_agent/core/db_init.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def create_database_if_not_exists() -> None:
    db_name = os.getenv('DB_NAME', 'energy_agent_db')
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD', '')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')

    # Conecta ao banco padrão 'postgres' para verificar/criar o banco alvo
    try:
        conn = psycopg2.connect(
            dbname='postgres',
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port,
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (db_name,)
        )
        exists = cursor.fetchone()

        if not exists:
            cursor.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name))
            )
            print(f"[db_init] Banco de dados '{db_name}' criado com sucesso.")
        else:
            print(f"[db_init] Banco de dados '{db_name}' já existe. Nenhuma ação necessária.")

        cursor.close()
        conn.close()

    except psycopg2.OperationalError as e:
        print(f"[db_init] ERRO ao conectar ao PostgreSQL: {e}", file=sys.stderr)
        print(
            "[db_init] Verifique se o servidor PostgreSQL está rodando e se as "
            "variáveis DB_USER, DB_PASSWORD, DB_HOST e DB_PORT estão corretas no .env",
            file=sys.stderr
        )
        sys.exit(1)


if __name__ == '__main__':
    create_database_if_not_exists()
```

### 3.2 Atualizar o `README.md` — Seção de execução

Na seção **"Como Executar o Projeto"**, adicione o passo abaixo **antes** do `manage.py migrate`:

```markdown
### 3. Inicializar o Banco de Dados PostgreSQL

Certifique-se de que o PostgreSQL está rodando e que as variáveis `DB_*` estão preenchidas no `.env`.
Execute o script de inicialização para criar o banco caso ele não exista:

```bash
python energy_agent/core/db_init.py
```

Em seguida, aplique as migrações Django:

```bash
python energy_agent/manage.py migrate
```

Para popular o banco com os dados iniciais de zonas, agentes e alertas:

```bash
python energy_agent/manage.py loaddata initial_data
```
```

---

## BLOCO 4 — Remover Estado da Memória: Modelos Django e CRUD via ORM

### 4.1 `energy_agent/api/models.py`

Substitua o conteúdo por:

```python
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
```

### 4.2 Criar fixture de dados iniciais

Crie o arquivo `energy_agent/api/fixtures/initial_data.json` com os dados que antes estavam hardcoded em `views.py`:

```json
[
  {
    "model": "api.zone",
    "pk": 1,
    "fields": {
      "zone_id": "zone-1",
      "name": "Admin Block A",
      "category": "Administrative Offices",
      "occupancy_label": "Low (12%)",
      "occupancy_value": 12,
      "temp": 21.0,
      "temp_set": 20.0,
      "humidity": 45.0,
      "consumption_label": "High (45kW)",
      "consumption_value": 45,
      "status": "INEFFICIENT",
      "status_label": "Inefficient Use",
      "ai_recommendation": "Reduce HVAC load — zone is mostly empty."
    }
  },
  {
    "model": "api.zone",
    "pk": 2,
    "fields": {
      "zone_id": "zone-2",
      "name": "Lab Complex C",
      "category": "Research Laboratories",
      "occupancy_label": "Med (65%)",
      "occupancy_value": 65,
      "temp": 22.0,
      "temp_set": 22.0,
      "humidity": 50.0,
      "consumption_label": "Expected (78kW)",
      "consumption_value": 78,
      "status": "OPTIMAL",
      "status_label": "Optimal",
      "ai_recommendation": "Schedule matches occupancy. Maintaining optimal setpoint."
    }
  },
  {
    "model": "api.zone",
    "pk": 3,
    "fields": {
      "zone_id": "zone-3",
      "name": "Lecture Hall 101",
      "category": "Main Classrooms",
      "occupancy_label": "High (95%)",
      "occupancy_value": 95,
      "temp": 20.0,
      "temp_set": 20.0,
      "humidity": 55.0,
      "consumption_label": "Expected (60kW)",
      "consumption_value": 60,
      "status": "OPTIMAL",
      "status_label": "Optimal",
      "ai_recommendation": "Class in progress. Ventilation operating at standard high-occupancy mode."
    }
  },
  {
    "model": "api.agent",
    "pk": 1,
    "fields": {
      "agent_id": "agent-spending",
      "name": "Spending Control Agent",
      "agent_type": "spending",
      "status": "OPTIMIZING",
      "est_savings": "15.4%",
      "active_rules": 12,
      "failure_risk": 0,
      "failure_risk_label": "",
      "backup_status": "",
      "network_stability": []
    }
  },
  {
    "model": "api.agent",
    "pk": 2,
    "fields": {
      "agent_id": "agent-resilience",
      "name": "Network Resilience Agent",
      "agent_type": "network",
      "status": "MONITORING",
      "est_savings": "",
      "active_rules": 0,
      "failure_risk": 12,
      "failure_risk_label": "Low/Moderate",
      "backup_status": "STANDBY",
      "network_stability": [60, 75, 65, 85, 70, 95, 90, 99.9]
    }
  },
  {
    "model": "api.agentcontrol",
    "pk": 1,
    "fields": {
      "agent": 1,
      "control_id": "ctrl-ac",
      "name": "Automated AC Adjustment",
      "description": "Modulate based on occupancy & outside temp",
      "enabled": true
    }
  },
  {
    "model": "api.agentcontrol",
    "pk": 2,
    "fields": {
      "agent": 1,
      "control_id": "ctrl-lights",
      "name": "Dynamic Lighting Schedules",
      "description": "Sync with academic/operational calendar",
      "enabled": true
    }
  },
  {
    "model": "api.agentcontrol",
    "pk": 3,
    "fields": {
      "agent": 1,
      "control_id": "ctrl-economy",
      "name": "Max Economy Mode",
      "description": "Prioritize savings over strict thermal comfort",
      "enabled": false
    }
  },
  {
    "model": "api.agentcontrol",
    "pk": 4,
    "fields": {
      "agent": 2,
      "control_id": "ctrl-backup",
      "name": "Intelligent Generator Dispatch",
      "description": "Pre-empt power sag with backup launch",
      "enabled": true
    }
  },
  {
    "model": "api.agentcontrol",
    "pk": 5,
    "fields": {
      "agent": 2,
      "control_id": "ctrl-microgrid",
      "name": "Microgrid Peak Shaving",
      "description": "Switch to battery during critical campus peaks",
      "enabled": false
    }
  },
  {
    "model": "api.alert",
    "pk": 1,
    "fields": {
      "alert_id": "alert-1",
      "title": "Spike Detected: Lab 3",
      "description": "Unusual consumption pattern detected outside academic calendar hours.",
      "alert_type": "error",
      "timestamp_label": "10 mins ago",
      "is_simulated": false,
      "ai_diagnostic": "High load detected inside the cleanroom. Possibly cleanroom HVAC ventilation stuck at 100% duty cycle while lab is unoccupied.",
      "ai_resolution": "Command sent to throttle cleanroom fan speeds to occupied level after 18:00."
    }
  },
  {
    "model": "api.alert",
    "pk": 2,
    "fields": {
      "alert_id": "alert-2",
      "title": "Maintenance Suggested: AHU-2",
      "description": "AC Unit B on Floor 2 showing decreased efficiency indices.",
      "alert_type": "info",
      "timestamp_label": "2 hours ago",
      "is_simulated": false,
      "ai_diagnostic": "Coil temperature gradient indicates filter throttling. Energy efficiency index dropped by 8%.",
      "ai_resolution": "Maintenance ticket scheduled for routine air filter replacement."
    }
  },
  {
    "model": "api.report",
    "pk": 1,
    "fields": {
      "report_id": "rep-1",
      "report_type": "Managerial Overview",
      "date_generated": "Oct 24, 2023 • 08:00 AM",
      "tags": ["Monthly"],
      "file_type": "PDF"
    }
  },
  {
    "model": "api.report",
    "pk": 2,
    "fields": {
      "report_id": "rep-2",
      "report_type": "Consumption Details",
      "date_generated": "Oct 20, 2023 • 14:30 PM",
      "tags": ["Weekly"],
      "file_type": "CSV"
    }
  },
  {
    "model": "api.report",
    "pk": 3,
    "fields": {
      "report_id": "rep-3",
      "report_type": "Savings & Cost Reduction",
      "date_generated": "Oct 15, 2023 • 09:15 AM",
      "tags": ["Simulation"],
      "file_type": "PDF"
    }
  }
]
```

### 4.3 `energy_agent/api/views.py` — Substituir listas em memória por ORM

Substitua o conteúdo completo de `views.py` pelo seguinte. Toda operação de leitura e escrita
que antes operava em listas Python agora usa `QuerySet` do Django ORM:

```python
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
```

---

## BLOCO 5 — Coerência entre Agentes e Skills

Os problemas a corrigir neste bloco são:

| Problema | Localização | Impacto |
|---|---|---|
| `optimizer_skill` retorna `urgency='moderate'` não reconhecida pelos schemas | `skills/optimizer_skill.py` | `simulation_skill` nunca disparada para ajuste de AC |
| `simulation_skill` só dispara com `urgency='immediate'`, mas `shutdown_equipment` raramente ocorre | `crew/tasks.py` | Skill de simulação funcionalmente morta |
| `min_acceptable_setpoint` calcula o **máximo** aceitável (nome invertido) | `skills/comfort_skill.py` | Confunde manutenção e pode induzir LLM a erro |
| Ajuste sazonal para temperaturas < 25°C comentado mas não implementado | `skills/forecast_skill.py` | Lógica incompleta |
| `JudgeAgent` não recebe `skills_output` estruturado na task description | `crew/tasks.py` | Juiz precisa inferir dados sem referência explícita |

### 5.1 `energy_agent/skills/optimizer_skill.py`

Corrija as urgências para usar apenas os valores do contrato (`'none'`, `'scheduled'`, `'immediate'`).
Substitua o bloco de lógica de decisão pelo seguinte:

```python
        # --- Lógica de decisão por prioridade ---

        # 1. Violação de conforto: preservar conforto, não alterar AC
        if comfort_violation:
            recommended_action = "no_action"
            urgency = "none"
            constraints_respected = True

        # 2. Fora do horário de operação: desligar equipamentos imediatamente
        elif not operating_hours:
            recommended_action = "shutdown_equipment"
            urgency = "immediate"
            ac_setpoint_target = None
            lighting_target = False
            constraints_respected = True

        # 3. Risco de pico com conforto alto (>= 60): ajustar AC — ação agendada
        elif peak_risk and comfort_score >= 60.0:
            recommended_action = "adjust_ac"
            ac_setpoint_target = round(ac_setpoint + 1.0, 1)  # aumenta setpoint em 1°C para economizar
            urgency = "scheduled"
            constraints_respected = True

        # 4. Risco de pico com conforto moderado (< 60): ajustar iluminação — ação agendada
        elif peak_risk and comfort_score < 60.0:
            if lighting_active:
                recommended_action = "adjust_lighting"
                lighting_target = False
                urgency = "scheduled"
                constraints_respected = True
            else:
                recommended_action = "no_action"
                urgency = "none"
                constraints_respected = True

        # 5. Caso padrão: sem ação necessária
        else:
            recommended_action = "no_action"
            urgency = "none"
            constraints_respected = True
```

**Nota sobre a correção do setpoint:** O ajuste de AC para economia energética em horário de pico
deve **aumentar** o setpoint (menos refrigeração = menos consumo), não diminuir. O código original
usava `ac_setpoint - 1.0`, o que aumentaria o consumo. Corrigido para `ac_setpoint + 1.0`.

### 5.2 `energy_agent/skills/comfort_skill.py`

Corrija o nome da variável e o cálculo do retorno para refletir corretamente o limite superior
aceitável. Substitua o bloco de cálculo e retorno por:

```python
        # --- Calcular limite máximo aceitável de setpoint ---
        # O sistema pode elevar o setpoint até o ponto onde o score ainda se mantém >= 40.
        # score = 100 - (delta_t * 8) - humidity_penalty - occupancy_penalty >= 40
        # => delta_t <= (60 - humidity_penalty - occupancy_penalty) / 8
        max_acceptable_delta: float = (
            100.0 - COMFORT_THRESHOLD - humidity_penalty - occupancy_penalty
        ) / TEMP_WEIGHT
        max_acceptable_delta = max(max_acceptable_delta, 0.0)

        # max_setpoint_celsius: setpoint máximo que ainda preserva conforto mínimo
        max_setpoint_celsius: float = round(ideal_temp + max_acceptable_delta, 2)

        return {
            "comfort_score": round(score, 2),
            "comfort_violation": comfort_violation,
            "max_setpoint_celsius": max_setpoint_celsius,   # renomeado de min_acceptable_setpoint
            "ideal_temp_celsius": ideal_temp,
        }
```

Atualize também o bloco de exceção para usar o mesmo nome:

```python
    except Exception as e:
        return {
            "comfort_score": 0.0,
            "comfort_violation": True,
            "max_setpoint_celsius": 23.0,
            "ideal_temp_celsius": 23.0,
            "error": f"Erro na avaliação de conforto: {str(e)}",
        }
```

### 5.3 `energy_agent/skills/forecast_skill.py`

Implemente o ajuste sazonal bidirecional que estava documentado no comentário mas ausente no código.
Substitua o bloco de ajuste sazonal por:

```python
        # --- Ajuste sazonal por temperatura ---
        # Acima de 25°C: +0.05 kWh por grau excedente (maior carga de refrigeração)
        # Abaixo de 25°C: -0.05 kWh por grau abaixo (menor carga de refrigeração)
        delta_temp: float = external_temp - 25.0
        predicted_kwh += delta_temp * 0.05
```

### 5.4 `energy_agent/crew/tasks.py`

Corrija as duas tarefas para que os agentes estejam alinhados ao contrato atualizado das skills:

```python
import json
from crewai import Task
from schemas.output_schema import MainAgentOutput, JudgeAgentOutput


def create_analysis_task(agent, environment_data: dict) -> Task:
    formatted_env = json.dumps(environment_data, indent=2, ensure_ascii=False)
    description = (
        "Você deve analisar os seguintes dados do ambiente:\n"
        f"{formatted_env}\n\n"
        "Execute o seguinte protocolo de ferramentas em ordem:\n\n"
        "1. Chame `forecast_skill` com: energy_kwh_last_24h, external_temp_celsius, "
        "calendar_event, tariff_peak.\n\n"
        "2. Chame `comfort_skill` com: environment_type, internal_temp_celsius, "
        "humidity_percent, occupancy_count.\n"
        "   ATENÇÃO: o retorno inclui 'max_setpoint_celsius' — este é o LIMITE MÁXIMO "
        "de setpoint que ainda preserva conforto mínimo (score >= 40). "
        "Nunca recomende um setpoint acima desse valor.\n\n"
        "3. Chame `optimizer_skill` com os JSONs retornados pelas duas skills acima, "
        "e com: tariff_current, tariff_peak, ac_active, lighting_active, "
        "ac_setpoint_celsius, operating_hours.\n"
        "   O campo 'urgency' no retorno será sempre um de: 'none', 'scheduled', 'immediate'.\n\n"
        "4. Chame `simulation_skill` SE E SOMENTE SE o campo 'urgency' retornado pelo "
        "optimizer for 'immediate' OU 'scheduled'. Para urgency='none', pule esta etapa.\n"
        "   Passe: optimizer_result_json (JSON do passo 3), predicted_kwh (do forecast), "
        "comfort_score (do comfort), tariff_current.\n\n"
        "5. Preencha o objeto MainAgentOutput com todos os campos:\n"
        "   - agent: 'EnergyOptimizerAgent'\n"
        "   - model: 'gemini-2.5-flash'\n"
        "   - timestamp: timestamp do ambiente\n"
        "   - environment_id: ID do ambiente\n"
        "   - skills_invoked: lista das skills efetivamente chamadas\n"
        "   - analysis: raciocínio técnico detalhado explicando cada decisão com base "
        "nos valores numéricos retornados pelas skills\n"
        "   - recommendation: objeto com os campos do optimizer (recommended_action, "
        "ac_setpoint_target, lighting_target, urgency, estimated_saving_brl, constraints_respected)\n"
        "   - skills_output: dicionário com chaves 'forecast', 'comfort', 'optimizer' e "
        "opcionalmente 'simulation', contendo os retornos brutos de cada skill chamada\n"
    )

    expected_output = (
        "Um objeto Pydantic MainAgentOutput contendo a análise completa do ambiente, "
        "a recomendação de ação energética e os retornos brutos de todas as skills executadas."
    )

    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
        output_pydantic=MainAgentOutput,
    )


def create_validation_task(agent) -> Task:
    description = (
        "Revise a análise e recomendação geradas pelo EnergyOptimizerAgent na tarefa anterior.\n\n"
        "Dados disponíveis na saída anterior:\n"
        "- skills_output.comfort.comfort_score: score de conforto (0-100)\n"
        "- skills_output.comfort.max_setpoint_celsius: limite máximo de setpoint seguro\n"
        "- skills_output.forecast.peak_risk: se há risco de pico tarifário\n"
        "- recommendation.urgency: 'none', 'scheduled' ou 'immediate'\n"
        "- recommendation.ac_setpoint_target: novo setpoint proposto (pode ser null)\n"
        "- skills_output.simulation: resultado da simulação, se disponível\n\n"
        "Regras de decisão obrigatórias:\n\n"
        "1. EXECUTE: comfort_score >= 40 E a ação não viola max_setpoint_celsius "
        "E a recomendação é coerente com o estado do ambiente.\n\n"
        "2. HOLD: a ação é prematura (urgency='none' com tarifa fora de pico) "
        "ou a simulation indicou recommendation_viable=False.\n\n"
        "3. OVERRIDE: comfort_score < 40 OU ac_setpoint_target > max_setpoint_celsius "
        "OU a recomendação é incoerente com ocupação ativa em horário de funcionamento. "
        "Neste caso, defina uma ação alternativa segura em action_taken e explique "
        "detalhadamente em override_reason.\n\n"
        "Preencha o objeto JudgeAgentOutput:\n"
        "   - agent: 'JudgeAgent'\n"
        "   - model: 'gemini-2.5-flash'\n"
        "   - timestamp: ISO atual\n"
        "   - environment_id: ID do ambiente\n"
        "   - action_id: UUID único gerado por você\n"
        "   - decision: 'execute', 'hold' ou 'override'\n"
        "   - action_taken: ação final autorizada (recommended_action, ac_setpoint_target, lighting_target)\n"
        "   - justification: texto com raciocínio baseado nos valores numéricos das skills\n"
        "   - main_agent_recommendation_accepted: True se não houve override\n"
        "   - override_reason: motivo detalhado se decision='override', senão string vazia\n"
        "   - estimated_impact: estimated_saving_brl e comfort_risk_detected\n"
    )

    expected_output = (
        "Um objeto Pydantic JudgeAgentOutput com a decisão operacional final validada, "
        "incluindo justificativa baseada em dados numéricos das skills."
    )

    return Task(
        description=description,
        expected_output=expected_output,
        agent=agent,
        output_pydantic=JudgeAgentOutput,
    )
```

### 5.5 `energy_agent/schemas/output_schema.py`

Renomeie `min_acceptable_setpoint` para `max_setpoint_celsius` em todos os campos dos schemas
Pydantic para manter consistência com a skill atualizada. O restante do arquivo permanece igual.

No bloco de schemas Pydantic, não há referência direta a esse campo (ele fica dentro de
`skills_output: Dict[str, Any]`), mas atualize o comentário de `MAIN_AGENT_REQUIRED_FIELDS`
para documentar a mudança:

```python
# Nota: comfort_skill retorna 'max_setpoint_celsius' (anteriormente 'min_acceptable_setpoint')
# Representa o limite superior de setpoint que preserva comfort_score >= 40
```

### 5.6 `energy_agent/test_skills.py`

Atualize as asserções para refletirem os campos renomeados:

```python
# Substituir:
assert "min_acceptable_setpoint" in comfort

# Por:
assert "max_setpoint_celsius" in comfort
```

---

## BLOCO 6 — Atualizar `.gitignore`

Substitua o conteúdo de `energy_agent/.gitignore` por:

```gitignore
# Variáveis de ambiente e segredos
.env

# Decisões do sistema de agentes
energy_agent/actions/*.json

# Cache Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python

# Ambiente virtual
.venv/
venv/
env/

# Banco de dados local
*.sqlite3

# Arquivos de IDE
.vscode/
.idea/
*.swp

# Distribuição
*.egg-info/
dist/
build/
```

---

## BLOCO 7 — Atualizar `README.md`

### 7.1 Seção de pré-requisitos

Substitua por:

```markdown
### Pré-requisitos

- Python 3.10 ou superior
- PostgreSQL 14 ou superior (servidor rodando localmente ou remoto)
- Chave de API do Google Gemini (`GEMINI_API_KEY`)
```

### 7.2 Seção de instalação — adicionar passo de banco de dados

Após o passo de instalação de dependências, adicione:

```markdown
### 2. Configurar Variáveis de Ambiente

Copie o arquivo de exemplo e preencha com seus valores:

```bash
cp energy_agent/.env.example energy_agent/.env
```

Edite `energy_agent/.env` e preencha obrigatoriamente:
- `DJANGO_SECRET_KEY`: gere uma chave segura com `python -c "import secrets; print(secrets.token_urlsafe(50))"`
- `GEMINI_API_KEY`: sua chave da API do Google Gemini
- `DB_PASSWORD`: senha do usuário PostgreSQL

### 3. Inicializar o Banco de Dados

```bash
# Cria o banco de dados se não existir
python energy_agent/core/db_init.py

# Aplica as migrações Django (cria as tabelas)
python energy_agent/manage.py migrate

# Popula os dados iniciais
python energy_agent/manage.py loaddata initial_data
```
```

---

## Resumo de Arquivos Modificados

| Arquivo | Bloco | Tipo de alteração |
|---|---|---|
| `requirements.txt` | 1 | Versões pinadas, adição do psycopg2 |
| `core/settings.py` | 1, 2, 3 | Segurança, PostgreSQL, versão |
| `.env.example` | 2 | Novo arquivo |
| `.gitignore` | 6 | Expandido |
| `core/db_init.py` | 3 | Novo arquivo |
| `api/models.py` | 4 | Modelos Django completos |
| `api/fixtures/initial_data.json` | 4 | Novo arquivo |
| `api/views.py` | 4 | Listas → ORM |
| `skills/optimizer_skill.py` | 5 | Urgências e lógica de setpoint corrigidas |
| `skills/comfort_skill.py` | 5 | Campo renomeado, semântica correta |
| `skills/forecast_skill.py` | 5 | Ajuste sazonal bidirecional |
| `crew/tasks.py` | 5 | Instruções alinhadas ao contrato das skills |
| `schemas/output_schema.py` | 5 | Comentário atualizado |
| `test_skills.py` | 5 | Asserções atualizadas |
| `README.md` | 7 | Pré-requisitos e passos de setup |

---

## Restrições de Implementação

1. **Não modifique** `crew/crew_runner.py`, `crew/agents.py`, `crew/tools.py`, `main.py`,
   `schemas/input_schema.py` além do que está explicitamente descrito acima.
2. **Não altere** a lógica de `simulation_skill.py` — apenas o gatilho em `tasks.py` foi ajustado.
3. **Mantenha** todos os endpoints da API com as mesmas URLs definidas em `api/urls.py`.
4. **Mantenha** a pasta `actions/` e o mecanismo de persistência em disco do `crew_runner.py`
   — ele é independente do banco de dados e serve como log de auditoria imutável.
5. **Não adicione** autenticação, rate limiting ou paginação — estas são melhorias fora do escopo
   desta modificação.
