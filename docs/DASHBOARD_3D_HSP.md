# Dashboard HSP — Análise de sombreamento em cena 3D

## Objetivo

O dashboard Streamlit substitui o controle de **tela vertical retangular**
por um visualizador 3D orbitável com módulos e obstáculos volumétricos.
O propósito é **estimar redução de HSP por perda da irradiância direta
na face do módulo**, sem modelar perdas elétricas ou especificações de
inversores, strings, substrings ou MPPTs.

A cena do dashboard é uma implementação óptica separada do laboratório
`solar3d/feature/solar3d-lab`. Esse laboratório inclui pesquisas elétricas
que **não** foram incorporadas a esta mudança.

## Como executar

No Windows (PowerShell), na pasta do repositório:

```powershell
git fetch origin
git switch feature/dashboard-solar3d-optical
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
python -m streamlit run dashboard.py
```

Abrir http://localhost:8501. Para o cálculo mensal/anual, selecionar
**NASA POWER** ou **PVGIS** (requer internet e disponibilidade da fonte).
A cena 3D e a posição solar podem ser visualizadas sem solicitar dados
meteorológicos à API externa.

## Usar o visualizador

1. No painel lateral, informar local, azimute, inclinação, tecnologia,
   **comprimento e largura físicos** do módulo. Em Retrato o comprimento
   acompanha a rampa; em Paisagem, a largura a acompanha.
2. Preencher **Altura da borda inferior ao solo (m)**. Para inclinação β,
   o centro do plano do módulo é
   `altura_borda + comprimento_na_rampa × sen(β) / 2`. A altura informada
   nunca é reinterpretada como altura central.
3. Configurar número de módulos, módulos por fileira, espaçamento,
   obstáculos (X=Leste, Y=Norte), largura, profundidade e altura. Os
   obstáculos são caixas retangulares apoiadas no plano do solo.
4. Alterar data, horário e offset UTC para prévia da direção solar,
   projeção das sombras no solo e fração de **área frontal bloqueada**.
   Girar/zoom com o mouse no gráfico Plotly/WebGL. Posições são editadas
   numericamente, não por arraste direto de objetos.
5. Clicar em **Calcular e comparar** para usar o ano completo de
   irradiância horária do motor HSP. Conferir HSP com/sombra, GHI
   horizontal, média mensal e perdas percentuais ópticas.

O campo de altura aplica-se ao ponto mais baixo do **plano do módulo**
(não à face inferior de uma espessura de moldura). O desenho aproxima
a placa por uma superfície sem espessura. Não representa levantamento
georreferenciado nem a geometria física dos suportes.

## Contrato físico e compatibilidade

- Plano local: X=Leste, Y=Norte, Z=vertical; azimute 0=N, 90=L,
  180=S, 270=O. Inclinação 0=horizontal e 90=vertical.
- Obstáculos são volumes ortogonais aos eixos locais; oclusão da
  face é feita por interseção de raios com caixas AABB.
- Cada módulo é amostrado em uma grade de 5×5 pontos por hora para
  o HSP e 8×6 pontos na prévia. A média de frações por módulo é
  ponderada por igual área, pois os módulos da cena têm dimensões
  idênticas; não é uma perda de potência elétrica.
- A série POA do pvlib é mantida e o bloqueio atua **uma única vez**
  na componente direta: `POA_com_sombra = POA_global − sombra ×
  POA_direta`. Difusa, refletida e componente traseira bifacial
  permanecem sem obstrução.
- Uma série de clima completa tem 8760 ou 8784 horas. O raycast
  funciona por lotes de 168 horas para limitar memória.
- Sem obstáculos, os resultados com/sombra são idênticos.
- A API `POST /calcular`, `/calcular-arranjo`, o parâmetro legado
  `config_obstaculo` e `POST /recurso-solar/horario` permanecem
  compatíveis. Somente o fluxo de UI antigo foi retirado do dashboard.
- Não há sincronização desta cena com projetos do GreenCity OS.
  A cena é mantida pela sessão Streamlit, não em banco persistente.

## Limitações

Amostragem em grade pode não detectar sombras muito finas. O 3D
mostra uma projeção aproximada no chão, limitada visualmente a 25 m
quando o Sol está próximo ao horizonte; essa limitação de exibição
**não afeta** o raycast que produz o HSP. Não modelamos terreno,
árvores, obstáculos rotacionados, oclusão difusa do céu, IAM, albedo
obstruído, múltiplas orientações por fileira, perdas por célula, bypass,
mismatch, MPPT ou DC/AC. A previsão não é um relatório certificado.

## Testes

```bash
python -m pytest -q tests/unit/test_scene3d_shading.py tests/dashboard
python -m pytest -q
```

Smoke recomendado: obstáculo ao Norte e Sol ao Norte sombreiam; girar
o Sol ao Sul não sombreia. Aumentar a altura da borda reduz, sob
geometria adequada, a sombra recebida. Retrato/Paisagem mudam a
altura do centro e as dimensões do plano. Remover obstáculos produz
HSP com sombra igual à referência. Verificar resultados idênticos
da API legada antes/depois da atualização.
