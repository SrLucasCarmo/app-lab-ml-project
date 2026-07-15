# PROJETO IA - CASE IEEE-CIS Fraud Detection (Vesta) 

# 🛡️ Estratégia de Monitoramento e Automação Antifraude

Este repositório contém o plano estratégico para o monitoramento de dados, avaliação de modelo em produção e as ações automatizadas para prevenção de fraudes e mitigação de *chargebacks*.

## ⚙️ Automação e Tomada de Decisão (Inferência em Tempo Real)

A inferência do modelo é realizada no momento exato de cada transação. Para garantir segurança sem comprometer a experiência do utilizador, utilizamos **faixas de probabilidade (score)** para acionar diferentes ações automatizadas:

* 🟢 **Baixo Risco (Score Baixo):** A transação é liberada automaticamente, garantindo uma experiência sem atrito para o cliente.
* 🟡 **Médio Risco (Score Médio):** A automação exige uma etapa de verificação adicional, solicitando uma **Validação em Dois Fatores (2FA)**.
* 🔴 **Alto Risco (Score Alto):** A transação é bloqueada preventivamente para evitar possíveis fraudes.

## 📊 Monitoramento em Produção

O monitoramento contínuo é essencial para identificar desvios e garantir a consistência do sistema. O nosso processo baseia-se em:

* **Validação Real vs. Previsto:** Compara-se constantemente os casos de *chargebacks* reais recebidos com as previsões geradas pelo modelo.
* **Mitigação de Falhas e Perda de Performance:** Para garantir resiliência e respostas rápidas a anomalias, mantemos **modelos alternativos prontos para produção**. Caso o modelo principal apresente queda de desempenho, a substituição é imediata.
* **Mudanças de Comportamento (Data Drift):** Alterações significativas nos padrões de consumo ou comportamento dos dados exigirão uma **remodelação e novo treinamento** do modelo de machine learning.

## 🎯 Métricas de Sucesso

A eficácia do projeto é avaliada pelo equilíbrio entre proteção financeira e satisfação do cliente. Os principais indicadores de sucesso (KPIs) são:

1.  **Taxa de Fraude:** Redução do volume e do valor financeiro das transações fraudulentas aprovadas.
2.  **Reclamações por Bloqueio (Falsos Positivos):** Controle sobre a quantidade de clientes legítimos afetados por bloqueios indevidos, otimizando continuamente a sensibilidade do modelo.