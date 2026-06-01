; ============================================================================
; SIMULACAO DE EVACUACAO DE EDIFICIO ALTO EM SITUACAO DE INCENDIO
; Edificio de 30 andares (120 m), grade 20x20 por andar
; Conformidade com ABNT NBR 9077: elevadores bloqueados, evacuacao por escadas
; Abordagem hibrida ABM + Automato Celular + aproximacao CFD (difusao local)
;
; CORRECOES da versao anterior:
;  - Mundo NAO toroidal (wrap horizontal e vertical = OFF na interface)
;  - Geometria de escada simplificada para garantir conectividade total
;  - BFS multi-andar robusto, com diagnostico de celulas inalcancaveis
;  - Logica de descida da escada corrigida
; ============================================================================

globals [
  N-ANDARES                 ;; 30
  GRID-W                    ;; 20 (largura de cada andar)
  GRID-H                    ;; 20 (profundidade)
  ANDAR-ALTURA              ;; quantas linhas no mundo cada andar ocupa (= GRID-H + 1)
  ESCADA-COL                ;; coluna local da escada
  ESCADA-LIN                ;; linha local da escada
  SAIDA-LIN                 ;; linha local da saida no terreo

  andar-foco                ;; andar onde o fogo comeca
  col-foco
  lin-foco

  total-inicial
  total-evacuados
  total-mortos
  total-feridos
  taxa-sobrevivencia
  saude-media-sobreviventes
  tempo-evacuacao
  fim?

  ;; diagnostico
  celulas-inalcancaveis
]

patches-own [
  andar                     ;; 0..29, ou -1 se for teto/separador
  col-local                 ;; 0..GRID-W-1
  lin-local                 ;; 0..GRID-H-1
  tipo                      ;; "vazio", "parede", "escada", "saida", "teto", "fogo-fonte"
  temperatura
  fumaca
  CO
  CO2
  distancia-saida
  custo-dinamico
]

breed [ocupantes ocupante]

ocupantes-own [
  perfil                    ;; "adulto", "idoso", "PcD"
  v0
  resistencia
  meu-andar
  fadiga
  saude
  FED-CO
  FED-CO2
  FED-heat
  FED-total
  velocidade-atual
  evacuado?
  morto?
  ferido?
  exposicao-acumulada
]

;; ============================================================================
;; SETUP
;; ============================================================================

to setup
  clear-all
  set-default-shape ocupantes "person"

  set N-ANDARES 30
  set GRID-W 20
  set GRID-H 20
  set ANDAR-ALTURA (GRID-H + 1)

  ;; escada no canto inferior-esquerdo do andar (col=1, lin=1) — adjacente
  ;; a duas paredes externas, mas ACESSIVEL pelos vizinhos col=2,lin=1 e col=1,lin=2
  set ESCADA-COL 1
  set ESCADA-LIN 1
  set SAIDA-LIN (GRID-H - 2)

  set andar-foco andar-incendio
  set col-foco coluna-incendio
  set lin-foco linha-incendio

  set fim? false

  construir-edificio
  posicionar-fogo
  criar-ocupantes
  calcular-campo-distancia
  diagnosticar-acessibilidade
  atualizar-custo-dinamico

  set total-inicial count ocupantes
  set total-evacuados 0
  set total-mortos 0
  set total-feridos 0
  set tempo-evacuacao 0

  reset-ticks
end

;; --- Construcao da geometria do edificio ----------------------------------

to construir-edificio
  ask patches [
    set andar -1
    set col-local -1
    set lin-local -1
    set tipo "teto"
    set temperatura 25
    set fumaca 0
    set CO 0
    set CO2 0
    set pcolor gray - 4
  ]

  let k 0
  while [k < N-ANDARES] [
    construir-andar k (k * ANDAR-ALTURA)
    set k k + 1
  ]
end

to construir-andar [k y-base]
  ;; preenche celulas uteis (20x20)
  let cx 0
  while [cx < GRID-W] [
    let cy 0
    while [cy < GRID-H] [
      ask patch cx (y-base + cy) [
        set andar k
        set col-local cx
        set lin-local cy
        set tipo "vazio"
        set pcolor white
      ]
      set cy cy + 1
    ]
    set cx cx + 1
  ]

  ;; paredes externas do andar (perimetro)
  ask patches with [andar = k and (
        col-local = 0 or col-local = GRID-W - 1 or
        lin-local = 0 or lin-local = GRID-H - 1)] [
    set tipo "parede"
    set pcolor gray - 2
  ]

  ;; divisoria interna vertical no meio do andar com porta larga
  let xmeio round (GRID-W / 2)
  let ymeio round (GRID-H / 2)
  ask patches with [andar = k and col-local = xmeio
                    and lin-local > 0 and lin-local < GRID-H - 1
                    and not (lin-local >= ymeio - 1 and lin-local <= ymeio + 1)] [
    set tipo "parede"
    set pcolor gray - 2
  ]

  ;; ESCADA: celula simples em (ESCADA-COL, ESCADA-LIN)
  ;; SEM caixa de paredes em volta — qualquer um pode entrar pelos vizinhos.
  ;; No andar 0, e o desembarque (vazio); nos demais, e "escada" (portal).
  ask patches with [andar = k and col-local = ESCADA-COL and lin-local = ESCADA-LIN] [
    ifelse k = 0 [
      set tipo "vazio"
      set pcolor white
    ] [
      set tipo "escada"
      set pcolor yellow - 1
    ]
  ]

  ;; SAIDA: somente no andar 0, na parede direita
  if k = 0 [
    ask patches with [andar = 0 and col-local = GRID-W - 1
                      and lin-local >= SAIDA-LIN - 1 and lin-local <= SAIDA-LIN + 1] [
      set tipo "saida"
      set pcolor green
    ]
  ]
end

to posicionar-fogo
  let py andar-foco * ANDAR-ALTURA + lin-foco
  let p patch col-foco py
  ;; se a posicao escolhida nao for valida, escolhe outra no mesmo andar
  if p = nobody or [andar] of p != andar-foco or [tipo] of p = "parede" or [tipo] of p = "escada" [
    let cand patches with [andar = andar-foco and tipo = "vazio"]
    if any? cand [ set p one-of cand ]
  ]
  if p != nobody [
    ask p [
      set tipo "fogo-fonte"
      set temperatura 600
      set fumaca 1
      set CO 1
      set CO2 1
      set pcolor red
    ]
  ]
end

;; --- Populacao heterogenea ------------------------------------------------

to criar-ocupantes
  let por-andar max list 1 round (numero-ocupantes / N-ANDARES)
  let k 0
  while [k < N-ANDARES] [
    let livres patches with [andar = k and tipo = "vazio"]
    let n min list por-andar count livres
    if n > 0 [
      ask n-of n livres [
        sprout-ocupantes 1 [
          definir-perfil
          set meu-andar k
          set fadiga 0
          set saude 1.0
          set FED-CO 0
          set FED-CO2 0
          set FED-heat 0
          set FED-total 0
          set velocidade-atual v0
          set evacuado? false
          set morto? false
          set ferido? false
          set exposicao-acumulada 0
          set size 0.9
        ]
      ]
    ]
    set k k + 1
  ]
end

to definir-perfil  ;; turtle procedure
  let r random-float 1
  ifelse r < percent-idosos / 100 [
    set perfil "idoso"
    set v0 0.60
    set resistencia 0.7 + random-float 0.3
    set color orange
  ] [
    ifelse r < (percent-idosos + percent-PcD) / 100 [
      set perfil "PcD"
      set v0 0.40
      set resistencia 0.7 + random-float 0.3
      set color violet
    ] [
      set perfil "adulto"
      set v0 1.0
      set resistencia 0.9 + random-float 0.4
      set color blue
    ]
  ]
end

;; --- Campo de distancia BFS ate a saida do terreo -------------------------
;; CORRECAO: O BFS agora alterna entre propagacao intra-andar (vizinhos 4 no
;; mesmo andar) e propagacao inter-andar pelas escadas, ate convergir.
;; A escada do andar k esta conectada a escada (ou desembarque) do andar k-1,
;; com custo extra "custo-lance" representando o tempo de descer um lance.

to calcular-campo-distancia
  ask patches [
    set distancia-saida 999999
    set custo-dinamico 1
  ]
  ask patches with [tipo = "saida"] [ set distancia-saida 0 ]

  let custo-lance 3   ;; descer um lance custa o equivalente a 3 celulas

  ;; Loop externo: ate nada mais mudar globalmente
  let mudou-global? true
  let iter-ext 0
  while [mudou-global? and iter-ext < 200] [
    set mudou-global? false
    set iter-ext iter-ext + 1

    ;; (1) Propaga distancias intra-andar ate CONVERGIR completamente
    let mudou-intra? true
    let iter-intra 0
    while [mudou-intra? and iter-intra < 2000] [
      set mudou-intra? false
      set iter-intra iter-intra + 1
      ask patches with [tipo != "parede" and tipo != "teto" and distancia-saida < 999999] [
        let d distancia-saida
        let k andar
        ask neighbors4 with [tipo != "parede" and tipo != "teto" and andar = k] [
          if distancia-saida > d + 1 [
            set distancia-saida d + 1
            set mudou-intra? true
          ]
        ]
      ]
    ]

    ;; (2) Propaga inter-andar pelas escadas (uma rodada)
    let k 0
    while [k < N-ANDARES - 1] [
      let p-baixo one-of patches with [andar = k and col-local = ESCADA-COL and lin-local = ESCADA-LIN]
      let p-cima  one-of patches with [andar = (k + 1) and col-local = ESCADA-COL and lin-local = ESCADA-LIN]
      if p-baixo != nobody and p-cima != nobody [
        let d-baixo [distancia-saida] of p-baixo
        if d-baixo < 999999 [
          ask p-cima [
            if distancia-saida > d-baixo + custo-lance [
              set distancia-saida d-baixo + custo-lance
              set mudou-global? true
            ]
          ]
        ]
      ]
      set k k + 1
    ]
  ]
end

to diagnosticar-acessibilidade
  let inacessiveis count patches with [
    tipo != "parede" and tipo != "teto" and distancia-saida >= 999999
  ]
  set celulas-inalcancaveis inacessiveis
  let uteis count patches with [tipo != "parede" and tipo != "teto"]
  print (word "BFS concluido. Celulas uteis: " uteis
              " | inalcancaveis: " inacessiveis)
  if inacessiveis > 0 [
    print "  ATENCAO: algumas celulas nao conectam a saida."
  ]
end

;; ============================================================================
;; LOOP PRINCIPAL
;; ============================================================================

to go
  if fim? [ stop ]
  if not any? ocupantes with [not evacuado? and not morto?] [
    finalizar
    stop
  ]
  if ticks >= max-ticks [
    finalizar
    stop
  ]

  propagar-fogo
  atualizar-custo-dinamico
  atualizar-ocupantes
  atualizar-visualizacao
  atualizar-metricas

  tick
end

;; ============================================================================
;; PROPAGACAO DO FOGO
;; Modelo expansivo (nao conservativo): cada celula "quente" contamina vizinhos
;; somando uma fracao. A fonte e mantida fixa, e o decaimento e baixo.
;; ============================================================================

to propagar-fogo
  ;; Reafirma as fontes
  ask patches with [tipo = "fogo-fonte"] [
    set temperatura 600
    set fumaca 1
    set CO 1
    set CO2 1
  ]

  ;; Espalhamento contagioso intra-andar
  espalhar "fumaca"      0.35
  espalhar "CO"          0.30
  espalhar "CO2"         0.30
  espalhar "temperatura" 0.25

  ;; Conveccao vertical: fumaca/calor sobem pelo poco da escada
  propagar-vertical

  ;; Decaimento leve (a fonte continua gerando, entao isso so suaviza)
  ask patches with [tipo != "fogo-fonte" and tipo != "parede" and tipo != "teto"] [
    set temperatura max list 25 (temperatura * 0.999 + 25 * 0.001)
    set fumaca max list 0 (fumaca - 0.0005)
    set CO max list 0 (CO - 0.0005)
    set CO2 max list 0 (CO2 - 0.0005)
  ]
end

;; Espalhamento contagioso: cada celula com valor > 0 transfere uma fracao
;; para os vizinhos do mesmo andar, SEM subtrair de si mesma (a fonte mantem
;; a alimentacao). Para temperatura, soma de forma a aproximar-se do valor
;; do vizinho mais quente.
to espalhar [grandeza taxa]
  let lista sort patches with [tipo != "parede" and tipo != "teto"
                                and ler self grandeza > 0.01]
  let pares map [p -> (list p (ler p grandeza))] lista
  foreach pares [ par ->
    let p item 0 par
    let v item 1 par
    let k [andar] of p
    let viz [neighbors4] of p
    set viz viz with [tipo != "parede" and tipo != "teto" and andar = k]
    if any? viz [
      ask viz [
        let v-meu ler self grandeza
        ifelse grandeza = "temperatura" [
          ;; temperatura: o vizinho frio se aquece em direcao ao quente
          let novo v-meu + taxa * (v - v-meu)
          if novo > v-meu [ escrever grandeza novo ]
        ] [
          ;; fumaca/CO/CO2: contagio aditivo, saturando em 1
          let ganho taxa * v * (1 - v-meu)
          escrever grandeza (min list 1 (v-meu + ganho))
        ]
      ]
    ]
  ]
end

;; Conveccao vertical: fumaca/calor sobem pelo poco da escada
to propagar-vertical
  let k 1
  while [k < N-ANDARES] [
    let p-aqui one-of patches with [andar = k and col-local = ESCADA-COL and lin-local = ESCADA-LIN]
    let p-baixo one-of patches with [andar = (k - 1) and col-local = ESCADA-COL and lin-local = ESCADA-LIN]
    if p-aqui != nobody and p-baixo != nobody [
      ask p-aqui [
        set fumaca min list 1 (fumaca + 0.30 * [fumaca] of p-baixo)
        set CO min list 1 (CO + 0.25 * [CO] of p-baixo)
        set CO2 min list 1 (CO2 + 0.25 * [CO2] of p-baixo)
        set temperatura max list temperatura (0.7 * temperatura + 0.3 * [temperatura] of p-baixo)
      ]
    ]
    set k k + 1
  ]
end

to-report ler [p grandeza]
  if grandeza = "temperatura" [ report [temperatura] of p ]
  if grandeza = "fumaca"      [ report [fumaca]      of p ]
  if grandeza = "CO"          [ report [CO]          of p ]
  if grandeza = "CO2"         [ report [CO2]         of p ]
  report 0
end

to escrever [grandeza valor]  ;; patch procedure
  if grandeza = "temperatura" [ set temperatura valor ]
  if grandeza = "fumaca"      [ set fumaca valor ]
  if grandeza = "CO"          [ set CO valor ]
  if grandeza = "CO2"         [ set CO2 valor ]
end

;; ============================================================================
;; CUSTO DINAMICO
;; ============================================================================

to atualizar-custo-dinamico
  ask patches with [tipo != "parede" and tipo != "teto"] [
    let pen-f peso-fumaca * fumaca
    let pen-c peso-calor * max list 0 ((temperatura - 40) / 100)
    let pen-g peso-congestao * count ocupantes-here
    set custo-dinamico distancia-saida + pen-f + pen-c + pen-g
  ]
end

;; ============================================================================
;; COMPORTAMENTO DOS AGENTES
;; ============================================================================

to atualizar-ocupantes
  ask ocupantes with [not evacuado? and not morto?] [
    decidir-e-mover
    atualizar-fisiologia
    checar-saida-ou-morte
  ]
end

to decidir-e-mover  ;; turtle procedure
  ;; v(t) = v0 * exp(-lambda * S(t)) * (1 - gamma * F(t))
  let S [fumaca] of patch-here
  let v v0 * exp (- lambda-fumaca * S) * (1 - gamma-fadiga * fadiga)
  if saude < 0.5 [ set v v * (saude / 0.5) ]
  if v < 0.05 [ set v 0.05 ]
  set velocidade-atual v

  if random-float 1 > v [ stop ]  ;; nao se move neste tick

  ;; Se estou numa escada, dou prioridade a descer um lance
  if [tipo] of patch-here = "escada" [
    descer-escada
    stop
  ]

  let aqui patch-here
  let k [andar] of aqui
  let d-aqui [distancia-saida] of aqui

  ;; Vizinhos navegaveis no mesmo andar. Para celulas de escada e saida,
  ;; ignoramos a restricao de ocupantes (alta capacidade).
  let candidatos neighbors with [
    tipo != "parede" and tipo != "teto"
    and andar = k
    and (tipo = "escada" or tipo = "saida" or not any? ocupantes-here)
    and distancia-saida < 999999
  ]
  if not any? candidatos [ stop ]

  ;; Estritamente mais perto da saida: priorizamos esses
  let mais-perto candidatos with [distancia-saida < d-aqui]

  ifelse any? mais-perto [
    ;; Entre os que avancam, escolhe o de menor custo-dinamico (evita fumaca)
    let melhor min-one-of mais-perto [custo-dinamico]
    move-to melhor
    if [tipo] of melhor = "escada" [
      ;; ao entrar numa escada, descer imediatamente no proximo tick
    ]
  ] [
    ;; Cercado por celulas iguais ou piores: tenta lateral para destravar
    let iguais candidatos with [distancia-saida = d-aqui]
    if any? iguais [
      let melhor min-one-of iguais [custo-dinamico]
      ;; pequena chance de mover lateralmente, para destravar congestao
      if random-float 1 < 0.3 [ move-to melhor ]
    ]
  ]

  set fadiga min list 1 (fadiga + 0.0006 / resistencia)
end

to descer-escada  ;; turtle procedure
  let andar-novo meu-andar - 1
  if andar-novo < 0 [ stop ]
  ;; A escada e tratada como capacidade alta (varios agentes em fila),
  ;; entao nao bloqueia se ja tiver outros agentes la
  let alvo one-of patches with [
    andar = andar-novo
    and col-local = ESCADA-COL and lin-local = ESCADA-LIN
  ]
  if alvo != nobody [
    move-to alvo
    set meu-andar andar-novo
  ]
end

;; --- Fisiologia: FED ------------------------------------------------------

to atualizar-fisiologia  ;; turtle procedure
  let cCO  [CO]          of patch-here
  let cCO2 [CO2]         of patch-here
  let T    [temperatura] of patch-here
  let S    [fumaca]      of patch-here

  let dCO    coef-CO    * cCO   / resistencia
  let dCO2   coef-CO2   * cCO2  / resistencia
  let dHeat  coef-calor * max list 0 ((T - 40) / 100) / resistencia

  set FED-CO   FED-CO   + dCO
  set FED-CO2  FED-CO2  + dCO2
  set FED-heat FED-heat + dHeat
  set FED-total FED-CO + FED-CO2 + FED-heat

  set saude max list 0 (1 - beta-saude * FED-total)
  set exposicao-acumulada exposicao-acumulada + S

  if saude < 0.5 and not ferido? [ set ferido? true ]
end

to checar-saida-ou-morte  ;; turtle procedure
  if FED-total >= 1 or saude <= 0 [
    set morto? true
    set color red
    set shape "x"
    stop
  ]
  if [tipo] of patch-here = "saida" [
    set evacuado? true
    hide-turtle
  ]
end

;; ============================================================================
;; VISUALIZACAO
;; ============================================================================

to atualizar-visualizacao
  ask patches with [tipo = "vazio" or tipo = "escada"] [
    let r 255 let g 255 let b 255
    let f fumaca
    set r r - 220 * f
    set g g - 220 * f
    set b b - 220 * f
    let t-norm max list 0 min list 1 ((temperatura - 25) / 400)
    set r min list 255 (r + 120 * t-norm)
    set g g - 120 * t-norm
    set b b - 120 * t-norm
    ifelse tipo = "escada" and f < 0.2 and temperatura < 50 [
      set pcolor yellow - 1
    ] [
      set pcolor (list (max list 0 r) (max list 0 g) (max list 0 b))
    ]
  ]
  ask ocupantes with [not evacuado? and not morto?] [
    ifelse saude > 0.7 [
      ifelse perfil = "adulto" [ set color blue ]
      [ ifelse perfil = "idoso" [ set color orange ] [ set color violet ] ]
    ] [
      ifelse saude > 0.4 [ set color brown ] [ set color red - 2 ]
    ]
  ]
end

;; ============================================================================
;; METRICAS
;; ============================================================================

to atualizar-metricas
  set total-evacuados count ocupantes with [evacuado?]
  set total-mortos    count ocupantes with [morto?]
  set total-feridos   count ocupantes with [ferido? and not morto? and not evacuado?]
  let vivos ocupantes with [not morto?]
  ifelse any? vivos [
    set saude-media-sobreviventes mean [saude] of vivos
  ] [ set saude-media-sobreviventes 0 ]
  ifelse total-inicial > 0 [
    set taxa-sobrevivencia 100 * (total-inicial - total-mortos) / total-inicial
  ] [ set taxa-sobrevivencia 0 ]
  set tempo-evacuacao ticks
end

to finalizar
  atualizar-metricas
  set fim? true
  print "============================================="
  print "SIMULACAO CONCLUIDA"
  print (word "TET: " tempo-evacuacao " ticks")
  print (word "Evacuados: " total-evacuados " / " total-inicial)
  print (word "Mortos: "    total-mortos)
  print (word "Feridos: "   total-feridos)
  print (word "Sobrev.: "   precision taxa-sobrevivencia 2 " %")
  print (word "Saude media: " precision saude-media-sobreviventes 3)
  print "============================================="
end

to-report ocupantes-no-andar [k]
  report count ocupantes with [meu-andar = k and not evacuado? and not morto?]
end
@#$#@#$#@
GRAPHICS-WINDOW
260
10
460
820
-1
-1
9.0
1
9
1
1
1
0
0
0
1
0
19
0
629
0
0
1
ticks
30.0

BUTTON
10
15
105
55
NIL
setup
NIL
1
T
OBSERVER
NIL
NIL
NIL
NIL
1

BUTTON
115
15
210
55
NIL
go
T
1
T
OBSERVER
NIL
NIL
NIL
NIL
1

BUTTON
10
60
210
93
go (1 passo)
go
NIL
1
T
OBSERVER
NIL
NIL
NIL
NIL
1

SLIDER
10
105
245
138
numero-ocupantes
numero-ocupantes
30
600
300.0
30
1
NIL
HORIZONTAL

SLIDER
10
142
245
175
percent-idosos
percent-idosos
0
60
15.0
5
1
%
HORIZONTAL

SLIDER
10
179
245
212
percent-PcD
percent-PcD
0
40
5.0
5
1
%
HORIZONTAL

TEXTBOX
10
220
245
240
Foco do incendio (parametrizavel):
11
0.0
1

SLIDER
10
240
245
273
andar-incendio
andar-incendio
0
29
5.0
1
1
NIL
HORIZONTAL

SLIDER
10
277
245
310
coluna-incendio
coluna-incendio
1
18
10.0
1
1
NIL
HORIZONTAL

SLIDER
10
314
245
347
linha-incendio
linha-incendio
1
18
10.0
1
1
NIL
HORIZONTAL

TEXTBOX
10
355
245
375
Parametros comportamentais:
11
0.0
1

SLIDER
10
375
245
408
lambda-fumaca
lambda-fumaca
0
3
1.5
0.1
1
NIL
HORIZONTAL

SLIDER
10
412
245
445
gamma-fadiga
gamma-fadiga
0
1
0.4
0.05
1
NIL
HORIZONTAL

TEXTBOX
10
452
245
472
Pesos do custo de navegacao:
11
0.0
1

SLIDER
10
472
245
505
peso-fumaca
peso-fumaca
0
50
20.0
1
1
NIL
HORIZONTAL

SLIDER
10
509
245
542
peso-calor
peso-calor
0
50
15.0
1
1
NIL
HORIZONTAL

SLIDER
10
546
245
579
peso-congestao
peso-congestao
0
20
3.0
0.5
1
NIL
HORIZONTAL

TEXTBOX
10
589
245
609
Coeficientes FED (toxicidade):
11
0.0
1

SLIDER
10
609
245
642
coef-CO
coef-CO
0
0.01
0.003
0.0005
1
NIL
HORIZONTAL

SLIDER
10
646
245
679
coef-CO2
coef-CO2
0
0.01
0.002
0.0005
1
NIL
HORIZONTAL

SLIDER
10
683
245
716
coef-calor
coef-calor
0
0.01
0.004
0.0005
1
NIL
HORIZONTAL

SLIDER
10
720
245
753
beta-saude
beta-saude
0
2
1.0
0.05
1
NIL
HORIZONTAL

SLIDER
10
763
245
796
max-ticks
max-ticks
500
20000
8000.0
500
1
NIL
HORIZONTAL

MONITOR
470
15
630
60
TET (ticks)
tempo-evacuacao
0
1
11

MONITOR
470
65
630
110
Evacuados
total-evacuados
0
1
11

MONITOR
470
115
630
160
Mortos
total-mortos
0
1
11

MONITOR
470
165
630
210
Feridos
total-feridos
0
1
11

MONITOR
470
215
630
260
Sobrev. (%)
taxa-sobrevivencia
1
1
11

MONITOR
470
265
630
310
Saude media
saude-media-sobreviventes
3
1
11

MONITOR
470
315
630
360
Adultos vivos
count ocupantes with [perfil = \"adulto\" and not evacuado? and not morto?]
0
1
11

MONITOR
470
365
630
410
Idosos vivos
count ocupantes with [perfil = \"idoso\" and not evacuado? and not morto?]
0
1
11

MONITOR
470
415
630
460
PcD vivos
count ocupantes with [perfil = \"PcD\" and not evacuado? and not morto?]
0
1
11

MONITOR
470
465
630
510
Inalcancaveis
celulas-inalcancaveis
0
1
11

PLOT
650
15
1120
220
Evacuacao x Tempo
ticks
n
0.0
10.0
0.0
10.0
true
true
"" ""
PENS
"Evacuados" 1.0 0 -13840069 true "" "plot total-evacuados"
"Mortos" 1.0 0 -2674135 true "" "plot total-mortos"
"Ativos" 1.0 0 -13345367 true "" "plot count ocupantes with [not evacuado? and not morto?]"

PLOT
650
230
1120
425
Saude media dos vivos
ticks
H
0.0
10.0
0.0
1.0
true
false
"" ""
PENS
"H" 1.0 0 -16777216 true "" "if any? ocupantes with [not morto?] [ plot mean [saude] of ocupantes with [not morto?] ]"

PLOT
650
435
1120
630
Fumaca e Temp. medias
ticks
nivel
0.0
10.0
0.0
1.0
true
true
"" ""
PENS
"fumaca" 1.0 0 -7500403 true "" "plot mean [fumaca] of patches with [tipo != \"parede\" and tipo != \"teto\"]"
"temp norm." 1.0 0 -2674135 true "" "plot (mean [temperatura] of patches with [tipo != \"parede\" and tipo != \"teto\"]) / 600"

PLOT
650
640
1120
820
Evacuados por perfil
ticks
n
0.0
10.0
0.0
10.0
true
true
"" ""
PENS
"Adulto" 1.0 0 -13345367 true "" "plot count ocupantes with [perfil = \"adulto\" and evacuado?]"
"Idoso" 1.0 0 -955883 true "" "plot count ocupantes with [perfil = \"idoso\" and evacuado?]"
"PcD" 1.0 0 -8630108 true "" "plot count ocupantes with [perfil = \"PcD\" and evacuado?]"

TEXTBOX
470
520
630
820
Legenda:\n- Azul: adulto saudavel\n- Laranja: idoso\n- Roxo: PcD\n- Marrom: ferido\n- X vermelho: vitima\n- Amarelo: escada\n- Verde: saida (terreo)\n- Cinza-escuro: parede\n- Cinza-claro: fumaca\n- Tons quentes: calor\n\nAndar 0 = terreo (em baixo).\nAndar 29 = topo (em cima).\n\nVer a saida do Command\nCenter para diagnostico\ndo BFS no setup.
9
0.0
1

@#$#@#$#@
## Resumo

Modelo NetLogo de evacuacao em edificio alto durante incendio, 30 andares (120 m), grade 20x20 por andar, conforme a especificacao ABNT NBR 9077. Elevadores bloqueados; evacuacao apenas pelas escadas.

## Correcoes desta versao

1. Mundo NAO toroidal (wrap horizontal/vertical desligados na interface), evitando teleporte de agentes do terreo para o topo do edificio.
2. Geometria de escada simplificada: a celula de escada e acessivel pelos vizinhos do mesmo andar, sem caixa de paredes que isolava o portal.
3. BFS multi-andar reescrito: alterna propagacao intra-andar e propagacao vertical pelas escadas ate convergir; inclui diagnostico de celulas inalcancaveis no setup.
4. Logica do agente: se estiver numa escada, sempre tenta descer um lance; caso contrario escolhe vizinho de menor custo-dinamico.

## Como ler

A View mostra o edificio em corte: andar 0 (terreo) embaixo com a saida verde; andar 29 no topo. As celulas amarelas no canto esquerdo de cada andar (col=1, lin=1) sao as escadas — formam uma coluna vertical pela qual os agentes descem. A fumaca tambem sobe por essa coluna. O monitor "Inalcancaveis" deve mostrar 0 ou um numero pequeno — se for grande, alguma parte do edificio ficou isolada da saida.

## Formalismo

v(t) = v0 * exp(-lambda * S(t)) * (1 - gamma * F(t))
v0_adulto = 1.0   v0_idoso = 0.60   v0_PcD = 0.40

FED(t) = FED_CO + FED_CO2 + FED_heat
H(t)   = 1 - beta * FED(t)
@#$#@#$#@
default
true
0
Polygon -7500403 true true 150 5 40 250 150 205 260 250

person
false
0
Circle -7500403 true true 110 5 80
Polygon -7500403 true true 105 90 120 195 90 285 105 300 135 300 150 225 165 300 195 300 210 285 180 195 195 90
Rectangle -7500403 true true 127 79 172 94
Polygon -7500403 true true 195 90 240 150 225 180 165 105
Polygon -7500403 true true 105 90 60 150 75 180 135 105

x
false
0
Polygon -7500403 true true 270 75 225 30 30 225 75 270
Polygon -7500403 true true 30 75 75 30 270 225 225 270

@#$#@#$#@
NetLogo 6.4.0
@#$#@#$#@
@#$#@#$#@
@#$#@#$#@
@#$#@#$#@
@#$#@#$#@
default
0.0
-0.2 0 0.0 1.0
0.0 1 1.0 0.0
0.2 0 0.0 1.0
link direction
true
0
Line -7500403 true 150 150 90 180
Line -7500403 true 150 150 210 180

@#$#@#$#@
0
@#$#@#$#@
