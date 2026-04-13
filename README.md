# Simulação-2026
## Trabalho Final — Eletiva IV - Simulação
### Curso de Ciência da Computação — FURB (2026)

## Descrição
Este repositório contém a implementação do trabalho final da disciplina **Eletiva IV - Simulação**, do **Curso de Ciência da Computação**, voltado à **simulação de evacuação de um edifício de 30 andares em situação de incêndio**. O problema envolve a modelagem de ocupantes, brigadistas, fogo, fumaça, escadas e restrições de deslocamento em contexto de emergência. :contentReference.

O projeto foi organizado segundo o **ciclo básico da simulação** trabalhado na disciplina:
**Sistema de Referência (S) → Modelo (M) → Formalismo (F) → Computador (C) → Execução (E) → Observação (O)**. :contentReference[oaicite:2]{index=2}

---

## Objetivo do trabalho
Construir um modelo computacional capaz de simular a evacuação emergencial de um edifício em chamas, permitindo identificar:
- gargalos de evacuação;
- efeitos da propagação do fogo e da fumaça;
- impacto de perfis distintos de ocupantes;
- influência de parâmetros críticos sobre taxa de evacuação, tempo de saída e número de vítimas. :contentReference[oaicite:3]{index=3}

---

## Sistema de Referência (S)
O sistema de referência adotado é um **edifício realista de 30 andares**, com foco em incêndio e evacuação vertical. O domínio inclui:
- 30 andares, com térreo = 0;
- dimensão mínima de **20 × 20 células por andar**;
- escadas de emergência com capacidade limitada;
- elevadores bloqueados durante o incêndio;
- ao menos uma saída sinalizada por andar, com evacuação concluída no térreo;
- perfis de ocupantes: **adulto padrão**, **idoso** e **PcD**;
- foco do incêndio parametrizável por andar e célula;
- materiais inflamáveis e não inflamáveis no ambiente. :contentReference[oaicite:4]{index=4}

---

## Modelo Conceitual (M)
O modelo conceitual abstrai o sistema de referência e deve ser descrito segundo o **Protocolo ODD (Overview, Design Concepts, Details)**. O modelo contempla:
- entidades: ocupantes, bombeiros/brigadistas, fogo, fumaça, escadas;
- atributos: posição, velocidade, pânico, estado, raio de influência etc.;
- regras de interação e deslocamento;
- restrições espaciais e operacionais;
- simplificações explicitamente justificadas. :contentReference[oaicite:5]{index=5}

### Elementos centrais do modelo
- **Emergência**: congestionamentos, bloqueios e rotas subótimas;
- **Adaptação**: reação dos agentes à mudança do ambiente;
- **Objetivos**: evacuar ou orientar evacuação;
- **Interação**: entre ocupantes, brigadistas e ambiente;
- **Estocasticidade**: seeds aleatórios para inicialização e dinâmica;
- **Observação**: coleta contínua de métricas ao longo da simulação. :contentReference[oaicite:6]{index=6}

---

## Formalismo (F)
O formalismo define como o modelo será especificado de maneira executável. O enunciado recomenda:
- **propagação do fogo** por regras locais de célula;
- **movimentação dos agentes** por sistema reativo ou heurísticas locais;
- **nível de pânico** como variável contínua entre 0 e 1;
- **fluxo nas escadas** com capacidade máxima por step;
- **ciclo de vida do agente** por máquina de estados finitos. :contentReference[oaicite:7]{index=7}

---

## Computador / Implementação (C)
A implementação pode ser realizada em uma das ferramentas indicadas:
- **NetLogo**
- **Python Mesa**
- **Gama Platform** :contentReference[oaicite:8]{index=8}

### Parâmetros configuráveis mínimos
- número de ocupantes;
- andar do foco do incêndio;
- célula de origem do fogo;
- taxa de propagação do fogo;
- número de brigadistas;
- seed aleatório;
- capacidade máxima de fluxo por escada/step;
- raio de visibilidade na fumaça. :contentReference[oaicite:9]{index=9}

### Requisitos funcionais principais
O sistema deve incluir:
- edifício com 30 andares representado em grade 2D;
- corredores, salas, escadas, elevadores bloqueados e saídas;
- foco inicial de incêndio parametrizável;
- propagação do fogo;
- geração de fumaça;
- gargalos de escada;
- agentes ocupantes com atributos e perfis distintos;
- agentes bombeiros/brigadistas com função de orientação;
- células em chamas como áreas intransponíveis. :contentReference[oaicite:10]{index=10}

### Requisitos não funcionais
- reprodutibilidade por seed configurável;
- parâmetros ajustáveis por interface ou arquivo de configuração;
- suporte a pelo menos **500 agentes simultâneos**;
- mínimo de **30 rodadas independentes**;
- código versionado em repositório Git com README de execução. :contentReference[oaicite:11]{index=11}

---

## Execução (E)
A execução do experimento deve obedecer aos seguintes critérios:
- realizar ao menos **30 rodadas** por configuração experimental;
- registrar métricas a cada step/tick;
- realizar **análise de sensibilidade** variando ao menos 2 parâmetros;
- exportar dados brutos em **CSV**;
- registrar a seed de cada rodada. :contentReference[oaicite:12]{index=12}

---

## Observação (O)
A etapa de observação deve produzir métricas e retroalimentação sobre o modelo. As métricas obrigatórias são:
- **taxa de evacuação**;
- **tempo médio de evacuação**;
- **número de vítimas**;
- **mapa de calor** da densidade de ocupantes;
- **gargalos** de circulação;
- **evolução temporal** de evacuados, mortos e área em chamas. :contentReference[oaicite:13]{index=13}

A análise também deve discutir:
- plausibilidade do comportamento emergente;
- parâmetros mais impactantes;
- refinamentos necessários no modelo ou formalismo;
- consistência do ciclo **S↔M↔F↔C↔E→O→S**. :contentReference[oaicite:14]{index=14}
