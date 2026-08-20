# BarbSist — Patch Mercado Pago OAuth por barbearia

Este patch deve ser aplicado **depois** do patch PIX + cartão parcelado.

## Objetivo

Permitir que o administrador/gerente da barbearia clique em **Conectar Mercado Pago**, faça login na própria conta Mercado Pago e autorize o BarbSist, sem copiar Access Token, Public Key ou Refresh Token.

## Novas rotas

- `GET /mercado-pago/status`
- `GET /mercado-pago/oauth/conectar`
- `GET /mercado-pago/oauth/callback`
- `POST /mercado-pago/oauth/desconectar`

As rotas de PIX e cartão existentes passam a usar o Access Token da barbearia e renová-lo automaticamente quando necessário.

## Variáveis de ambiente

Veja `.env.mercado_pago_oauth.example`.

As credenciais `MP_CLIENT_ID` e `MP_CLIENT_SECRET` pertencem à aplicação BarbSist no Mercado Pago. O barbeiro não deve digitá-las.

O `MP_OAUTH_REDIRECT_URI` deve ser estático e idêntico ao cadastrado na aplicação Mercado Pago.

## Banco

Faça backup e execute:

`python .\\migrar_mercado_pago_oauth.py`

A migração adiciona os campos OAuth à configuração Mercado Pago e cria a tabela temporária de estados OAuth.

## Segurança

- Access Token e Refresh Token são criptografados com `MP_CREDENTIALS_KEY`.
- O parâmetro OAuth `state` é aleatório, salvo apenas como hash, expira em 10 minutos e só pode ser usado uma vez.
- PKCE está suportado opcionalmente por `MP_OAUTH_USE_PKCE=true`. Ative-o somente se PKCE também estiver habilitado na aplicação Mercado Pago.
- `MP_WEBHOOK_SECRET` pode ficar como segredo global da aplicação BarbSist; o dono da barbearia não precisa informá-lo.

## Observação sobre desconexão

A rota de desconexão remove localmente as credenciais da barbearia no BarbSist. Caso o vendedor queira revogar formalmente a autorização no Mercado Pago, a revogação também deve ser realizada na conta Mercado Pago.
