# Sistema de Agentes de Controle Energético

Um sistema inteligente para otimização de consumo energético em edifícios (prédios administrativos, salas de aula, laboratórios e ambientes climatizados). O sistema utiliza uma arquitetura baseada em LLMs (Gemini 2.5 Pro) atuando como agentes autônomos, auxiliados por *skills* (ferramentas) implementadas em Python puro.

## 🏗️ Arquitetura

O sistema é composto por duas entidades principais:

1.  **Agente Principal (`main_agent.py`)**: Analisa os dados de telemetria do ambiente e decide, autonomamente, quais *skills* invocar (via `function_calling`) para tomar uma decisão. Produz uma recomendação de ação energética e uma análise estruturada.
2.  **Agente Juiz (`judge_agent.py`)**: Recebe a recomendação do Agente Principal e atua como uma camada de segurança e coerência. Ele decide se a ação deve ser executada, mantida em espera ou sobrescrita, garantindo que regras estritas (como limites de conforto térmico) sejam respeitadas. Por fim, persiste a decisão em disco para auditoria.

### 🛠️ Skills (Ferramentas)

O Agente Principal tem acesso a quatro *skills* (funções Python sem uso de LLM) para basear suas decisões:

*   **Forecast Skill (`forecast_skill.py`)**: Prevê o consumo de energia da próxima hora analisando o histórico recente, aplicando ajustes sazonais (temperatura externa) e de calendário.
*   **Comfort Skill (`comfort_skill.py`)**: Calcula um índice de conforto térmico PMV simplificado (0 a 100) considerando temperatura ideal da sala, umidade e ocupação.
*   **Optimizer Skill (`optimizer_skill.py`)**: Baseado nas saídas de Forecast e Comfort, além de regras tarifárias e de funcionamento, recomenda a ação de melhor custo-benefício (ex: reduzir AC, desligar iluminação).
*   **Simulation Skill (`simulation_skill.py`)**: Projeta o impacto financeiro e o risco de degradação de conforto da ação recomendada ao longo de um horizonte de tempo.

## 🚀 Como Executar

### Pré-requisitos

*   Python 3.11+
*   Chave de API válida do Google Gemini.

### 1. Instalação

Navegue até o diretório do projeto e instale as dependências:

```bash
cd energy_agent
pip install -r requirements.txt
```

### 2. Configuração

O projeto usa o pacote `python-dotenv` para gerenciar variáveis de ambiente.
Preencha sua chave de API no arquivo `.env` localizado na raiz da pasta `energy_agent`:

```env
GEMINI_API_KEY=sua_chave_da_api_gemini_aqui
```

### 3. Execução

Para testar o fluxo end-to-end com um payload de dados fixo em uma sala de aula de exemplo, execute o ponto de entrada principal:

```bash
python main.py
```

Você verá no console:
1.  A resposta estruturada do **Agente Principal** em JSON.
2.  A avaliação final do **Agente Juiz** em JSON.
3.  A confirmação de que a ação final foi salva na pasta `actions/`.

## 📁 Estrutura de Pastas

```
energy_agent/
├── .env                    # Variáveis de ambiente (API Key)
├── requirements.txt        # Dependências do projeto
├── main.py                 # Entrypoint para teste end-to-end
├── actions/                # (Gerado em runtime) Registros das decisões do Juiz
├── agents/
│   ├── main_agent.py       # Lógica do Agente Principal (Tool Calling Loop)
│   └── judge_agent.py      # Lógica do Agente Juiz e persistência
├── schemas/
│   ├── input_schema.py     # Validação de dados de entrada do ambiente
│   └── output_schema.py    # Validação de JSONs de saída dos agentes
└── skills/
    ├── forecast_skill.py   # Skill de previsão de consumo
    ├── comfort_skill.py    # Skill de cálculo de conforto térmico
    ├── optimizer_skill.py  # Skill de otimização de ações
    └── simulation_skill.py # Skill de simulação de cenário futuro
```

## ⚙️ Tecnologias Utilizadas

*   **Linguagem**: Python
*   **LLM SDK**: `google-genai` (SDK Oficial do Google)
*   **Modelo de IA**: `gemini-2.5-pro` (Configurado com `temperature=0` para saídas determinísticas).
