"""Regras de status e de quando disparar alerta."""

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
