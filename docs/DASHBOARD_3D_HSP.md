# Dashboard HSP — editor Solar 3D óptico interativo

## Escopo e arquitetura

O dashboard Streamlit agora utiliza um **componente Three.js interativo e
bidirecional**. Arrastar objetos na cena atualiza os valores X/Y em estado de
sessão Python, e essas posições são usadas diretamente para calcular a
sombra horária no HSP.

**Sem mudanças nos endpoints, schemas ou contratos da API**: continuam
inalterados `POST /calcular`, `/calcular-arranjo`,
`/recurso-solar/horario` e o campo legado `config_obstaculo`.
O mecanismo óptico de cena `scene3d` é opcional e acionado apenas pelo
dashboard. O laboratório experimental `solar3d` não foi incorporado.

## Executar localmente

Windows / PowerShell:

```powershell
git fetch origin
git switch dev
git pull --ff-only origin dev
python -m pip install -r requirements.txt
python -m pytest -q
python -m streamlit run dashboard.py
```

Enquanto a PR desta alteração ainda estiver aberta, trocar `dev`
por `feature/dashboard-solar3d-drag-mppt-groups`.

Abrir `http://localhost:8501`. A cena e a posição solar são
calculadas localmente, mas **o navegador precisa alcançar
`cdn.jsdelivr.net`** para carregar Three.js e OrbitControls.
O cálculo HSP anual com NASA POWER ou PVGIS necessita acesso à fonte
climática. O pacote do componente está em
`dashboard/components/solar3d_drag/`.

## Usar o editor

- **Clicar numa placa ou obstáculo:** seleciona o objeto. Enquanto
  o botão esquerdo estiver pressionado, mover o mouse desloca o objeto
  **no plano horizontal (Leste X, Norte Y)**. Soltar grava a posição.
- **Ctrl+clique** (ou Command no macOS): adiciona/remove placas da
  seleção. Arrastar uma das selecionadas move todas, preservando suas
  posições relativas. A seleção também pode incluir obstáculos.
- **Shift+clique em uma placa:** seleciona as placas do mesmo MPPT.
  Alternativamente, marcar *Arrastar MPPT inteiro ao clicar numa placa*.
- **Arrastar o fundo vazio:** orbita a câmera. Roda do mouse: zoom.
  **Esc:** limpa a seleção.
- **Alturas:** são editadas **somente por campo numérico** em
  *Gerenciar MPPTs, placas e dimensões*. Um arraste nunca altera Z.
  A altura base do painel lateral é o padrão para **placas novas**;
  existe botão para aplicá-la a todas as placas existentes.
- **Adicionar MPPT:** cria grupo visual rotulado; é permitido ter
  múltiplas placas por grupo e transferir placas entre grupos via
  seletor. Excluir grupo só é possível se vazio.
- **Adicionar placa neste MPPT:** cria placa com ID persistente,
  dimensões/orientação compartilhadas, altura inferior própria e
  posição independente.
- **Adicionar obstáculo:** cria uma nova caixa; largura,
  profundidade e altura são campos numéricos, e X/Y são arrastáveis.
- **Data, hora e fuso:** controlam o Sol na prévia. O botão
  **Calcular e comparar** executa a análise climática horária usando
  o estado confirmado dos objetos.

Limites para preservar responsividade: até **48 placas**, **16 MPPTs
visuais**, **32 obstáculos**. Projetos grandes podem exigir mais tempo
de processamento.

## Referência geométrica e ótica

Coordenadas métricas ENU: X Leste, Y Norte, Z altura. O azimute do
painel é geográfico (0=N, 90=L, 180=S, 270=O); inclinação 0° significa
plano horizontal. Comprimento acompanha a rampa em Retrato; largura
acompanha em Paisagem.

Para cada placa individual:

```
altura_do_centro = altura_da_borda_inferior +
                   comprimento_na_rampa * sen(inclinacao)/2
```

A referência de entrada é sempre **a borda mais baixa do plano do
módulo**, não o centro, moldura ou espessura do suporte. Placas da
mesma cena compartilham dimensões, inclinação e azimute, mas podem
ter posições e alturas inferiores individuais.

O motor calcula interseção de raios solares com volumes retangulares
(AABB), usando amostras na face frontal: **5×5 para a série horária** e
**8×6 para a prévia**. A sombra de cada placa é calculada
independentemente, inclusive se cada uma está em um MPPT diferente.
A fração média da área frontal bloqueada reduz somente a parcela
direta da irradiância incidente:

```
POA_com_sombra = POA_global - fracao_sombreada * POA_direta
```

Grupos MPPT são **somente etiquetas para selecionar e arrastar
placas**; a soma óptica não simula strings em série/paralelo, corrente
comum, diodos, mismatch, recorte do inversor ou DC/AC.

## Testes e homologação

```bash
python -m pytest -q
node --input-type=module --check < dashboard/components/solar3d_drag/editor.js
node --test tests/dashboard/test_scene3d_selection.mjs
```

Os testes verificam: raycasting por placa, grupos e posições
independentes, altura pela borda, `Ctrl`/ `Shift` e
sincronização apenas de X/Y. O teste `compileall` e `pytest` é
executado no GitHub Actions; testes JS de seleção também constam do CI.

**Roteiro manual no navegador:**

1. Criar MPPT 1 com duas placas e MPPT 2 com uma placa.
2. Arrastar somente a primeira: a segunda não deve se mover.
3. Selecionar as duas do MPPT 1 com `Ctrl`, arrastar e conferir
   preservação do espaçamento.
4. `Shift+clique` na placa do MPPT 2 e mover o grupo.
5. Criar dois obstáculos, arrastar um diante de uma das placas,
   alterar a altura digitando e conferir a sombra na prévia.
6. Clicar em **Calcular e comparar** e observar HSP com/sombra.
   Sem obstáculos, a diferença deve ser zero.
7. Recarregar a aba: a cena ainda **não é persistida em banco**,
   logo deve retornar ao estado inicial da sessão.
8. Executar regressões HTTP dos contratos legados: não houve
   alteração da API nesta implementação.

## Limitações explícitas

Os módulos são superfícies sem espessura, obstáculos são paralelepípedos
sem rotação em terreno plano. O editor não simula a interferência elétrica
entre placas, sombreamento entre fileiras, vegetação, horizonte,
oclusão difusa da abóbada, albedo obstruído ou geometria georreferenciada.
A projeção de sombra **desenhada** no solo é ilustrativa e encurtada a
25 metros; o cálculo numérico de sombra usa interseção de raios
independente dessa visualização. A amostragem de área pode perder
sombras finas. Não equivale a certificação de engenharia nem a PVsyst.

Os controles agrupam placas com **mesma orientação e dimensões**;
não é possível modelar orientações diferentes por MPPT nesta versão.
A implementação usa scripts ES modules remotos do jsDelivr:
para instalações completamente offline, será necessário empacotar
Three.js localmente.
