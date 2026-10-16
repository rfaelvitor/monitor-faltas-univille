from pathlib import Path

import pytest

from faltas import parser

FIX = Path(__file__).parent / "fixtures"


def ler(nome):
    return (FIX / nome).read_text(encoding="cp1252")


def test_disciplinas_da_home():
    ds = parser.ler_disciplinas(ler("myspace.html"))
    assert [d["sigla"] for d in ds] == ["ESD_I", "TES_II", "ALG"]
    assert ds[0]["codigo"] == "gerencial-engetec.esd_i-2026-2"
    assert ds[0]["semestre"] == "2026-2"


def test_filtra_semestre_mais_recente():
    ds = parser.filtrar_semestre(parser.ler_disciplinas(ler("myspace.html")))
    assert {d["sigla"] for d in ds} == {"ESD_I", "TES_II"}


def test_filtra_semestre_forcado():
    ds = parser.filtrar_semestre(parser.ler_disciplinas(ler("myspace.html")), "2026-1")
    assert [d["sigla"] for d in ds] == ["ALG"]


def test_professores_sem_repetir():
    profs = parser.ler_professores(ler("gradebook_dois_professores.html"))
    assert profs == [{"codigo": "155670", "nome": "PROFESSORA A"}, {"codigo": "155479", "nome": "PROFESSOR B"}]


def test_frequencia_dois_bimestres():
    f = parser.ler_frequencia(ler("presenca_dois_bimestres.html"))
    assert f["b1"]["faltas"] == 10
    assert f["b1"]["aulas"] == 16
    assert f["b1"]["frequencia"] == pytest.approx(37.5)
    assert f["b1"]["docente"] == "PROFESSOR EXEMPLO"
    assert f["b2"]["faltas"] == 6
    assert f["b2"]["justificadas"] == 0


def test_frequencia_so_primeiro_bimestre():
    f = parser.ler_frequencia(ler("presenca_so_primeiro.html"))
    assert f["b1"]["faltas"] == 4
    assert f["b2"]["faltas"] == 0 and f["b2"]["aulas"] == 0


def test_frequencia_pagina_vazia():
    f = parser.ler_frequencia(ler("presenca_vazia.html"))
    assert f["b1"]["aulas"] == 0 and f["b2"]["aulas"] == 0


def test_pagina_de_login_detectada():
    assert parser.tem_formulario_login(ler("login.html"))
    with pytest.raises(ValueError):
        parser.ler_frequencia(ler("login.html"))
