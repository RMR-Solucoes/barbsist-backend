from email.message import EmailMessage
import os
import smtplib

from dotenv import load_dotenv


load_dotenv(override=True)


SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USUARIO = os.getenv("SMTP_USUARIO", "").strip()
SMTP_SENHA = os.getenv("SMTP_SENHA", "").strip()
SMTP_REMETENTE_NOME = os.getenv(
    "SMTP_REMETENTE_NOME",
    "BarbSist",
).strip()

SMTP_USAR_TLS = os.getenv(
    "SMTP_USAR_TLS",
    "true",
).strip().lower() in {
    "1",
    "true",
    "sim",
    "yes",
}


class ErroEnvioEmail(Exception):
    pass


def validar_configuracao_smtp():
    campos_ausentes = []

    if not SMTP_HOST:
        campos_ausentes.append("SMTP_HOST")

    if not SMTP_USUARIO:
        campos_ausentes.append("SMTP_USUARIO")

    if not SMTP_SENHA:
        campos_ausentes.append("SMTP_SENHA")

    if campos_ausentes:
        raise ErroEnvioEmail(
            "Configuração SMTP incompleta: "
            + ", ".join(campos_ausentes)
        )


def enviar_email_recuperacao_senha(
    destinatario: str,
    nome_usuario: str,
    link_recuperacao: str,
    expira_minutos: int = 30,
):
    validar_configuracao_smtp()

    nome_exibicao = (
        nome_usuario.strip()
        if nome_usuario
        else "usuário"
    )

    mensagem = EmailMessage()

    mensagem["Subject"] = (
        "Redefinição de senha — BarbSist"
    )

    mensagem["From"] = (
        f"{SMTP_REMETENTE_NOME} <{SMTP_USUARIO}>"
    )

    mensagem["To"] = destinatario

    mensagem.set_content(
        f"""Olá, {nome_exibicao}.

Recebemos uma solicitação para redefinir a senha da sua conta no BarbSist.

Acesse o link abaixo:

{link_recuperacao}

Este link expira em {expira_minutos} minutos e poderá ser utilizado apenas uma vez.

Caso você não tenha solicitado essa alteração, ignore este e-mail.

Atenciosamente,
Equipe BarbSist
"""
    )

    mensagem.add_alternative(
        f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
</head>
<body style="
    margin: 0;
    padding: 24px;
    background: #f3f4f6;
    font-family: Arial, sans-serif;
    color: #111827;
">
    <div style="
        max-width: 600px;
        margin: 0 auto;
        background: #ffffff;
        border-radius: 12px;
        padding: 32px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.08);
    ">
        <h1 style="
            margin-top: 0;
            font-size: 24px;
        ">
            Redefinição de senha
        </h1>

        <p>Olá, {nome_exibicao}.</p>

        <p>
            Recebemos uma solicitação para redefinir
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
            e poderá ser utilizado apenas uma vez.
        </p>

        <p>
            Caso você não tenha solicitado essa alteração,
            ignore este e-mail.
        </p>

        <hr style="
            border: 0;
            border-top: 1px solid #e5e7eb;
            margin: 28px 0;
        ">

        <p style="
            font-size: 13px;
            color: #6b7280;
            margin-bottom: 0;
        ">
            Equipe BarbSist
        </p>
    </div>
</body>
</html>
""",
        subtype="html",
    )

    try:
        with smtplib.SMTP(
            SMTP_HOST,
            SMTP_PORT,
            timeout=20,
        ) as servidor:
            servidor.ehlo()

            if SMTP_USAR_TLS:
                servidor.starttls()
                servidor.ehlo()

            servidor.login(
                SMTP_USUARIO,
                SMTP_SENHA,
            )

            servidor.send_message(
                mensagem
            )

    except Exception as erro:
        raise ErroEnvioEmail(
            "Não foi possível enviar o e-mail "
            "de recuperação de senha."
        ) from erro