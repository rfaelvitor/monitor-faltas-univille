from faltas.config import Config


def _base(monkeypatch):
    monkeypatch.setenv("UNIVILLE_USUARIO", "x")
    monkeypatch.setenv("UNIVILLE_SENHA", "y")
    monkeypatch.delenv("PERFIL_NAVEGADOR", raising=False)


def test_perfil_padrao_so_com_navegador_visivel(monkeypatch):
    _base(monkeypatch)
    monkeypatch.setenv("HEADLESS", "1")
    assert Config.carregar().perfil is None
    monkeypatch.setenv("HEADLESS", "0")
    assert Config.carregar().perfil == "~/.monitor-faltas/perfil"


def test_perfil_pode_ser_desligado(monkeypatch):
    _base(monkeypatch)
    monkeypatch.setenv("HEADLESS", "0")
    monkeypatch.setenv("PERFIL_NAVEGADOR", "0")
    assert Config.carregar().perfil is None


def test_sessao_salva_so_com_navegador_visivel(monkeypatch):
    _base(monkeypatch)
    monkeypatch.delenv("SESSAO_SALVA", raising=False)
    monkeypatch.setenv("HEADLESS", "1")
    assert Config.carregar().sessao is None
    monkeypatch.setenv("HEADLESS", "0")
    assert Config.carregar().sessao == "~/.monitor-faltas/sessao.json"
    monkeypatch.setenv("SESSAO_SALVA", "0")
    assert Config.carregar().sessao is None
