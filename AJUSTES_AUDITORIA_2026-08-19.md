# BarbSist — Ajustes consolidados 19/08/2026

Incluído neste pacote:
- correção da duplicidade do router de autenticação;
- Planos com serviços vinculados expostos ao frontend;
- nova assinatura inicia PENDENTE_PAGAMENTO e com 0 usos;
- pagamento confirmado é a única origem de PAGO/usos;
- proteção contra pagamento duplicado por assinatura + referência mensal;
- confirmação manual PIX;
- integração Mercado Pago PIX por barbearia, com credenciais criptografadas, X-Idempotency-Key, Webhook validado por x-signature e processamento idempotente;
- isolamento multi-barbearia na validação de Estilos;
- validação de serviço incluído no plano já no agendamento;
- bloqueio de nova conversão de agendamento em atendimento;
- remoção de item de comanda aberta com reversão de estoque/uso de plano;
- cancelamento de comanda aberta com reversões;
- correção dos status ATIVO/SUSPENSO/ENCERRADO no resumo de Assinaturas;
- tela de configuração Mercado Pago e geração de PIX na tela de Assinaturas.

## Variáveis novas
- `MP_CREDENTIALS_KEY`: gere com `python gerar_chave_mp.py` e mantenha fixa.
- `PUBLIC_BACKEND_URL`: URL pública do backend Railway, sem barra final.

## Importante
Este pacote consolida as correções críticas da auditoria e a Etapa 1 de Mercado Pago. Dashboard Financeiro, DRE, Fluxo de Caixa, Fidelidade, Venda Rápida/PDV, código de barras, upload de imagens e Auditoria Geral continuam como módulos futuros e não foram simulados como prontos.
