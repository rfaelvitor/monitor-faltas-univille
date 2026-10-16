import html
import smtplib
from email.message import EmailMessage

from .regras import STATUS, margem

CORES = {
    "ok": "#1f7a3d",
    "atencao": "#9a6b00",
    "alerta": "#b45309",
    "limite": "#b91c1c",
    "reprovado": "#7f1d1d",
}


def _linha(d, destaque=False):
    limite = d["limite"]
    peso = "font-weight:600;" if destaque else ""
    cor = CORES[d["status"]]
    return (
        f"<tr style='{peso}'>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #eee'>{html.escape(d['nome'])}</td>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #eee;text-align:center'>{d['b1']['faltas']}</td>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #eee;text-align:center'>{d['b2']['faltas']}</td>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #eee;text-align:center'>{d['total']}/{limite}</td>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #eee;text-align:center'>{margem(d['total'], limite)}</td>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #eee;color:{cor}'>{STATUS[d['status']]}</td>"
        "</tr>"
    )


def _tabela(disciplinas, destacar=()):
    cab = "".join(
        f"<th style='padding:6px 10px;text-align:left;border-bottom:2px solid #ccc'>{t}</th>"
        for t in ["Disciplina", "1º bim", "2º bim", "Total", "Pode faltar", "Situação"]
    )
    linhas = "".join(_linha(d, d["codigo"] in destacar) for d in disciplinas)
    return f"<table style='border-collapse:collapse;font-family:Arial,sans-serif;font-size:14px'><tr>{cab}</tr>{linhas}</table>"


def _rodape(url_painel):
    if not url_painel:
        return ""
    return f"<p style='font-family:Arial,sans-serif;font-size:13px'><a href='{html.escape(url_painel)}'>Abrir painel de faltas</a></p>"


def montar_alerta(novos, disciplinas, url_painel=None):
    if len(novos) == 1:
        d = novos[0]
        limite = d["limite"]
        if d["total"] > limite:
            assunto = f"[Faltas] {d['sigla']}: {d['total']} faltas, passou do limite de {limite}"
        elif d["total"] == limite:
            assunto = f"[Faltas] {d['sigla']}: {d['total']} faltas, no limite (mais uma reprova)"
        else:
            assunto = f"[Faltas] {d['sigla']}: {d['total']} faltas, sobram {margem(d['total'], limite)}"
    else:
        assunto = f"[Faltas] {len(novos)} disciplinas subiram de nível"

    itens = "".join(
        f"<li><b>{html.escape(d['nome'])}</b>: {d['total']} faltas "
        f"({d['b1']['faltas']} no 1º bim + {d['b2']['faltas']} no 2º), "
        f"pode faltar mais {margem(d['total'], d['limite'])}</li>"
        for d in novos
    )
    corpo = (
        "<div style='font-family:Arial,sans-serif;font-size:14px'>"
        f"<p>Novo nível de faltas atingido:</p><ul>{itens}</ul>"
        f"<p>Panorama de todas as disciplinas:</p>"
        "</div>"
        + _tabela(disciplinas, {d["codigo"] for d in novos})
        + _rodape(url_painel)
    )
    return assunto, corpo


def montar_boas_vindas(disciplinas, url_painel=None):
    assunto = f"[Faltas] Monitor ativado: {len(disciplinas)} disciplinas acompanhadas"
    corpo = (
        "<div style='font-family:Arial,sans-serif;font-size:14px'>"
        "<p>O monitor de faltas está funcionando. Situação atual:</p></div>"
        + _tabela(disciplinas)
        + "<p style='font-family:Arial,sans-serif;font-size:13px'>A partir de agora você só recebe e-mail quando uma disciplina subir de nível de alerta.</p>"
        + _rodape(url_painel)
    )
    return assunto, corpo


def montar_erro(mensagem):
    assunto = "[Faltas] O monitor não conseguiu verificar hoje"
    corpo = (
        "<div style='font-family:Arial,sans-serif;font-size:14px'>"
        f"<p>A verificação falhou com o erro:</p><pre>{html.escape(mensagem)}</pre>"
        "<p>Se repetir por vários dias, veja a aba Actions do repositório ou rode localmente (README).</p></div>"
    )
    return assunto, corpo


def enviar(cfg, assunto, corpo_html):
    if not cfg.email_configurado:
        print("E-mail não configurado, pulando envio")
        return False
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = cfg.gmail_usuario
    msg["To"] = cfg.email_destino
    msg.set_content("Abra este e-mail num cliente com suporte a HTML.")
    msg.add_alternative(corpo_html, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(cfg.gmail_usuario, cfg.gmail_senha_app)
        smtp.send_message(msg)
    print("E-mail enviado")
    return True
