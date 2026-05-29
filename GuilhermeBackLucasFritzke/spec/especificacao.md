# Especificação do Sistema Desejado: Entidades, Parâmetros e Atributos

## 1. Ontologia do Modelo (Entidades do Ecossistema)

### 1.1 Agentes Móveis (Turtles)

* **Ocupantes (Civis):**
  * Atributos Fisiológicos e Perfis: `meu-andar`, `tipo-agente` (adulto, idoso, pcd), `vel-max` (1.0, 0.6, 0.4 m/s), `vel-atual`, `t-reacao` (distribuição lognormal escalonada), `estado` (ativo, evacuado, ferido, morto), `fed-valor`.
  * Atributos Cognitivos e de Navegação: `perfil-conhec` (1 a 5), `alvo-x`, `alvo-y`, `alvo-andar`, `memoria-ticks`, `nivel-panico`.
  * **Atributos de Fluidez v2 (Novos):** * `ticks-parado`: Contador cumulativo de ciclos em que o agente não alterou sua coordenada geográfica.
    * `ultimo-x`, `ultimo-y`: Registradores da posição espacial no tick imediatamente anterior para detecção de deadlocks.

* **Brigadistas:**
  * Atributos: `meu-andar`, `vel-max` (1.5 m/s), `andar-base`, `orientados`.
  * **Evolução de Estado v2 (Novo):** `estado-brig` (categórico: "orientando", "evacuando", "evacuado", "morto"). O brigadista agora possui inteligência de evacuação e escapa do edifício quando o seu andar de origem estiver totalmente limpo de civis ativos.

### 1.2 Ambiente Estático e Dinâmico (Patches)
Cada célula armazena arrays indexados de dimensão igual ao número de andares (30):
* `tipo-celula-l` (0: Sala, 1: Corredor, 2: Escada, 3: Saída, 4: Parede)
* `fogo-l` (Booleano/Binário: presença de chamas)
* `fumaca-l` (Concentração de fumaça $\Phi$)
* `temperatura-l` (Em °C)
* `visibilidade-l` (Em metros, derivada por extinção luminosa)
* `acum-densidade-l` (Contador histórico de pisoteio/passagem)

## 2. Parâmetros Globais de Calibração (Globals)
* `alpha-dens`: Coeficiente de redução cinemática por densidade local = **0.12** (Calibrado na v2 para evitar parada total em clusters).
* `rho-bloq`: Densidade limite para congestionamento em corredores = **8.0** pessoas/patch.
* `cap-escada`: Capacidade de vazão máxima do patch de escada por andar = **15** agentes (Expandido na v2 para simular escoamento de prédios altos).
* `vis-min-trans`: Visibilidade mínima de tráfego nominal = **1.5m** (Reduzido na v2 para evitar agentes travados por opacidade leve).
* `deadlock-limite`: Tolerância máxima de imobilidade espacial = **8** ticks.
* `raio-evacuacao`: Raio de atração física final das portas externas do térreo = **2** patches.
