# PATCH FUNDAÇÃO SUPERADMIN + ASSINATURAS SAAS + MERCADO PAGO

## Objetivo
Separar definitivamente:
- `superadmin`: controle global do BarbSist, sem barbearia vinculada.
- `admin`: dono/administrador de uma barbearia específica.

Também incorpora a cobrança SaaS central do BarbSist via Mercado Pago, separada do Mercado Pago OAuth de cada barbearia.

## Principais alterações
- `Usuario.barbearia_id` passa a aceitar `NULL` somente para o desenho global do Superadmin.
- Login aceita `barbearia_slug` opcional: Superadmin entra por e-mail/senha; usuários operacionais continuam exigindo slug.
- Recuperação de senha também suporta Superadmin global.
- `criar_superadmin_producao.py` cria/atualiza Superadmin com `barbearia_id=NULL`.
- Novas tabelas: `planos_saas`, `assinaturas_saas`, `pagamentos_saas`.
- Checkout SaaS PIX e cartão parcelado usa credenciais centrais do BarbSist.
- Webhook SaaS separado do Webhook Mercado Pago das barbearias.
- Rotas Superadmin para planos, assinaturas, pagamentos, bloqueio/liberação e status do MP central.
- Resumo da plataforma em `/admin/plataforma/resumo`.

## Credenciais centrais do BarbSist
Configurar no `.env`/Railway:
- `BARBSIST_MP_ACCESS_TOKEN`
- `BARBSIST_MP_PUBLIC_KEY`
- `BARBSIST_MP_WEBHOOK_SECRET`
- `PUBLIC_BACKEND_URL`

Não confundir com OAuth de cada barbearia.

## Migração
Faça backup do banco e execute:

    python .\migrar_superadmin_saas.py

O script também cria Mensal, Semestral e Anual a R$ 0,01 apenas para homologação caso ainda não existam. Ajuste os preços antes de produção.

## Rotas principais
Superadmin:
- `GET /admin/plataforma/resumo`
- `GET/POST/PUT /admin/barbsist-assinaturas/planos...`
- `GET /admin/barbsist-assinaturas/assinaturas`
- `GET /admin/barbsist-assinaturas/pagamentos`
- `PUT /admin/barbsist-assinaturas/assinaturas/{id}/liberar`
- `PUT /admin/barbsist-assinaturas/assinaturas/{id}/bloquear`
- `GET /admin/barbsist-assinaturas/mercado-pago/status`

Admin da barbearia:
- `GET /barbsist-assinaturas/planos`
- `GET /barbsist-assinaturas/minha-assinatura`
- `GET /barbsist-assinaturas/mercado-pago/public-key`
- `POST /barbsist-assinaturas/checkout/pix`
- `POST /barbsist-assinaturas/checkout/cartao`

Público para notificações MP:
- `POST /barbsist-assinaturas/webhook`

## Importante
Este patch NÃO ativa ainda o bloqueio automático de login por inadimplência. Primeiro homologue checkout + Webhook + painel Superadmin; depois ative a trava de acesso mantendo a área de pagamento disponível.
