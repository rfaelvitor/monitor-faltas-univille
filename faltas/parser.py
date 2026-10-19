"""Leitura do HTML do portal (Enturma) da Univille."""
import re

from bs4 import BeautifulSoup

RE_SLUG = re.compile(r"^/community/([^/?#]+)$")
RE_SEMESTRE = re.compile(r"-(\d{4}-\d)$")
RE_SIGLA = re.compile(r"\[([^\]]+)\]")
RE_NUM = re.compile(r"(\d+(?:[.,]\d+)?)")


MINUSCULAS = {"de", "da", "do", "das", "dos", "e", "em", "na", "no", "nas", "nos", "a", "o", "para", "com", "por", "ao", "à", "às", "aos"}
ROMANOS = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}


def nome_curto(nome):
    """'ESTRUTURAS DE DADOS I [ESD_I] - GERENCIAL-ENGETEC (2026-2)' vira 'Estruturas de Dados 1'."""
    base = re.split(r"\s*\[", nome, maxsplit=1)[0].strip()
    base = re.sub(r"\s*\(\d{4}-\d\)\s*$", "", base)  # sem sigla, tira só o semestre do fim
    palavras = base.split()
    if not palavras:
        return nome.strip()
    saida = []
    for i, p in enumerate(palavras):
        if i == len(palavras) - 1 and i > 0 and p.upper() in ROMANOS:
            saida.append(str(ROMANOS[p.upper()]))  # algarismo romano no fim vira número
        elif i > 0 and p.lower() in MINUSCULAS:
            saida.append(p.lower())
        else:
            saida.append("-".join(x.capitalize() for x in p.split("-")))
    return " ".join(saida)


def _num(texto, tipo=int, padrao=0):
    m = RE_NUM.search(texto or "")
    if not m:
        return padrao
    return tipo(m.group(1).replace(",", "."))


def ler_disciplinas(html_myspace):
    """Lista as disciplinas da home (Meu Espaço)."""
    sopa = BeautifulSoup(html_myspace, "lxml")
    vistas = {}
    for a in sopa.select(".item-community > a[href]"):
        m = RE_SLUG.match(a["href"].strip())
        if not m:
            continue
        slug = m.group(1)
        nome_tag = a.select_one(".name")
        nome = (nome_tag.get_text(" ", strip=True) if nome_tag else a.get("title", slug)).strip()
        sem = RE_SEMESTRE.search(slug)
        sigla = RE_SIGLA.search(nome)
        vistas[slug] = {
            "codigo": slug,
            "nome": nome_curto(nome),
            "nome_completo": nome,
            "sigla": sigla.group(1) if sigla else slug.split(".")[-1].upper(),
            "semestre": sem.group(1) if sem else None,
        }
    return list(vistas.values())


def filtrar_semestre(disciplinas, semestre=None):
    """Mantém só o semestre pedido, ou o mais recente encontrado."""
    com_sem = [d for d in disciplinas if d["semestre"]]
    if not com_sem:
        return disciplinas
    alvo = semestre or max(d["semestre"] for d in com_sem)
    return [d for d in com_sem if d["semestre"] == alvo]


def ler_professores(html_gradebook):
    """Professores (codeTeacher) com link de frequência na página do diário."""
    sopa = BeautifulSoup(html_gradebook, "lxml")
    professores = {}
    for a in sopa.select('a[href*="studentPresence"]'):
        m = re.search(r"codeTeacher=(\d+)", a["href"])
        if not m:
            continue
        codigo = m.group(1)
        if codigo in professores:
            continue
        li = a.find_parent("ul")
        li = li.find_parent("li") if li else None
        nome_tag = li.find("b") if li else None
        professores[codigo] = nome_tag.get_text(strip=True) if nome_tag else ""
    return [{"codigo": c, "nome": n} for c, n in professores.items()]


def _bimestre_vazio():
    return {"faltas": 0, "justificadas": 0, "aulas": 0, "frequencia": None, "docente": ""}


def ler_frequencia(html_presenca):
    """Totais de faltas por bimestre na página 'Controle de Frequência / Conteúdo'."""
    sopa = BeautifulSoup(html_presenca, "lxml")
    raiz = sopa.select_one("#studentGrades")
    if raiz is None:
        raise ValueError("Página de frequência sem #studentGrades (layout mudou ou sessão expirou)")

    resultado = {"b1": _bimestre_vazio(), "b2": _bimestre_vazio()}
    for periodo in raiz.select("table.seePeriod"):
        cab = periodo.select_one(".headerPeriod")
        titulo = cab.get_text(strip=True) if cab else ""
        if titulo.startswith("1"):
            chave = "b1"
        elif titulo.startswith("2"):
            chave = "b2"
        else:
            continue

        b = _bimestre_vazio()
        for td in periodo.select(".totalFreq"):
            texto = td.get_text(" ", strip=True).lower()
            if "justificad" in texto:
                b["justificadas"] = _num(texto)
            elif "falta" in texto:
                b["faltas"] = _num(texto)
            elif "aula" in texto:
                b["aulas"] = _num(texto)
            elif "frequ" in texto:
                b["frequencia"] = _num(texto, float, None)

        # se o rodapé não vier, soma linha a linha
        linhas = periodo.select("tr.info01, tr.info02")
        if linhas and not periodo.select(".totalFreq"):
            for tr in linhas:
                tds = tr.find_all("td")
                if len(tds) >= 6:
                    b["aulas"] += _num(tds[1].get_text())
                    b["faltas"] += _num(tds[4].get_text())
                    b["justificadas"] += _num(tds[5].get_text())

        for linha in periodo.select("table.periodDesc tr"):
            rotulo = linha.select_one(".labelP")
            valor = linha.select_one(".tdP")
            if rotulo and valor and "docente" in rotulo.get_text().lower():
                b["docente"] = valor.get_text(" ", strip=True)

        resultado[chave] = b
    return resultado


def tem_formulario_login(html):
    return 'id="loginForm"' in html or "id='loginForm'" in html


RE_DATA = re.compile(r"(\d{2})-(\d{2})-(\d{4})\s+(\d{2}):(\d{2})")


def _data_iso(texto):
    m = RE_DATA.search(texto or "")
    if not m:
        return None
    d, mes, a, h, mi = m.groups()
    return f"{a}-{mes}-{d}T{h}:{mi}"


def _entregue(texto):
    t = " ".join(texto.lower().split())
    if "não foi entregue" in t or "nao foi entregue" in t:
        return False
    # trabalho em equipe mostra parciais e finais; só conta como entregue com resposta final
    if "parcia" in t and "fina" not in t:
        return False
    return "enviad" in t


def ler_trabalhos(html_trabalhos):
    """Lista da página 'Trabalhos / Atividades' (Homework.html). Disciplina sem trabalho não tem tabela."""
    sopa = BeautifulSoup(html_trabalhos, "lxml")
    tabela = sopa.select_one("#homeworkList")
    if tabela is None:
        return []
    trabalhos = []
    for tr in tabela.select("tbody > tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 6:
            continue
        link = tds[0].find("a")
        titulo = (link.get("data-title") or link.get_text(strip=True)) if link else tds[0].get_text(" ", strip=True)
        resposta = tds[4].get_text(" ", strip=True)
        trabalhos.append({
            "id": (link.get("data-id") if link else None) or titulo,
            "titulo": titulo.strip(),
            "inicio": _data_iso(tds[1].get_text()),
            "prazo": _data_iso(tds[2].get_text()),
            "equipe": tds[3].get_text(" ", strip=True),
            "resposta": resposta,
            "entregue": _entregue(resposta),
            "situacao": tds[5].get_text(" ", strip=True),
        })
    rodape = tabela.select_one("tfoot")
    if rodape:
        m = re.search(r"Total de (\d+)", rodape.get_text())
        if m and int(m.group(1)) > len(trabalhos):
            print(f"AVISO: página de trabalhos mostra {len(trabalhos)} de {m.group(1)} (paginação não tratada)")
    return trabalhos
