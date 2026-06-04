# Sistema de Agentes de Controle Energético (CrewAI + Django)

Um sistema inteligente para otimização de consumo energético em edifícios (prédios administrativos, salas de aula, laboratórios e ambientes climatizados). O sistema utiliza a framework **CrewAI** para orquestrar agentes autônomos cooperativos e expõe a solução como uma API Web REST de resposta rápida construída em **Django**.

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
├── core/                   # Configurações globais do Django (urls.py, settings.py)
├── api/                    # App Django responsável pelos endpoints da API (views.py, urls.py)
├── crew/                   # Módulo de agentes e tarefas CrewAI
│   ├── agents.py           # Definição dos agentes e carregamento do LLM
│   ├── tasks.py            # Definição das tarefas com schemas Pydantic
│   ├── tools.py            # Wrappers de ferramentas para o CrewAI
│   └── crew_runner.py      # Executor da orquestração e persistência
├── schemas/                # Schemas de validação de dados
│   ├── input_schema.py     # Validação de dados do ambiente
│   └── output_schema.py    # Schemas Pydantic da saída estruturada
├── skills/                 # Lógica matemática pura em Python (sem LLM)
├── actions/                # Pasta gerada em runtime onde são salvas as decisões finais do juiz
├── .env                    # Variáveis de ambiente contendo o token da API do Gemini
└── requirements.txt        # Requisitos do projeto
```

---

## 🚀 Como Executar o Projeto

### Pré-requisitos

- Python 3.10 ou superior
- PostgreSQL 14 ou superior (servidor rodando localmente ou remoto)
- Chave de API do Google Gemini (`GEMINI_API_KEY`)

### 1. Instalação de Dependências

> [!WARNING]
> Evite utilizar o Python 3.14 (ou superior pré-lançamento), pois bibliotecas compiladas como o `pydantic-core` não possuem pacotes binários estáveis pré-compilados para essa versão ainda. Recomenda-se utilizar o **Python 3.13** (ou inferior).

Se você tiver a ferramenta `uv` instalada (recomendado):

```bash
# Criar o ambiente virtual com Python 3.13
uv venv .venv --python 3.13
.\.venv\Scripts\Activate.ps1

# Instalar requisitos com o uv (muito mais rápido)
uv pip install -r energy_agent/requirements.txt
```

Caso contrário, utilizando o `python` tradicional (certifique-se de que é a versão 3.13):

```bash
# Se utilizar Windows Powershell:
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Se utilizar Linux/MacOS:
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
- `GEMINI_API_KEY`: sua chave da API do Google Gemini
- `DB_PASSWORD`: senha do usuário PostgreSQL

### 3. Inicializar o Banco de Dados

Execute o script de inicialização para criar o banco de dados caso não exista e em seguida aplique as migrações Django:

```bash
# Cria o banco de dados se não existir
python energy_agent/core/db_init.py

# Aplica as migrações Django (cria as tabelas)
python energy_agent/manage.py migrate
```

### 4. Execução Local via CLI (Modo de Teste)

Para rodar uma execução offline simulando um ambiente estático através de dados de teste, execute:

```bash
python energy_agent/main.py
```

### 5. Executando o Servidor Django (API REST)

Para inicializar o servidor de desenvolvimento Django localmente na porta 8000:

```bash
python energy_agent/manage.py runserver
```

---

## 🔌 Documentação da API REST

A API do sistema é stateless, não exige autenticação complexa para desenvolvimento e retorna respostas diretamente em formato JSON.

### Endpoint: Otimizar Ambiente

*   **URL**: `/api/optimize/`
*   **Método**: `POST`
*   **Headers**: `Content-Type: application/json`

#### Exemplo de Payload (Corpo da Requisição JSON):

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

#### Exemplo de Resposta de Sucesso (`200 OK`):

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
  "justification": "A recomendação de desligar a iluminação é aprovada pois o conforto térmico está mantido (score = 51) e o horário é de pico de tarifa...",
  "main_agent_recommendation_accepted": true,
  "override_reason": "",
  "estimated_impact": {
    "estimated_saving_brl": 0.3538,
    "comfort_risk_detected": false
  },
  "main_agent_input": {
     "...": "dados originais analisados pelo otimizador"
  },
  "_saved_filepath": "C:\\caminho\\do\\arquivo\\salvo.json"
}
```

---

## 🛠️ Tecnologias Utilizadas

*   **Django 6.x**: Framework backend python utilizada para gerenciar as rotas e requisições HTTP REST.
*   **CrewAI 1.14.x**: Orquestrador agêntico que realiza o fluxo sequencial de pensamento e ferramentas.
*   **Google Gemini (gemini-2.5-flash)**: LLM principal para inferência, raciocínio e estruturação de respostas.
