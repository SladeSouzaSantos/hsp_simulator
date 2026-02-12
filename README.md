# ☀️ HSP Simulator - Solar Engine API

Este projeto é um ecossistema de alta precisão para simulação de **Horas de Sol Pleno (HSP)**, especializado em sistemas fotovoltaicos monofaciais e bifaciais. Diferente de calculadoras simples, este motor utiliza o **Modelo de Irradiância de Perez (Perez-1990)** para realizar a transposição de irradiância com rigor científico, permitindo prever ganhos e perdas em cenários complexos de instalação.

---

## 🛠️ Funcionalidades Principais
* **Motor de Irradiância Avançado:** Implementação do modelo de Perez para decomposição e transposição de irradiância global, difusa e direta.
* **Análise de Ganho Bifacial:** Cálculo baseado em *View Factor* (Fator de Visão) e Albedo, permitindo simular desde instalações de solo até **Muros Solares** (instalações verticais) com precisão comprovada.
* **Engine de Sombreamento 3D:** Avaliação do impacto de obstruções fixas (edifícios, muros, postes) com base na geometria solar horária, calculando a penetração da sombra no módulo.
* **Integração NASA POWER:** Consumo automatizado de dados meteorológicos históricos e climatológicos via API.
* **Ecossistema Híbrido:** API REST (FastAPI) e Dashboard analítico (Streamlit).
    * **API REST (FastAPI):** Endpoints escaláveis com validação Pydantic V2 para integração com CRMs ou softwares de engenharia.
    * **Dashboard (Streamlit):** Interface analítica para visualização de curvas mensais e comparação de cenários.
* **Sistema de Benchmarking:** Auditoria automatizada que valida a precisão do motor contra dados reais do **SunData (CRESESB)**.
* **Rigor Técnico:** Validação sistemática contra dados do **SunData (CRESESB)**, mantendo desvios médios globais abaixo de 3%.

---

## 🔌 Documentação da API (POST `/calcular`)

A API utiliza **Pydantic V2** para garantir tipagem rigorosa e utiliza *aliases* para fornecer nomes técnicos padronizados no JSON de saída.

### Principais Endpoints
* `POST /calcular`: Cálculo detalhado para um único cenário técnico.
* `POST /calcular-arranjo`: Processamento em lote para múltiplos módulos, otimizando as chamadas de dados da NASA via cache.

### 1. POST `/calcular`
Ideal para simulações rápidas de um único cenário técnico.

**Parâmetros de Entrada:**
| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `latitude` | float | Latitude (ex: -7.562) |
| `longitude` | float | Longitude (ex: -37.688) |
| `inclinacao_graus` | int | Ângulo de inclinação (0 a 90°) |
| `azimute_graus` | int | Orientação (0=N, 180=S) |
| `albedo_solo` | float | Refletividade do solo (ex: 0.2) |
| `distancia_centro_modulo_chao` | float | Altura de instalação (m) |
| `tecnologia_celula` | string | TOPCON, PERC, AL BSF |
| `is_bifacial` | bool | Ativar face traseira (Default: true) |
| `config_obstaculo` | dict | (Opcional) Objeto com `altura_obstaculo`, `distancia_obstaculo` e `referencia_azimutal_obstaculo`. |

---

### 2. POST `/calcular-arranjo`
Projetado para processar múltiplas placas (strings ou arranjos complexos) em uma única chamada, otimizando o consumo de dados da NASA.

**Parâmetros de Entrada:**
| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `latitude` | float | Latitude comum ao arranjo |
| `longitude` | float | Longitude comum ao arranjo |
| `itens` | list[dict] | Lista de objetos contendo `id_placa` e suas configurações técnicas individuais (inclinação, obstáculos, etc). |

> [!TIP]
> Este endpoint realiza apenas **uma consulta** à API da NASA para todo o lote, garantindo alta performance mesmo em grandes arranjos.

---

### 📊 Exemplo de Resposta Padronizada
O motor retorna os resultados comparando o cenário real (com perdas) e o potencial teórico (referência):

```json
{
  "total_placas": 1,
  "resultados": [
    {
      "id_placa": "Módulo_Norte_01",
      "kWh/m²/dia": {
        "real": {
          "media": 5.882,
          "mensal": [5.55, 5.84, 5.99, 5.69, 5.67, 5.10, 5.51, 6.31, 6.57, 6.43, 6.17, 5.72]
        },
        "referencia": {
          "media_sem_sombra": 5.942,
          "mensal_sem_sombra": [5.62, 5.84, 5.99, 5.76, 5.79, 5.36, 5.62, 6.31, 6.57, 6.43, 6.17, 5.79]
        }
      },
      "perda_sombreamento_estimada": "1.6%"
    }
  ]
}
```

> [!NOTE]
> Os valores da lista `mensal` representam o HSP ($kWh/m²/dia$) para cada mês do ano, facilitando a plotagem de gráficos ou cálculos de geração mensal.

---

## 📂 Estrutura do Repositório

O projeto segue uma arquitetura modular focada em separação de responsabilidades e rigor técnico:

- **`core/`**: O coração do ecossistema. Contém os motores de física (`perez_engine.py`) e de geometria solar/sombras (`shadow_engine.py`).
- **`benchmarks/`**: O centro de garantia de qualidade. Contém o `auditor.py` e scripts para execução de auditorias técnicas e validação de precisão.
- **`services/`**: Camada de infraestrutura para comunicação com a NASA POWER e repositórios de dados climatológicos.
- **`schemas/`**: Contratos de dados (Pydantic V2) que garantem a integridade das requisições e a tipagem rigorosa da API.
- **`tests/fixtures/`**: Dados de referência imutáveis (Gabarito CRESESB) utilizados para validar a física do motor contra padrões reais.
- **`data/`**: Pasta destinada aos arquivos de localidades e saída dos relatórios de auditoria em `.csv`.
- **`utils/`**: Ferramentas utilitárias, como o `exporter.py` (otimizado para Excel BR) e constantes técnicas de albedo e células.
- **`api.py`**: Ponto de entrada FastAPI com documentação automática e suporte a processamento em lote.
- **`dashboard.py`**: Interface visual analítica desenvolvida em Streamlit para visualização de curvas e comparação de cenários.

---

## ⚖️ Validação e Rigor Técnico

Para garantir a precisão dos cálculos, o projeto conta com uma bateria de testes que compara os resultados do motor com o **SunData (CRESESB)**, a principal referência de engenharia solar no Brasil.

### 📊 Resultados de Validação (Transposição Pura)
A tabela abaixo compara o HSP base (inclinação 0°) do SunData com a previsão do nosso motor para diferentes inclinações, validando a precisão matemática do modelo de Perez.

| Cidade | Ângulo | SunData (Real) | HSP Simulator | Desvio (%) |
| :--- | :--- | :--- | :--- | :--- |
| **Natal/RN** | 4° | 5.68 | 5.68 | **0.00%** |
| **Natal/RN** | 6° | 5.68 | 5.68 | **+0.03%** |
| **Natal/RN** | 16° | 5.60 | 5.59 | **-0.12%** |
| **Caicó/RN** | 5° | 5.92 | 5.93 | +0.20% |
| **Caicó/RN** | 6° | 5.92 | 5.93 | +0.20% |
| **Caicó/RN** | 17° | 5.83 | 5.84 | +0.23% |
| **Petrolina/PE** | 7° | 5.80 | 5.81 | +0.23% |
| **Petrolina/PE** | 9° | 5.80 | 5.81 | +0.23% |
| **Petrolina/PE** | 21° | 5.68 | 5.70 | +0.39% |
| **Manaus/AM** | 3° | 4.42 | 4.42 | **0.05%** |
| **Manaus/AM** | 4° | 4.42 | 4.42 | **0.09%** |
| **Porto Alegre/RS** | 22° | 4.62 | 4.67 | +1.12% |
| **Porto Alegre/RS** | 30° | 4.60 | 4.65 | +1.08% |
| **Porto Alegre/RS** | 50° | 4.26 | 4.30 | +0.93% |
| **Sao Jose dos Campos** | 20° | 4.80 | 4.72 | +1.69% |
| **Sao Jose dos Campos** | 23° | 4.80 | 4.72 | +1.79% |
| **Sao Jose dos Campos** | 35° | 4.72 | 4.60 | +2.69% |

> [!NOTE]
> Os testes cobrem desde latitudes equatoriais até o extremo sul do Brasil, mantendo um erro médio global abaixo de 3%, o que confere grau de engenharia ao simulador.

> [!TIP]
> A precisão de 0.00% em latitudes próximas ao equador demonstra que a implementação do modelo de transposição está perfeitamente alinhada com os padrões de mercado.

---

## 🧪 Como Executar as Auditorias (Benchmarks)

O sistema conta com um **Solar Auditor** dedicado que valida tanto a física de transposição quanto a sensibilidade da engine de sombreamento. Diferente de testes simples, os benchmarks geram relatórios de auditoria para análise de engenharia.

1. Certifique-se de que os arquivos de referência estão em suas respectivas pastas (`data/` e `tests/fixtures/`).

2. Execute a bateria completa de auditoria:
```bash
python -m benchmarks.run_benchmarks
```

### O que o sistema atesta:
* **Validação CRESESB (Transposição):** Compara o motor contra o gabarito oficial do SunData em múltiplas latitudes, validando a precisão matemática do modelo de Perez.
* **Sensibilidade de Obstrução:** Verifica se obstáculos (muros, prédios, postes) geram perdas de HSP coerentes com a geometria solar horária.
* **Geração de Relatórios:** Exporta automaticamente os resultados para análise técnica detalhada.

> [!IMPORTANT]
> Os relatórios de auditoria são salvos em `VALIDACAO_CRESESB_ATTESTED.csv` e `BENCHMARK_SOMBRA_FINAL.csv` dentro da pasta `data/`.

---

## 🚀 Como começar

1. Instale as dependências:
```bash
pip install -r requirements.txt
```

2. Execute o Dashboard (Front-End):
```bash
streamlit run dashboard.py
```

3. Execute a API (Back-End):
```bash
uvicorn api:app --reload
```

---

## 📄 Licença
Distribuído sob a licença MIT. Veja o arquivo LICENSE para mais detalhes.
