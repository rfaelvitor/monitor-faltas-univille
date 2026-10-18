from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from faltas import email_alerta, parser, regras

FUSO = ZoneInfo("America/Sao_Paulo")
FIX = Path(__file__).parent / "fixtures"


def trabalhos():
    lista = parser.ler_trabalhos((FIX / "trabalhos.html").read_text(encoding="cp1252"))
    return [{**t, "codigo_disciplina": "esd", "sigla": "ESD_I"} for t in lista]


def em(texto):
    return datetime.fromisoformat(texto).replace(tzinfo=FUSO)


def test_parser_le_tabela():
    ts = trabalhos()
    assert [t["entregue"] for t in ts] == [False, True, True, False]
    assert ts[3]["titulo"] == "Exercício Recursão" and ts[3]["prazo"] == "2026-10-21T23:55"


def test_sem_tabela_e_lista_vazia():
    assert parser.ler_trabalhos("<html><body>nada aqui</body></html>") == []


def test_entregue_em_equipe_so_com_resposta_final():
    assert parser._entregue("4 respostas parciais enviadas 2 respostas finais enviadas")
    assert not parser._entregue("2 respostas parciais enviadas")
    assert not parser._entregue("não foi entregue")


def test_estagios_pela_data():
    t = trabalhos()[3]  # prazo 21/10 23:55
    assert regras.estagio_trabalho(t, em("2026-10-15T10:00")) == "novo"
    assert regras.estagio_trabalho(t, em("2026-10-19T10:00")) == "3d"
    assert regras.estagio_trabalho(t, em("2026-10-21T08:00")) == "1d"
    assert regras.estagio_trabalho(t, em("2026-10-22T08:00")) == "vencido"
    assert regras.estagio_trabalho({**t, "entregue": True}, em("2026-10-21T08:00")) is None


def test_sequencia_de_avisos_cada_um_uma_vez():
    ts = trabalhos()
    novos, av = regras.calcular_avisos_trabalhos(ts, None, em("2026-10-15T10:00"))
    assert [n["estagio"] for n in novos] == ["novo"]  # vencidos antigos calados
    novos, av = regras.calcular_avisos_trabalhos(ts, av, em("2026-10-16T10:00"))
    assert novos == []
    novos, av = regras.calcular_avisos_trabalhos(ts, av, em("2026-10-19T10:00"))
    assert [n["estagio"] for n in novos] == ["3d"]
    novos, av = regras.calcular_avisos_trabalhos(ts, av, em("2026-10-21T10:00"))
    assert [n["estagio"] for n in novos] == ["1d"]
    novos, av = regras.calcular_avisos_trabalhos(ts, av, em("2026-10-22T10:00"))
    assert [n["estagio"] for n in novos] == ["vencido"]
    novos, av = regras.calcular_avisos_trabalhos(ts, av, em("2026-10-23T10:00"))
    assert novos == []


def test_entregue_depois_para_de_avisar():
    ts = trabalhos()
    _, av = regras.calcular_avisos_trabalhos(ts, None, em("2026-10-15T10:00"))
    ts[3]["entregue"] = True
    novos, _ = regras.calcular_avisos_trabalhos(ts, av, em("2026-10-21T10:00"))
    assert novos == []


def test_email_so_de_trabalho():
    ts = trabalhos()
    novos, _ = regras.calcular_avisos_trabalhos(ts[3:], {}, em("2026-10-21T10:00"))
    assunto, corpo = email_alerta.montar_alerta([], [], None, novos, regras.pendentes(ts, em("2026-10-21T10:00")))
    assert assunto.startswith("[Trabalhos] ESD_I: Exercício Recursão")
    assert "21/10 23:55" in corpo
