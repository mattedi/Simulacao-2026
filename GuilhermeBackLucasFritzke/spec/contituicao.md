# Constituição do Modelo: Restrições Globais e Invariantes Narrativas

## 1. Escopo Jurídico e Limites do Sistema
Este documento dita as regras de contorno absolutas da simulação. Nenhuma alteração nas fases posteriores ou no código computacional pode violar estas cláusulas.

### Cláusulas de Arquitetura (Invariantes Modificadas)
* **C1 (Paradigma):** O simulador adotará estritamente a modelagem baseada em agentes (ABM), regido pela tupla matemática de oito dimensões: $S = \langle A, E, R, F, T, I, D, O \rangle$.
* **C2 (Geometria Espacial):** O ambiente é um edifício de 30 andares. Cada pavimento é um grid 2D discreto de $20 \times 20$ células (`patches`), utilizando conectividade de Moore (8 direções).
* **C3 (Sincronismo e Movimento Determinístico):** O avanço temporal é discreto ($\Delta t = 1s$). O movimento dos agentes a cada *tick* passa a ser **determinístico-cinemático** (passos baseados na velocidade atual efetiva) com agendamento assíncrono via permutação aleatória (`ask shuffle turtles`), eliminando comportamentos probabilísticos de travamento de fluxo de versões anteriores.
* **C4 (Restrição Legal de Escoamento - NBR 9077):** Os elevadores permanecem permanentemente indisponíveis para fuga. O escoamento vertical é realizado exclusivamente pelas células categorizadas como escadas.
* **C5 (Heterogeneidade Populacional):** A população de civis é dividida em proporções fixas de comportamento cinemático: Adultos (70%), Idosos (20%) e Pessoas com Deficiência - PcD (10%), com velocidades máximas livres distintas.

### Invariantes de Fluidez da Versão II (Novas Salvaguardas)
* **C6 (Escoamento Vertical Eficiente):** A descida de escadas deve ocorrer em **cascata contínua** de até 3 andares no mesmo *tick*, simulando a gravidade e a continuidade do fluxo vertical, contanto que haja capacidade física disponível no lance inferior.
* **C7 (Anti-Deadlock Estrutural):** O modelo é obrigado a possuir um mecanismo de escape cognitivo e físico para evitar o congelamento eterno de agentes em cantos de salas, bifurcações congestionadas ou labirintos espaciais do edifício.
* **C8 (Garantia Mínima de Marcha):** Sob nenhuma circunstância ambiental de fumaça ou pânico a velocidade de um agente ativo cairá a zero, garantindo que o escoamento lento continue mesmo em condições extremas de visibilidade degradada.
