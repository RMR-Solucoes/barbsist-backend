# Mercado Pago — Fundação de Cobrança Geral

Este patch generaliza `MercadoPagoCobranca` para que uma única integração Mercado Pago da barbearia possa atender, por etapas:

- `PLANO_CLIENTE` — ativo nesta etapa;
- `COMANDA` — reservado para a próxima integração;
- `VENDA` — reservado para o futuro módulo de Venda/PDV.

## Novas rotas genéricas

- `POST /mercado-pago/cobrancas/pix`
- `POST /mercado-pago/cobrancas/cartao`

As rotas antigas de assinatura continuam disponíveis por compatibilidade.

Nesta etapa, as novas rotas aceitam `origem_negocio=PLANO_CLIENTE`. Se `COMANDA` ou `VENDA` forem usados antes das etapas correspondentes, o backend retorna HTTP 501 propositalmente, sem criar movimentação financeira.

## Banco

Execute somente após backup:

```powershell
python .\migrar_mercado_pago_cobranca_geral.py
```

A migração preserva as cobranças já existentes e as marca como `PLANO_CLIENTE`.
