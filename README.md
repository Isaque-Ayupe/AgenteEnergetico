# Sistema de Agentes de Controle Energético (CrewAI + Django)

Um sistema inteligente para otimização de consumo energético em edifícios (prédios administrativos, salas de aula, laboratórios e ambientes climatizados). O sistema utiliza a framework **CrewAI** para orquestrar agentes autônomos cooperativos e expõe a solução como uma API Web REST construída em **Django** com banco de dados **PostgreSQL**.

---

## 🏗️ Arquitetura e Fluxo

O sistema conta com dois agentes que atuam de forma sequencial na orquestração:

1.  **Energy Optimizer Specialist (`crew/agents.py`)**: Analisa os dados de telemetria do ambiente físico e executa as ferramentas (*skills*) em Python necessárias para gerar a melhor recomendação de setpoint de temperatura e controle de iluminação.
2.  **Energy Control Operations Judge (`crew/agents.py`)**: Recebe a recomendação estruturada, valida contra restrições rígidas (garantindo que o conforto térmico mínimo seja mantido) e emite a decisão final de operação (`execute`, `hold` ou `override`). A resposta final é persistida em formato JSON na pasta `actions/` e retornada como um JSON HTTP.

### 🛠️ Skills (Ferramentas) do Agente Otimizador

O otimizador tem acesso às seguintes ferramentas de cálculo determinístico:

*   **Forecast Skill (`skills/forecast_skill.py`)**: Realiza previsão de consumo elétrico para a próxima hora com base no histórico das últimas 24 horas, ajustando por sazonalidade (temperatura externa) e eventos acadêmicos.
*   **Comfort Skill (`skills/comfort_skill.py`)**: Avalia o nível de conforto térmico predial (de 0 a 100) e calcula os limites aceitáveis de desvio de setpoint.
*   **Optimizer Skill (`skills/optimizer_skill.py`)**: Recomenda ações corretivas de baixo consumo energético com base na previsão e no conforto.
*   **Simulation Skill (`skills/simulation_skill.py`)**: Projeta a economia e avalia se há risco de degradação térmica futura caso a ação proposta seja imediata ou de alto impacto.

---

## 📁 Estrutura do Projeto

```
energy_agent/
├── manage.py               # Script de gerenciamento do Django
├── core/                   # Configurações globais do Django (urls.py, settings.py, db_init.py)
├── api/                    # App Django responsável pelos endpoints da API
│   ├── models.py           # Modelos: Zone, Agent, AgentControl, Alert, Report, Anomaly
│   ├── views.py            # Views REST: telemetria, CRUD de zonas/anomalias, simulação, otimização
│   ├── urls.py             # Definição de todas as rotas da API
│   └── migrations/         # Migrações do banco de dados
├── crew/                   # Módulo de agentes e tarefas CrewAI
│   ├── agents.py           # Definição dos agentes e carregamento do LLM
│   ├── tasks.py            # Definição das tarefas com schemas Pydantic
│   ├── tools.py            # Wrappers de ferramentas para o CrewAI
│   └── crew_runner.py      # Executor da orquestração e persistência
├── schemas/                # Schemas de validação de dados (Pydantic)
│   ├── input_schema.py     # Validação de dados do ambiente
│   └── output_schema.py    # Schemas Pydantic da saída estruturada
├── skills/                 # Lógica matemática pura em Python (sem LLM)
├── actions/                # Pasta gerada em runtime com as decisões finais do agente Juiz
├── .env                    # Variáveis de ambiente (API Key do Gemini, credenciais do banco)
└── requirements.txt        # Requisitos do projeto
```

---

## 🗄️ Modelos de Dados

O sistema persiste todos os dados operacionais no PostgreSQL usando os seguintes modelos Django:

| Modelo | Descrição | Campos Principais |
|--------|-----------|-------------------|
| **Zone** | Zona climática monitorada (sala, lab, bloco) | `zone_id`, `name`, `category`, `temp`, `temp_set`, `humidity`, `consumption_value`, `occupancy_value`, `status`, `ai_recommendation` |
| **Agent** | Agente de controle predial (spending, network) | `agent_id`, `name`, `agent_type`, `status`, `est_savings`, `active_rules`, `failure_risk`, `network_stability` |
| **AgentControl** | Controle individual (toggle) de funcionalidade | `control_id`, `name`, `description`, `enabled` |
| **Alert** | Alerta de anomalia ou evento operacional | `alert_id`, `title`, `description`, `alert_type`, `is_simulated`, `ai_diagnostic`, `ai_resolution` |
| **Report** | Relatório gerado pelo sistema | `report_id`, `report_type`, `date_generated`, `tags`, `file_type` |
| **Anomaly** | Registro persistente de anomalia real | `anomaly_id`, `anomaly_type`, `zone` (FK), `severity`, `status`, `diagnostic`, `action_taken`, `savings_impact`, `zone_snapshot_before`, `zone_snapshot_after` |

---

## 🚀 Como Executar o Projeto

### Pré-requisitos

- Python 3.10 a 3.13 (evite 3.14+)
- PostgreSQL 14 ou superior
- Chave de API do Google Gemini (`GEMINI_API_KEY`)

### 1. Instalação de Dependências

Se você tiver a ferramenta `uv` instalada (recomendado):

```bash
# Criar o ambiente virtual com Python 3.13
uv venv .venv --python 3.13
.\.venv\Scripts\Activate.ps1

# Instalar requisitos com o uv (muito mais rápido)
uv pip install -r energy_agent/requirements.txt
```

Caso contrário, utilizando o `pip` padrão:

```bash
# Windows PowerShell:
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux/MacOS:
python3 -m venv .venv
source .venv/bin/activate

# Instalar requisitos:
pip install -r energy_agent/requirements.txt
```

### 2. Configurar Variáveis de Ambiente

Copie o arquivo de exemplo e preencha com seus valores:

```bash
cp energy_agent/.env.example energy_agent/.env
```

Edite `energy_agent/.env` e preencha obrigatoriamente:
- `DJANGO_SECRET_KEY`: gere uma chave segura com `python -c "import secrets; print(secrets.token_urlsafe(50))"`
- `GEMINI_API_KEY`: sua chave da API do Google Gemini (obtida no Google AI Studio)
- `DB_USER`: usuário do PostgreSQL (padrão: `postgres`)
- `DB_PASSWORD`: senha do usuário PostgreSQL

### 3. Inicializar o Banco de Dados

```bash
# Cria o banco de dados se não existir
python energy_agent/core/db_init.py

# Aplica as migrações Django (cria todas as tabelas: zonas, agentes, alertas, anomalias, etc.)
python energy_agent/manage.py migrate
```

### 4. Execução Local via CLI (Modo de Teste)

Para rodar uma execução offline simulando um ambiente estático:

```bash
python energy_agent/main.py
```

### 5. Executando o Servidor Django (API REST)

```bash
python energy_agent/manage.py runserver
```

O servidor estará acessível em `http://localhost:8000/`.

---

## 🔌 Documentação da API REST

A API é stateless, não exige autenticação complexa para desenvolvimento e retorna respostas em JSON. Todas as rotas estão prefixadas com `/api/`.

### Endpoints Disponíveis

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/api/health` | Health check do servidor |
| `GET` | `/api/telemetry` | Dados completos de telemetria (zonas, agentes, alertas, relatórios, stats) |
| `POST` | `/api/zones` | Criar nova zona |
| `PUT` | `/api/zones/<zone_id>` | Atualizar zona existente |
| `DELETE` | `/api/zones/<zone_id>` | Remover zona |
| `POST` | `/api/agents/toggle` | Alternar controle de agente (habilitar/desabilitar funcionalidade) |
| `POST` | `/api/error-simulation` | **Gerar anomalia real** — aplica alterações reais na telemetria da zona |
| `GET` | `/api/anomalies` | Listar todas as anomalias registradas (filtro opcional: `?status=active`) |
| `GET` | `/api/anomalies/<anomaly_id>` | Detalhes de uma anomalia específica |
| `PUT` | `/api/anomalies/<anomaly_id>` | Atualizar anomalia (status, notas). Se `status=resolved`, restaura zona |
| `DELETE` | `/api/anomalies/<anomaly_id>` | Remover registro de anomalia |
| `POST` | `/api/optimize/` | Otimização energética via CrewAI (orquestração de agentes) |
| `POST` | `/api/agents` | Criar novo agente |
| `POST` | `/api/alerts` | Criar alerta manualmente |
| `POST` | `/api/reports` | Criar relatório |

---

### Endpoint: Gerar Anomalia Real (`/api/error-simulation`)

*   **Método**: `POST`
*   **Headers**: `Content-Type: application/json`

#### Payload:

```json
{
  "anomalyType": "Sobrecarga de HVAC - Temperatura Crítica",
  "zoneId": "zone-1",
  "severity": "high",
  "notes": "Chiller principal em manutenção"
}
```

#### Tipos de Anomalia Suportados:

| Tipo | Efeito Real na Zona |
|------|---------------------|
| Sobrecarga de HVAC - Temperatura Crítica | Temperatura +4~8°C, consumo +40~80kW, umidade +5~15% |
| Surto de Consumo Elétrico | Consumo +60~120kW, temperatura +1~3°C |
| Falha de Sensor Térmico | Temperatura definida como 99.9°C ou -1.0°C (leitura absurda) |
| Luzes Ativas Fora de Horário (Desperdício) | Consumo +15~30kW, ocupação reduzida |
| Pico de Umidade em Sala de Servidores | Umidade +25~40%, consumo +10~25kW |
| Fator de Potência Crítico nos Transformadores | Consumo +50~100kW, temperatura +2~5°C |

> **Nota**: Todos os deltas são multiplicados por um fator de severidade (low=0.5×, medium=0.75×, high=1.0×, critical=1.5×).

#### Resposta de Sucesso (`200 OK`):

```json
{
  "success": true,
  "alert": {
    "id": "anomaly-1718000000000",
    "title": "Anomalia: Sobrecarga de HVAC - Temperatura Crítica",
    "description": "Anomalia real detectada em Admin Block A (Administrative Offices). Severidade: high.",
    "type": "error",
    "timestamp": "Agora",
    "isSimulated": false,
    "aiDiagnostic": "Superaquecimento real detectado no fan coil principal...",
    "aiResolution": "Modulação de válvula fracionária executada..."
  },
  "anomaly": {
    "id": "anom-1718000000000",
    "anomalyType": "Sobrecarga de HVAC - Temperatura Crítica",
    "zoneId": "zone-1",
    "zoneName": "Admin Block A",
    "severity": "high",
    "status": "active",
    "diagnostic": "...",
    "actionTaken": "...",
    "savingsImpact": "Estimativa de economia de 15% na carga da zona...",
    "snapshotBefore": { "temp": 21.0, "humidity": 45.0, "consumptionValue": 45 },
    "snapshotAfter": { "temp": 27.3, "humidity": 55.0, "consumptionValue": 112 },
    "createdAt": "2026-06-14T14:00:00.000000+00:00"
  },
  "aiFeedback": {
    "diagnostic": "...",
    "actionTaken": "...",
    "savingsImpact": "..."
  }
}
```

---

### Endpoint: CRUD de Anomalias (`/api/anomalies`)

#### Listar Anomalias
*   `GET /api/anomalies` — retorna todas as anomalias
*   `GET /api/anomalies?status=active` — filtra por status (`active`, `resolved`, `dismissed`)

#### Resolver Anomalia (restaura a zona ao estado anterior)
*   `PUT /api/anomalies/<anomaly_id>`

```json
{ "status": "resolved" }
```

> Quando uma anomalia é marcada como `resolved`, os valores da zona (temperatura, umidade, consumo, status) são automaticamente restaurados ao estado salvo no `snapshotBefore`.

---

### Endpoint: Otimizar Ambiente (`/api/optimize/`)

*   **Método**: `POST`
*   **Headers**: `Content-Type: application/json`

#### Exemplo de Payload:

```json
{
  "environment_id": "sala_101",
  "environment_type": "classroom",
  "timestamp": "2025-05-25T14:30:00-03:00",
  "internal_temp_celsius": 27.5,
  "external_temp_celsius": 32.0,
  "humidity_percent": 68.0,
  "occupancy_count": 35,
  "energy_kwh_current_hour": 4.2,
  "energy_kwh_last_24h": [
    1.1, 0.9, 0.8, 0.7, 0.6, 0.8, 1.2, 2.1, 3.5, 4.0,
    4.3, 4.1, 3.9, 4.2, 4.5, 4.3, 3.8, 3.2, 2.5, 2.0,
    1.8, 1.5, 1.3, 1.1
  ],
  "ac_active": true,
  "lighting_active": true,
  "ac_setpoint_celsius": 24.0,
  "tariff_current": 0.85,
  "tariff_peak": true,
  "calendar_event": "class",
  "operating_hours": true
}
```

#### Resposta de Sucesso (`200 OK`):

```json
{
  "agent": "JudgeAgent",
  "model": "gemini-2.5-flash",
  "timestamp": "2025-05-25T14:35:00-03:00",
  "environment_id": "sala_101",
  "action_id": "f1a2b3c4-d5e6-7890-1234-567890abcdef",
  "decision": "execute",
  "action_taken": {
    "recommended_action": "adjust_lighting",
    "ac_setpoint_target": 24.0,
    "lighting_target": false
  },
  "justification": "A recomendação de desligar a iluminação é aprovada pois o conforto térmico está mantido...",
  "main_agent_recommendation_accepted": true,
  "estimated_impact": {
    "estimated_saving_brl": 0.3538,
    "comfort_risk_detected": false
  }
}
```

---

## 🛠️ Tecnologias Utilizadas

*   **Django 6.0.5**: Framework backend Python para rotas HTTP e ORM.
*   **PostgreSQL**: Banco de dados relacional para persistência de zonas, agentes, alertas, anomalias e relatórios.
*   **CrewAI 1.14.x**: Orquestrador agêntico para fluxo sequencial de pensamento e ferramentas.
*   **Google Gemini (gemini-2.5-flash)**: LLM principal para inferência, raciocínio e diagnósticos de anomalias.
*   **python-dotenv**: Carregamento seguro de variáveis de ambiente.
*   **psycopg2-binary / psycopg**: Drivers PostgreSQL para Python.
