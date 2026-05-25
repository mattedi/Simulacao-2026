# Clarificação de Ambiguidades e Resoluções Algorítmicas
# Status: Homologado com Ajustes Físicos (v2) | Referência: Especificacao.md

## 1. Resolução de Regras e Lógica de Fluxo

### Q1: Como a velocidade atual lida com aglomerações e ambientes tóxicos?
**Resolução (Revisada):** Para evitar o erro de congelamento matemático em clusters densos, o coeficiente de Weidmann foi suavizado para `alpha-dens = 0.12`. Além disso, foi estabelecido um **piso de velocidade incondicional de 0.25 m/s**. Mesmo em pânico máximo ou visibilidade nula, o agente nunca para completamente por razões ambientais, mantendo uma marcha de sobrevivência tátil.

### Q2: Como funciona o sistema de Waypoints para salas internas isoladas?
**Resolução (Geométrica):** Agentes localizados em salas fechadas nos quadrantes distantes (Salas de canto SW, NW, SE, NE, N, S) sofrem de oclusão visual da rota de fuga principal. Eles são obrigados a mirar primeiro em um **Waypoint de Porta** específico da sua sub-sala (ex: coordenadas 5,5 para o canto SW). Somente após cruzar este waypoint espacial eles recalculam sua rota em direção ao destino final (escada/saída). Isso resolve de forma determinística os agentes presos atrás de paredes internas.

### Q3: Qual é o protocolo de desempate e resolução de Deadlocks ?
**Resolução (Dinâmica):** Se o agente permanecer na mesma coordenada espacial (`ultimo-x`, `ultimo-y`) por ciclos sucessivos:
1. Ao atingir `ticks-parado > deadlock-limite (8 ticks)`, seu nível de pânico aumenta por frustração e ele força um replanejamento imediato de alvo. Na escolha do patch vizinho, adiciona-se um ruído aleatório (ruído de penalidade flutuante de até 5 unidades) para quebrar escolhas puramente simétricas.
2. Se a imobilidade persistir e atingir um limiar severo (`4 * deadlock-limite = 32 ticks`), assume-se um travamento de malha estrutural. O agente realiza um salto físico emergencial (`teleporte`) de 1 patch para qualquer vizinho livre e não inflamado.

### Q4: Como o fluxo das escadas lida com a verticalidade no plano 2D?
**Resolução:** Quando um agente está posicionado em um patch do tipo escada (`tipo-celula-l = 2`), ele tenta executar uma descida em cascata de até **3 andares dentro do mesmo tick**. A movimentação vertical só é interrompida antes se o andar inferior estiver em chamas, com fumaça asfixiante extrema ($\Phi > 4.0$) ou se a contagem de corpos na escada abaixo atingir o teto de `cap-escada (15)`.

### Q5: Como funciona a atração das saídas do térreo (Fila de Evacuação)?
**Resolução:** Para evitar gargalos artificiais onde o agente fica travado adjacente à saída sem conseguir computar o patch exato da porta, define-se um `raio-evacuacao = 2`. Qualquer agente ativo que entrar neste raio de adjacência da saída externa no andar 0 é imediatamente puxado para a zona segura e seu estado é alterado para "Evacuado".
