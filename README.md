# ☀️ HSP Simulator - Solar Engine API

Este projeto é um simulador de **Horas de Sol Pleno (HSP)** projetado para cálculos de alta precisão em sistemas fotovoltaicos monofaciais e bifaciais. O motor de cálculo utiliza o **Modelo de Irradiância de Perez**, permitindo analisar o impacto da inclinação, azimute, albedo e altura de instalação no desempenho dos módulos.



## 🛠️ Funcionalidades Principais
- **Motor de Irradiância:** Implementação do modelo de Perez para decomposição de irradiância global e difusa.
- **Ganho Bifacial:** Cálculo técnico considerando o fator de visão (View Factor) e reflexão do solo (Albedo).
- **Integração NASA POWER:** Busca automática de dados meteorológicos históricos baseada em coordenadas (Latitude/Longitude).
- **Interface e API:** - **Dashboard:** Visualização comparativa via Streamlit.
  - **API REST:** Endpoint FastAPI para integração com outros sistemas (retorno em JSON).
- **Exportação:** Gerador de relatórios CSV otimizados para o padrão brasileiro (Excel).

## 🔌 Documentação da API (POST `/calcular`)

A API aceita requisições via método **POST** com o corpo em formato JSON.

### Parâmetros de Entrada (Request Body)
| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `latitude` | float | Latitude da usina (ex: -7.562) |
| `longitude` | float | Longitude da usina (ex: -37.688) |
| `inclinacao_graus` | int | Ângulo de inclinação do painel |
| `azimute_graus` | int | Orientação (0=Norte, 180=Sul) |
| `albedo_solo` | float | Fator de reflexão do solo (ex: 0.2) |
| `distancia_centro_modulo_chao` | float | Altura do centro da placa até o solo (m) |
| `tecnologia_celula` | string | Tecnologia (TOPCON, PERC, etc) |

### Exemplo de Saída (Response Body)
A resposta retorna a média anual e uma lista (`mensal`) contendo os valores de HSP de **Janeiro a Dezembro**, nesta ordem:

```json
{
  "media": 6.205,
  "mensal": [
    5.876, 6.126, 6.362, 6.271, 5.840, 5.578, 
    5.800, 6.505, 6.921, 6.741, 6.455, 5.991
  ]
}
```

> [!NOTE]
> Os valores da lista `mensal` representam o HSP ($kWh/m²/dia$) para cada mês do ano, facilitando a plotagem de gráficos ou cálculos de geração mensal.

## 📂 Estrutura do Repositório
- `core/`: O "cérebro" do projeto (Engines e lógica principal).
- `services/`: Gateways de comunicação com APIs externas.
- `utils/`: Constantes técnicas e ferramentas de exportação.
- `api.py`: Porta de entrada para requisições via API.
- `dashboard.py`: Interface visual interativa.

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

## 🧪 Como Executar os Testes de Validação

O projeto inclui um painel interativo para validar novas implementações ou verificar a precisão em diferentes localidades.

1. Certifique-se de que os arquivos `localidades.json` e `amostragem_sundata.json` estão na pasta `data/`.
2. Execute o painel de testes:

```bash
python -m tests.run_tests
```

### Opções Disponíveis no Painel:
* **[1] Simulação Técnica:** Gera cenários complexos (Muro solar, variação de altura e albedo) para testar o comportamento bifacial.
* **[2] Comparativo de Fontes:** Compara diretamente os dados brutos da NASA POWER com o SunData (CRESESB).
* **[3] Teste de Transposição Pura:** O teste mais rigoroso; valida se a física de inclinação da API é idêntica à dos softwares de referência.
* **[4] Executar Tudo:** Gera relatórios detalhados em `.csv` na pasta `data/` para análise profunda.

## 🚀 Como começar

1. Instale as dependências:
```bash
pip install -r requirements.txt
```
2
. Execute o Dashboard:
```bash
streamlit run dashboard.py
```

3. Execute a API:
```bash
uvicorn api:app --reload
```

## 📄 Licença
Distribuído sob a licença MIT. Veja o arquivo LICENSE para mais detalhes.