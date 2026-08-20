# BarbSist — pacote ajustado após auditoria (19/08/2026)

Este pacote contém o código-fonte ajustado do backend. Por segurança, o ZIP final não inclui `.env`, bancos `.db`, `venv`, caches ou `.git`.

## Antes de substituir arquivos

1. Faça backup da pasta atual.
2. Preserve o seu `.env` e o banco local, caso use SQLite.
3. Não copie um banco antigo por cima do banco atual.
4. Instale/atualize as dependências do `requirements.txt` no seu ambiente virtual.

## Variáveis novas para Mercado Pago

- `PUBLIC_BACKEND_URL`: URL pública HTTPS do backend.
- `MP_CREDENTIALS_KEY`: chave Fernet para criptografar credenciais de cada barbearia.

Gere a chave uma única vez com:

```powershell
python .\gerar_chave_mp.py
```

Depois configure a mesma chave no Railway. Não a altere depois de gravar credenciais Mercado Pago no sistema.

## Configuração Mercado Pago por barbearia

Acesse a nova tela **Mercado Pago** no frontend e informe, para cada barbearia:

- Access Token;
- Webhook Secret;
- Public Key (opcional para o PIX atual, mas armazenada para evolução);
- ambiente;
- integração ativa.

A integração só pode ser ativada quando Access Token e Webhook Secret estiverem cadastrados.

O Webhook mostrado na tela terá o formato:

`https://SEU-BACKEND/mercado-pago/webhook/{barbearia_id}`

## Ajustes implementados neste pacote

- seleção de serviços no cadastro/edição de Plano;
- nova assinatura começa pendente e sem usos liberados;
- confirmação de pagamento centralizada;
- bloqueio lógico de pagamento duplicado por referência mensal;
- confirmação manual de PIX;
- geração de PIX Mercado Pago por assinatura;
- credenciais Mercado Pago criptografadas e isoladas por barbearia;
- Webhook Mercado Pago com validação `x-signature` e consulta do pagamento antes de liberar plano;
- idempotência de cobrança/pagamento;
- pagamento aprovado gera `PagamentoPlano`, entrada no Caixa e libera usos;
- correção dos status de Assinaturas no frontend;
- validação multi-barbearia de Estilos no agendamento;
- validação de serviço pertencente ao Plano no agendamento;
- bloqueio de segunda conversão de agendamento em Comanda;
- remoção de item de Comanda aberta com reversão de estoque/uso de plano;
- cancelamento de Comanda aberta com reversões;
- remoção da inclusão duplicada do router de autenticação;
- tela administrativa Mercado Pago e histórico de cobranças.

## Ainda não implementado neste pacote

Este pacote NÃO deve ser interpretado como conclusão das demais pendências da auditoria. Continuam para etapas posteriores: Dashboard Financeiro, Fluxo de Caixa, DRE, Venda Rápida/PDV, Fidelidade, código de barras, upload de imagens, auditoria geral, estornos completos de Caixa/Contas, frontend administrativo de Usuários/Estilos, migração para Decimal/Alembic, testes automatizados e otimizações de performance.

## Validação feita antes da geração do ZIP

- `python -m compileall -q .` no backend: aprovado (somente warnings históricos em scripts antigos de migração).
- criação do schema SQLAlchemy em SQLite temporário: aprovada, incluindo as novas tabelas Mercado Pago.
- o build completo do Next.js não foi executado neste ambiente; execute `npm run build` localmente antes do deploy.
