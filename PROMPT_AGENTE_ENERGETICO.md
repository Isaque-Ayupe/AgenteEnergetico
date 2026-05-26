# Prompt — Implementação do Sistema de Agentes de Controle Energético

## Contexto do projeto

Você irá implementar dois agentes de IA para um sistema de **otimização de consumo energético em edifícios** (prédios administrativos, salas de aula, laboratórios e ambientes climatizados).

O sistema possui um **Agente Principal** responsável por analisar dados e retornar decisões estruturadas, e um **Agente Juiz** responsável por executar as ações e registrá-las em disco.

**Não implemente simuladores de dados, interfaces visuais ou dashboards. Foque exclusivamente nos agentes.**

\---

## Stack e configuração

* **Linguagem:** Python 3.11+
* **Modelo:** `gemini 2.5` (gemini API)
* **SDK:** `googlegenai` (oficial)
* **Variável de ambiente:** `GEMINI\_API\_KEY`
* **Estrutura de pastas esperada ao final:**

```
energy\_agent/
├── agents/
│   ├── \_\_init\_\_.py
│   ├── main\_agent.py       ← Agente Principal
│   └── judge\_agent.py      ← Agente Juiz
├── skills/
│   ├── \_\_init\_\_.py
│   ├── forecast\_skill.py   ← Skill: Previsão de consumo
│   ├── comfort\_skill.py    ← Skill: Índice de conforto térmico
│   ├── optimizer\_skill.py  ← Skill: Otimização de recomendações
│   └── simulation\_skill.py ← Skill: Simulação de cenários
├── actions/                ← Pasta criada pelo Agente Juiz para registros
│   └── (arquivos gerados automaticamente)
├── schemas/
│   ├── input\_schema.py     ← Schema de entrada de dados
│   └── output\_schema.py    ← Schemas dos JSONs de saída
├── main.py                 ← Entrypoint de execução
└── requirements.txt
```

\---

## Schemas de dados

### Entrada de dados (`InputData`)

O agente receberá um dicionário com os seguintes campos. Todos os campos podem ser `None` (o agente deve lidar com dados incompletos):

```python
{
  "environment\_id": str,           # ID único do ambiente/sala
  "environment\_type": str,         # "classroom" | "lab" | "office" | "corridor"
  "timestamp": str,                # ISO 8601
  "internal\_temp\_celsius": float,  # temperatura interna atual
  "external\_temp\_celsius": float,  # temperatura externa
  "humidity\_percent": float,       # umidade relativa %
  "occupancy\_count": int,          # quantidade de pessoas presentes
  "energy\_kwh\_current\_hour": float,# consumo atual da hora em kWh
  "energy\_kwh\_last\_24h": list\[float], # consumo das últimas 24h (lista de 24 valores)
  "ac\_active": bool,               # ar-condicionado ligado?
  "lighting\_active": bool,         # iluminação ligada?
  "ac\_setpoint\_celsius": float,    # set-point atual do AC
  "tariff\_current": float,         # tarifa atual R$/kWh
  "tariff\_peak": bool,             # está em horário de pico?
  "calendar\_event": str | None,    # "class" | "exam" | "recess" | "holiday" | None
  "operating\_hours": bool          # dentro do horário de funcionamento?
}
```

### Saída do Agente Principal (`MainAgentOutput`)

Retorno **sempre** em JSON estruturado:

```json
{
  "agent": "main\_agent",
  "model": "gemini-2.5-flash",
  "timestamp": "<ISO 8601>",
  "environment\_id": "<id>",
  "skills\_invoked": \["forecast", "comfort", "optimizer"],
  "analysis": {
    "current\_state": "<descrição concisa do estado atual>",
    "risk\_level": "low" | "medium" | "high",
    "comfort\_score": 0.0,
    "predicted\_kwh\_next\_hour": 0.0,
    "peak\_risk": true | false
  },
  "recommendation": {
    "action": "adjust\_ac" | "adjust\_lighting" | "shutdown\_equipment" | "no\_action",
    "ac\_setpoint\_target": 0.0 | null,
    "lighting\_target": true | false | null,
    "urgency": "immediate" | "scheduled" | "none",
    "estimated\_saving\_brl": 0.0,
    "reasoning": "<raciocínio detalhado em uma string>"
  },
  "skills\_output": {
    "forecast": { ... },
    "comfort": { ... },
    "optimizer": { ... },
    "simulation": { ... } | null
  }
}
```

### Saída do Agente Juiz (`JudgeAgentOutput`)

```json
{
  "agent": "judge\_agent",
  "model": "gemini-2.5-flash",

&#x20; "timestamp": "<ISO 8601>",
  "environment\_id": "<id>",
  "action\_id": "<uuid4>",
  "decision": "execute" | "hold" | "override",
  "action\_taken": {
    "type": "adjust\_ac" | "adjust\_lighting" | "shutdown\_equipment" | "no\_action",
    "parameters": { ... },
    "executed\_at": "<ISO 8601>"
  },
  "justification": "<raciocínio completo de por que esta decisão foi tomada>",
  "main\_agent\_recommendation\_accepted": true | false,
  "override\_reason": "<razão do override, se houver>" | null,
  "estimated\_impact": {
    "comfort\_preserved": true | false,
    "estimated\_saving\_brl": 0.0
  }
}
```

\---

## Agente Principal — Especificação detalhada

### Arquivo: `agents/main\_agent.py`

**Responsabilidades:**

1. Receber os dados de entrada (`InputData`)
2. Carregar contexto do estado atual do ambiente
3. Decidir autonomamente quais skills acionar e em qual ordem
4. Chamar cada skill como uma **tool call** da API GEMINI
5. Compor o resultado final e retornar o `MainAgentOutput` como JSON

**System prompt do agente:**

```
Você é o Agente de Controle Energético responsável por otimizar o consumo de energia em edifícios institucionais.

Seu objetivo é analisar os dados recebidos de cada ambiente e produzir uma recomendação precisa de ação.

Você possui 4 skills disponíveis como ferramentas:
- forecast\_skill: prevê o consumo de energia para a próxima hora com base no histórico
- comfort\_skill: calcula o índice de conforto térmico PMV do ambiente
- optimizer\_skill: gera a recomendação de menor custo que preserva conforto mínimo
- simulation\_skill: simula o impacto da ação antes de recomendá-la (use apenas quando urgency for "immediate" ou risk\_level for "high")

Regras de decisão:
1. Sempre execute forecast\_skill e comfort\_skill antes das demais
2. Execute optimizer\_skill após obter os resultados de forecast e comfort
3. Execute simulation\_skill somente se o risco for alto ou a ação for imediata
4. Se os dados estiverem incompletos, assuma valores conservadores (conforto = 50, previsão = média histórica disponível)
5. Nunca recomende ações que violem o conforto mínimo (comfort\_score < 40)
6. Seu retorno DEVE ser sempre um JSON válido e completo conforme o schema MainAgentOutput
```

**Implementação das tools (definições para a API):**

Implemente cada skill como uma tool Anthropic com `input\_schema` bem definido. Exemplo da estrutura:

```python
tools = \[
    {
        "name": "forecast\_skill",
        "description": "Prevê o consumo de energia (kWh) para a próxima hora com base no histórico das últimas 24h, temperatura externa, tipo de sala e calendário.",
        "input\_schema": {
            "type": "object",
            "properties": {
                "energy\_kwh\_last\_24h": {"type": "array", "items": {"type": "number"}},
                "external\_temp\_celsius": {"type": "number"},
                "environment\_type": {"type": "string"},
                "calendar\_event": {"type": "string"},
                "tariff\_peak": {"type": "boolean"}
            },
            "required": \["energy\_kwh\_last\_24h"]
        }
    },
    {
        "name": "comfort\_skill",
        "description": "Calcula o índice de conforto térmico PMV do ambiente. Retorna score de 0 a 100 e flag de violação.",
        "input\_schema": {
            "type": "object",
            "properties": {
                "internal\_temp\_celsius": {"type": "number"},
                "humidity\_percent": {"type": "number"},
                "occupancy\_count": {"type": "integer"},
                "ac\_setpoint\_celsius": {"type": "number"},
                "environment\_type": {"type": "string"}
            },
            "required": \["internal\_temp\_celsius", "humidity\_percent"]
        }
    },
    {
        "name": "optimizer\_skill",
        "description": "Gera a recomendação de ação de menor custo energético que ainda preserve o conforto mínimo. Recebe resultado do forecast e comfort.",
        "input\_schema": {
            "type": "object",
            "properties": {
                "forecast\_result": {"type": "object"},
                "comfort\_result": {"type": "object"},
                "tariff\_current": {"type": "number"},
                "tariff\_peak": {"type": "boolean"},
                "ac\_active": {"type": "boolean"},
                "lighting\_active": {"type": "boolean"},
                "ac\_setpoint\_celsius": {"type": "number"},
                "operating\_hours": {"type": "boolean"}
            },
            "required": \["forecast\_result", "comfort\_result", "tariff\_current"]
        }
    },
    {
        "name": "simulation\_skill",
        "description": "Simula o impacto da ação recomendada pelo optimizer antes da execução real. Use apenas quando urgency='immediate' ou risk\_level='high'.",
        "input\_schema": {
            "type": "object",
            "properties": {
                "optimizer\_result": {"type": "object"},
                "current\_state": {"type": "object"},
                "simulation\_horizon\_hours": {"type": "integer", "default": 2}
            },
            "required": \["optimizer\_result", "current\_state"]
        }
    }
]
```

**Lógica de execução das skills:**

As skills são executadas localmente (não são chamadas externas). Quando o LLM retornar um `tool\_use` block, o código Python deve:

1. Identificar qual skill foi chamada
2. Executar a função Python correspondente em `skills/`
3. Retornar o resultado como `tool\_result` na próxima mensagem
4. Continuar o loop até o LLM retornar `stop\_reason == "end\_turn"`

Implemente o loop de tool use corretamente com o padrão `agentic loop` do SDK Anthropic.

**Extração do JSON final:**

O LLM irá retornar o `MainAgentOutput` no último bloco de texto. Extraia e valide o JSON. Se a extração falhar, faça um retry com instrução explícita de correção.

\---

## Skills — Especificação detalhada

### `skills/forecast\_skill.py`

Função: `run\_forecast(input\_data: dict) -> dict`

Lógica interna (Python puro, sem LLM):

* Calcular média das últimas `n` horas disponíveis no histórico
* Aplicar ajuste sazonal baseado em `external\_temp\_celsius` (±0.05 kWh por grau acima de 25°C)
* Aplicar ajuste de calendário: `recess` ou `holiday` reduz 40%, `exam` aumenta 15%
* Aplicar multiplicador de pico: se `tariff\_peak == True`, sinalizar risco
* Retornar:

```python
{
  "predicted\_kwh\_next\_hour": float,
  "confidence": "high" | "medium" | "low",  # baseado na quantidade de dados históricos
  "peak\_risk": bool,
  "baseline\_avg\_kwh": float
}
```

### `skills/comfort\_skill.py`

Função: `run\_comfort(input\_data: dict) -> dict`

Lógica interna (Python puro, sem LLM):

* Calcular índice PMV simplificado:

  * Temperatura ideal por tipo de sala: `classroom`=22°C, `lab`=21°C, `office`=23°C, `corridor`=25°C
  * Desvio de temperatura: `delta\_t = abs(internal\_temp - ideal\_temp)`
  * Penalidade de umidade: se `humidity > 70%`, penalidade de 10 pontos
  * Penalidade de ocupação: se `occupancy > 30`, penalidade de 5 pontos
  * Score base: `100 - (delta\_t \* 8) - humidity\_penalty - occupancy\_penalty`
  * Clamp: `max(0, min(100, score))`
* Retornar:

```python
{
  "comfort\_score": float,           # 0–100
  "comfort\_violation": bool,        # True se score < 40
  "min\_acceptable\_setpoint": float, # set-point mínimo para score >= 40
  "ideal\_temp\_celsius": float
}
```

### `skills/optimizer\_skill.py`

Função: `run\_optimizer(input\_data: dict) -> dict`

Lógica interna (Python puro, sem LLM):

* Recebe `forecast\_result` e `comfort\_result`
* Se `comfort\_violation == True`: priorizar conforto, não reduzir AC
* Se `peak\_risk == True` e `comfort\_score >= 60`: recomendar redução do set-point em 1°C
* Se `operating\_hours == False`: recomendar desligamento de AC e iluminação
* Calcular economia estimada: `(predicted\_kwh \* 0.15) \* tariff\_current` (redução de 15% como baseline)
* Retornar:

```python
{
  "recommended\_action": str,
  "ac\_setpoint\_target": float | None,
  "lighting\_target": bool | None,
  "urgency": "immediate" | "scheduled" | "none",
  "estimated\_saving\_brl": float,
  "constraints\_respected": bool
}
```

### `skills/simulation\_skill.py`

Função: `run\_simulation(input\_data: dict) -> dict`

Lógica interna (Python puro, sem LLM):

* Simular aplicação da ação pelo `horizon\_hours` informado
* Estimar consumo após ação: `predicted\_kwh \* (1 - saving\_rate)`
* Estimar risco de violação de conforto ao longo do tempo
* Retornar:

```python
{
  "simulation\_horizon\_hours": int,
  "projected\_kwh\_total": float,
  "projected\_saving\_brl": float,
  "comfort\_risk\_detected": bool,
  "recommendation\_viable": bool
}
```

\---

## Agente Juiz — Especificação detalhada

### Arquivo: `agents/judge\_agent.py`

**Responsabilidades:**

1. Receber o `MainAgentOutput` (JSON do agente principal)
2. Avaliar se a recomendação deve ser executada, mantida em espera ou sobrescrita
3. Tomar a decisão final de forma autônoma
4. Gerar o `JudgeAgentOutput` como JSON
5. **Persistir o arquivo JSON de ação** na pasta `actions/`

**System prompt do agente juiz:**

```
Você é o Agente Juiz do sistema de controle energético. Você recebe a análise e recomendação do Agente Principal e decide se a ação deve ser executada, mantida em espera ou sobrescrita.

Suas responsabilidades:
1. Verificar se a recomendação respeita o conforto mínimo dos ocupantes (comfort\_score >= 40)
2. Verificar se a ação é coerente com o estado atual descrito (ex: não desligar AC se há ocupação e temperatura alta)
3. Verificar se a urgência declarada condiz com o risco\_level informado
4. Se tudo estiver consistente: decisão = "execute"
5. Se a ação for desnecessária ou prematura: decisão = "hold"  
6. Se houver incoerência ou risco ao conforto: decisão = "override" com ação alternativa segura

Regras absolutas:
- NUNCA autorize uma ação que reduza comfort\_score abaixo de 40
- Se operating\_hours == true e occupancy\_count > 0, sempre preserve AC mínimo (não desligue)
- Se risk\_level == "low" e tariff\_peak == false: decisão padrão é "hold" ou "no\_action"

Seu retorno DEVE ser sempre um JSON válido e completo conforme o schema JudgeAgentOutput.
```

**Lógica de persistência em disco:**

Após gerar o `JudgeAgentOutput`, o agente juiz deve:

```python
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

def save\_action(judge\_output: dict) -> str:
    actions\_dir = Path("actions")
    actions\_dir.mkdir(exist\_ok=True)
    
    action\_id = judge\_output.get("action\_id") or str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{timestamp}\_{action\_id\[:8]}\_{judge\_output\['environment\_id']}.json"
    
    filepath = actions\_dir / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(judge\_output, f, indent=2, ensure\_ascii=False)
    
    return str(filepath)
```

\---

## Entrypoint — `main.py`

Implemente um entrypoint que:

1. Receba um payload de entrada hardcoded (dados de exemplo reais, sem simulador)
2. Instancie e execute o Agente Principal
3. Imprima o `MainAgentOutput` formatado no terminal
4. Passe o resultado para o Agente Juiz
5. Imprima o `JudgeAgentOutput` formatado no terminal
6. Confirme o caminho do arquivo salvo em `actions/`

Exemplo de payload de entrada para o entrypoint:

```python
sample\_input = {
    "environment\_id": "sala\_101",
    "environment\_type": "classroom",
    "timestamp": "2025-05-25T14:30:00-03:00",
    "internal\_temp\_celsius": 27.5,
    "external\_temp\_celsius": 32.0,
    "humidity\_percent": 68.0,
    "occupancy\_count": 35,
    "energy\_kwh\_current\_hour": 4.2,
    "energy\_kwh\_last\_24h": \[1.1, 0.9, 0.8, 0.7, 0.6, 0.8, 1.2, 2.1, 3.5, 4.0,
                             4.3, 4.1, 3.9, 4.2, 4.5, 4.3, 3.8, 3.2, 2.5, 2.0,
                             1.8, 1.5, 1.3, 1.1],
    "ac\_active": True,
    "lighting\_active": True,
    "ac\_setpoint\_celsius": 24.0,
    "tariff\_current": 0.85,
    "tariff\_peak": True,
    "calendar\_event": "class",
    "operating\_hours": True
}
```

\---

## `requirements.txt`

```
googlegenai>=0.40.0
python-dotenv>=1.0.0
```

\---

## Instruções finais de implementação

1. Use `tool\_choice={"type": "auto"}` no Agente Principal para que o modelo decida autonomamente quais skills chamar.
2. O loop de tool use do Agente Principal deve ter um limite de segurança de **10 iterações** para evitar loops infinitos.
3. Todo JSON retornado pelos agentes deve ser validado com `json.loads()` antes de prosseguir. Em caso de falha, faça um retry com a mensagem: `"Seu retorno não é um JSON válido. Corrija e retorne apenas o JSON, sem markdown, sem explicações."`.
4. Use `temperature=0` nos dois agentes para garantir determinismo nas decisões.
5. Não use streaming.
6. As skills são **funções Python puras** — nenhuma delas faz chamada à API. Apenas o Agente Principal e o Agente Juiz fazem chamadas ao modelo.
7. O Agente Juiz **não usa tool calls** — ele recebe o JSON do Agente Principal diretamente no prompt e retorna sua decisão em uma única chamada.
8. Docstrings em português em todas as funções principais.
9. Tratamento de erros com `try/except` em todas as chamadas à API, com log de erro claro no terminal.
10. O arquivo de ação gerado pelo Agente Juiz deve conter **todo o payload** do `JudgeAgentOutput`, incluindo o `MainAgentOutput` original como campo `"main\_agent\_input"` para rastreabilidade completa.

```

