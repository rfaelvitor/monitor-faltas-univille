"""Regras de status e de quando disparar alerta."""
from datetime import datetime


STATUS = {
    "ok": "Tranquilo",
    "atencao": "Atenção",
    "alerta": "Perto do limite",
    "limite": "No limite",
    "reprovado": "Reprovado por falta",
}


def status_de(total, limite, niveis):
    if total > limite:
        return "reprovado"
    if total == limite:
        return "limite"
    primeiro = niveis[0] if niveis else limite
    # alerta forte da metade do caminho entre o primeiro nível e o limite (10..18 -> 14)
    corte_alerta = primeiro + (limite - primeiro) // 2
    if total >= corte_alerta:
        return "alerta"
    if total >= primeiro:
        return "atencao"
    return "ok"


def nivel_atingido(total, niveis, limite):
    """Maior nível de alerta que o total já alcançou (0 se nenhum)."""
    pontos = sorted({n for n in niveis if n <= limite} | {limite, limite + 1})
    alcancados = [n for n in pontos if total >= n]
    return alcancados[-1] if alcancados else 0


def calcular_alertas(disciplinas, enviados, niveis):
    """Compara com os níveis já avisados e devolve (novos_alertas, enviados_atualizado).

    Se as faltas diminuírem (falta justificada, correção do professor),
    o nível avisado desce junto, pra poder avisar de novo depois.
    """
    novos = []
    atualizado = {}
    for d in disciplinas:
        cod = d["codigo"]
        nivel = nivel_atingido(d["total"], niveis, d["limite"])
        anterior = enviados.get(cod, 0)
        if nivel > anterior:
            novos.append({**d, "nivel": nivel})
        atualizado[cod] = nivel
    return novos, atualizado


def margem(total, limite):
    return max(limite - total, 0)


# estágios de aviso de trabalho, em ordem; cada um é avisado no máximo uma vez
ESTAGIOS = {"novo": 1, "3d": 2, "1d": 3, "vencido": 4}
TEXTO_ESTAGIO = {
    "novo": "trabalho novo",
    "3d": "vence em até 3 dias",
    "1d": "vence em menos de 1 dia",
    "vencido": "prazo passou e não foi entregue",
}


def estagio_trabalho(t, agora):
    """Em que ponto o trabalho está (None se já foi entregue)."""
    if t["entregue"]:
        return None
    if not t.get("prazo"):
        return "novo"
    prazo = datetime.fromisoformat(t["prazo"]).replace(tzinfo=agora.tzinfo)
    falta = (prazo - agora).total_seconds() / 3600
    if falta < 0:
        return "vencido"
    if falta <= 24:
        return "1d"
    if falta <= 72:
        return "3d"
    return "novo"


def calcular_avisos_trabalhos(trabalhos, avisados, agora):
    """Devolve (avisos_novos, avisados_atualizado).

    avisados guarda o maior estágio já avisado por trabalho. Na primeira vez
    (avisados None) os vencidos antigos entram calados, pra não chegar um
    e-mail com tudo que ficou pra trás no semestre.
    """
    primeira = avisados is None
    avisados = dict(avisados or {})
    novos = []
    for t in trabalhos:
        chave = f"{t['codigo_disciplina']}:{t['id']}"
        est = estagio_trabalho(t, agora)
        if est is None:
            continue
        rank = ESTAGIOS[est]
        if rank <= avisados.get(chave, 0):
            continue
        avisados[chave] = rank
        if primeira and est == "vencido":
            continue
        novos.append({**t, "estagio": est})
    return novos, avisados


def pendentes(trabalhos, agora):
    """Trabalhos não entregues com prazo ainda aberto, do mais urgente pro menos."""
    abertos = [t for t in trabalhos if estagio_trabalho(t, agora) in ("novo", "3d", "1d")]
    return sorted(abertos, key=lambda t: t.get("prazo") or "9999")
