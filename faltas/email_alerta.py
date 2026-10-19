import html
import smtplib
from email.message import EmailMessage

from datetime import datetime

from .regras import STATUS, TEXTO_ESTAGIO, margem

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
        f"<td style='padding:6px 10px;border-bottom:1px solid #eee;text-align:center'>{d['total']}</td>"
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


def _disc(t):
    return t.get("disciplina") or t["sigla"]


def _prazo(t):
    if not t.get("prazo"):
        return "sem prazo"
    return datetime.fromisoformat(t["prazo"]).strftime("%d/%m %H:%M")


COR_ESTAGIO = {"novo": "#1d4ed8", "3d": "#b45309", "1d": "#b91c1c", "vencido": "#7f1d1d"}


def _bloco_trabalhos(avisos):
    if not avisos:
        return ""
    itens = "".join(
        f"<li><b>{html.escape(_disc(t))}</b>: {html.escape(t['titulo'])}, prazo {_prazo(t)} "
        f"<span style='color:{COR_ESTAGIO[t['estagio']]}'>({TEXTO_ESTAGIO[t['estagio']]})</span></li>"
        for t in avisos
    )
    return f"<div style='font-family:Arial,sans-serif;font-size:14px'><p>Trabalhos:</p><ul>{itens}</ul></div>"


def _tabela_pendentes(pendentes):
    if not pendentes:
        return "<p style='font-family:Arial,sans-serif;font-size:13px'>Nenhum trabalho pendente com prazo aberto.</p>"
    cab = "".join(
        f"<th style='padding:6px 10px;text-align:left;border-bottom:2px solid #ccc'>{t}</th>"
        for t in ["Disciplina", "Trabalho", "Prazo"]
    )
    linhas = "".join(
        "<tr>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #eee'>{html.escape(_disc(t))}</td>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #eee'>{html.escape(t['titulo'])}</td>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #eee'>{_prazo(t)}</td>"
        "</tr>"
        for t in pendentes
    )
    return (
        "<p style='font-family:Arial,sans-serif;font-size:14px'>Trabalhos pendentes:</p>"
        f"<table style='border-collapse:collapse;font-family:Arial,sans-serif;font-size:14px'><tr>{cab}</tr>{linhas}</table>"
    )


def _assunto_trabalhos(avisos):
    if len(avisos) == 1:
        t = avisos[0]
        return f"[Trabalhos] {_disc(t)}: {t['titulo']} ({TEXTO_ESTAGIO[t['estagio']]})"
    return f"[Trabalhos] {len(avisos)} avisos de trabalho"


def montar_alerta(novos, disciplinas, url_painel=None, avisos_trab=(), pendentes_trab=()):
    if not novos:
        assunto = _assunto_trabalhos(avisos_trab)
        corpo = _bloco_trabalhos(avisos_trab) + _tabela_pendentes(pendentes_trab) + _rodape(url_painel)
        return assunto, corpo
    if len(novos) == 1:
        d = novos[0]
        limite = d["limite"]
        if d["total"] > limite:
            assunto = f"[Faltas] {d['nome']}: {d['total']} faltas, passou do limite de {limite}"
        elif d["total"] == limite:
            assunto = f"[Faltas] {d['nome']}: {d['total']} faltas, no limite (mais uma reprova)"
        else:
            assunto = f"[Faltas] {d['nome']}: {d['total']} faltas, sobram {margem(d['total'], limite)}"
    else:
        assunto = f"[Faltas] {len(novos)} disciplinas subiram de nível"

    itens = "".join(
        f"<li><b>{html.escape(d['nome'])}</b>: {d['total']} faltas "
        f"({d['b1']['faltas']} no 1º bim + {d['b2']['faltas']} no 2º), "
        f"pode faltar mais {margem(d['total'], d['limite'])}</li>"
        for d in novos
    )
    if avisos_trab:
        assunto = assunto.replace("[Faltas]", "[Faltas e trabalhos]", 1)
    corpo = (
        "<div style='font-family:Arial,sans-serif;font-size:14px'>"
        f"<p>Novo nível de faltas atingido:</p><ul>{itens}</ul>"
        "</div>"
        + _bloco_trabalhos(avisos_trab)
        + "<p style='font-family:Arial,sans-serif;font-size:14px'>Panorama de todas as disciplinas:</p>"
        + _tabela(disciplinas, {d["codigo"] for d in novos})
        + (_tabela_pendentes(pendentes_trab) if avisos_trab else "")
        + _rodape(url_painel)
    )
    return assunto, corpo


def montar_boas_vindas(disciplinas, url_painel=None, pendentes_trab=()):
    assunto = f"[Faltas] Monitor ativado: {len(disciplinas)} disciplinas acompanhadas"
    corpo = (
        "<div style='font-family:Arial,sans-serif;font-size:14px'>"
        "<p>O monitor de faltas está funcionando. Situação atual:</p></div>"
        + _tabela(disciplinas)
        + _tabela_pendentes(pendentes_trab)
        + "<p style='font-family:Arial,sans-serif;font-size:13px'>A partir de agora você só recebe e-mail quando uma disciplina subir de nível de alerta "
        "ou quando um trabalho for novo, estiver a 3 dias ou 1 dia do prazo, ou vencer sem entrega.</p>"
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
