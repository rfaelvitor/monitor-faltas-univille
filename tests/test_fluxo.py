"""Roda o fluxo inteiro com um portal falso (sem rede)."""
import json
from pathlib import Path

import pytest

from faltas import cripto, main, parser

FIX = Path(__file__).parent / "fixtures"


def ler(nome):
    return (FIX / nome).read_text(encoding="cp1252")


class PortalFalso:
    faltas_extra = 0

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def login(self):
        pass

    def home(self):
        return ler("myspace.html")

    def professores(self, slug):
        return parser.ler_professores(ler("gradebook_dois_professores.html"))

    def frequencia(self, slug, prof):
        if "esd_i" in slug and prof == "155670":
            f = parser.ler_frequencia(ler("presenca_dois_bimestres.html"))
            f["b2"]["faltas"] += PortalFalso.faltas_extra
        elif "esd_i" in slug:
            f = parser.ler_frequencia(ler("presenca_vazia.html"))
        else:
            f = parser.ler_frequencia(ler("presenca_so_primeiro.html"))
        return f"/community/{slug}/GradeBook.html?action=studentPresence&codeTeacher={prof}", f


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    for k, v in {
        "UNIVILLE_USUARIO": "x", "UNIVILLE_SENHA": "y", "SENHA_PAINEL": "painel123",
        "PASTA_SAIDA": str(tmp_path / "site"), "GMAIL_USUARIO": "a@b.com", "GMAIL_SENHA_APP": "z",
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("URL_PAINEL", raising=False)
    enviados = []
    monkeypatch.setattr(main, "Portal", PortalFalso)
    monkeypatch.setattr(main.email_alerta, "enviar", lambda cfg, a, c: enviados.append(a) or True)
    PortalFalso.faltas_extra = 0
    return tmp_path / "site", enviados


def estado(pasta):
    return cripto.decifrar(json.loads((pasta / "data.enc.json").read_text()), "painel123")


def test_primeira_execucao_manda_resumo(ambiente):
    pasta, enviados = ambiente
    main.executar()
    assert len(enviados) == 1 and "Monitor ativado" in enviados[0]
    dados = estado(pasta)
    esd = next(d for d in dados["disciplinas"] if d["sigla"] == "ESD_I")
    assert esd["total"] == 16 and esd["status"] == "alerta" and esd["margem"] == 2
    assert esd["docente"] == "PROFESSOR EXEMPLO"
    assert dados["alertas_enviados"][esd["codigo"]] == 16
    assert (pasta / "index.html").exists() and not (pasta / "data.json").exists()


def test_sem_mudanca_nao_manda_nada(ambiente):
    _, enviados = ambiente
    main.executar()
    main.executar()
    assert len(enviados) == 1


def test_nova_falta_cruza_nivel(ambiente):
    pasta, enviados = ambiente
    main.executar()
    PortalFalso.faltas_extra = 2
    main.executar()
    assert len(enviados) == 2 and "ESD_I: 18 faltas, no limite" in enviados[1]
    hist = [h for h in estado(pasta)["historico"] if h["sigla"] == "ESD_I"]
    assert [h["total"] for h in hist] == [16, 18]


def test_uma_vez_por_dia_pula_segunda_execucao(ambiente, monkeypatch):
    _, enviados = ambiente
    monkeypatch.setenv("UMA_VEZ_POR_DIA", "1")
    assert main.executar() is True
    PortalFalso.faltas_extra = 2
    assert main.executar() is False
    monkeypatch.setenv("FORCAR", "1")
    assert main.executar() is True
    assert len(enviados) == 2
