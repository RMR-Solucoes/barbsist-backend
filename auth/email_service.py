import os

import resend
from dotenv import load_dotenv


load_dotenv()


RESEND_API_KEY = os.getenv(
    "RESEND_API_KEY",
    "",
).strip()

EMAIL_FROM = os.getenv(
    "EMAIL_FROM",
    "BarbSist <onboarding@resend.dev>",
).strip()


class ErroEnvioEmail(Exception):
    pass


def validar_configuracao_resend():
    if not RESEND_API_KEY:
        raise ErroEnvioEmail(
            "Configura??o do Resend incompleta: "
            "RESEND_API_KEY."
        )


def enviar_email_recuperacao_senha(
    destinatario: str,
    nome_usuario: str,
    link_recuperacao: str,
    expira_minutos: int = 30,
):
    validar_configuracao_resend()

    nome_exibicao = (
        nome_usuario.strip()
        if nome_usuario
        else "usu?rio"
    )

    assunto = "Redefini??o de senha ? BarbSist"

    texto = f"""Ol?, {nome_exibicao}.

Recebemos uma solicita??o para redefinir a senha da sua conta no BarbSist.

Acesse o link abaixo:

{link_recuperacao}

Este link expira em {expira_minutos} minutos e poder? ser utilizado apenas uma vez.

Caso voc? n?o tenha solicitado essa altera??o, ignore este e-mail.

Atenciosamente,
Equipe BarbSist
"""

    html = f"""
    <div style="
        font-family: Arial, sans-serif;
        max-width: 600px;
        margin: 0 auto;
        padding: 24px;
        color: #111827;
    ">
        <h1 style="
            font-size: 24px;
            margin-bottom: 24px;
        ">
            Redefini??o de senha
        </h1>

        <p>Ol?, {nome_exibicao}.</p>

        <p>
            Recebemos uma solicita??o para redefinir
            a senha da sua conta no BarbSist.
        </p>

        <p style="text-align: center; margin: 32px 0;">
            <a
                href="{link_recuperacao}"
                style="
                    display: inline-block;
                    background: #2563eb;
                    color: #ffffff;
                    text-decoration: none;
                    padding: 14px 24px;
                    border-radius: 8px;
                    font-weight: bold;
                "
            >
                Redefinir minha senha
            </a>
        </p>

        <p>
            Este link expira em
            <strong>{expira_minutos} minutos</strong>
            e poder? ser utilizado apenas uma vez.
        </p>

        <p>
            Caso voc? n?o tenha solicitado essa altera??o,
            ignore este e-mail.
        </p>

        <p style="margin-top: 32px;">
            Atenciosamente,<br>
            Equipe BarbSist
        </p>
    </div>
    """

    try:
        resend.api_key = RESEND_API_KEY

        resposta = resend.Emails.send({
            "from": EMAIL_FROM,
            "to": [destinatario],
            "subject": assunto,
            "text": texto,
            "html": html,
        })

        return resposta

    except Exception as erro:
        raise ErroEnvioEmail(
            "N?o foi poss?vel enviar o e-mail "
            "de recupera??o de senha."
        ) from erro
