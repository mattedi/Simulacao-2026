# Plano de Arquitetura Técnica e Estrutura de Fluxo do Programa

## 1. Arquitetura Sequencial do Loop Principal
O loop principal de simulação mantém uma cronologia causal de sub-rotinas rígidas por ciclo temporal (*tick*). E de atualiza de forma síncrona o controle adaptativo dos brigadistas e a atualização dos sensores de deadlock.
