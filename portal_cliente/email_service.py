import os
import resend
from dotenv import load_dotenv

load_dotenv()


def enviar_email_confirmacao_portal_cliente(destinatario: str, nome: str, codigo: str, expira_minutos: int = 15):
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    remetente = os.getenv("EMAIL_FROM", "BarbSist <onboarding@resend.dev>").strip()
    if not api_key:
        raise RuntimeError("RESEND_API_KEY não configurada. A conta não foi criada.")
    resend.api_key = api_key
    return resend.Emails.send({
        "from": remetente,
        "to": [destinatario],
        "subject": "Confirme seu acesso ao BarbSist",
        "text": f"Olá, {nome}. Seu código de confirmação é {codigo}. Ele expira em {expira_minutos} minutos.",
        "html": f"<p>Olá, {nome}.</p><p>Seu código de confirmação é:</p><p style='font-size:28px;font-weight:bold;letter-spacing:6px'>{codigo}</p><p>Ele expira em {expira_minutos} minutos.</p>",
    })
