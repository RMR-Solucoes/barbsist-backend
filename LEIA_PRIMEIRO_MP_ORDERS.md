# Mercado Pago — migração para Orders API

Este patch adapta a cobrança da barbearia ao **Checkout Transparente via Orders API** sem remover a estrutura já homologada de OAuth e multi-barbearia.

## Alterações principais

- adiciona `order_id` a `MercadoPagoCobranca`;
- preserva `payment_id` para rastrear a transação de pagamento contida na Order;
- PIX e cartão passam a criar `POST /v1/orders`;
- adiciona `POST /mercado-pago/webhook` como Webhook global da aplicação;
- mantém temporariamente `POST /mercado-pago/webhook/{barbearia_id}` para compatibilidade;
- o Webhook global identifica a barbearia por `user_id` do evento OAuth/Order ou pela cobrança local;
- somente `PLANO_CLIENTE` continua ativo nesta etapa; `COMANDA` e `VENDA` permanecem bloqueadas com HTTP 501 até suas etapas específicas.

## Depois de aplicar

1. Faça backup de `barbearia.db`.
2. Execute `python .\\migrar_mercado_pago_orders.py`.
3. Compile/import `main`.
4. Confira no OpenAPI a rota `POST /mercado-pago/webhook`.
5. No Mercado Pago, configure o evento **Order (Mercado Pago)** apontando para `https://SEU_BACKEND/mercado-pago/webhook`.
6. Salve a chave secreta gerada como `MP_WEBHOOK_SECRET` no backend.

Não remova os backups nem publique a cópia local antes da homologação Sandbox.
