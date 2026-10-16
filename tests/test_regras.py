from faltas import cripto, regras

NIVEIS = [10, 12, 14, 16, 18]


def d(cod, total, limite=18):
    return {"codigo": cod, "total": total, "limite": limite}


def test_status():
    assert regras.status_de(8, 18, NIVEIS) == "ok"
    assert regras.status_de(10, 18, NIVEIS) == "atencao"
    assert regras.status_de(14, 18, NIVEIS) == "alerta"
    assert regras.status_de(18, 18, NIVEIS) == "limite"
    assert regras.status_de(19, 18, NIVEIS) == "reprovado"


def test_nivel_atingido():
    assert regras.nivel_atingido(9, NIVEIS, 18) == 0
    assert regras.nivel_atingido(11, NIVEIS, 18) == 10
    assert regras.nivel_atingido(16, NIVEIS, 18) == 16
    assert regras.nivel_atingido(20, NIVEIS, 18) == 19


def test_limite_maior_inclui_o_proprio_limite():
    assert regras.nivel_atingido(20, NIVEIS, 20) == 20
    assert regras.nivel_atingido(21, NIVEIS, 20) == 21


def test_alerta_so_quando_sobe_de_nivel():
    novos, env = regras.calcular_alertas([d("a", 12), d("b", 5)], {"a": 10}, NIVEIS)
    assert [n["codigo"] for n in novos] == ["a"] and env == {"a": 12, "b": 0}

    novos, env = regras.calcular_alertas([d("a", 13), d("b", 5)], env, NIVEIS)
    assert novos == []


def test_pula_niveis_gera_um_alerta_so():
    novos, env = regras.calcular_alertas([d("a", 16)], {"a": 10}, NIVEIS)
    assert len(novos) == 1 and novos[0]["nivel"] == 16


def test_falta_justificada_rearma_alerta():
    _, env = regras.calcular_alertas([d("a", 11)], {"a": 12}, NIVEIS)
    assert env["a"] == 10
    novos, _ = regras.calcular_alertas([d("a", 12)], env, NIVEIS)
    assert len(novos) == 1


def test_cripto_ida_e_volta():
    dados = {"x": "ção", "n": [1, 2]}
    pacote = cripto.cifrar(dados, "segredo")
    assert "ção" not in str(pacote)
    assert cripto.decifrar(pacote, "segredo") == dados
