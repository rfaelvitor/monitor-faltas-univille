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


def test_sessao_desligada_por_padrao_e_navegador(monkeypatch):
    _base(monkeypatch)
    monkeypatch.delenv("SESSAO_SALVA", raising=False)
    monkeypatch.delenv("NAVEGADOR", raising=False)
    monkeypatch.setenv("HEADLESS", "0")
    cfg = Config.carregar()
    assert cfg.sessao is None and cfg.navegador == "chromium" and cfg.perfil == "~/.monitor-faltas/perfil"
    monkeypatch.setenv("NAVEGADOR", "firefox")
    cfg = Config.carregar()
    assert cfg.navegador == "firefox" and cfg.perfil == "~/.monitor-faltas/perfil-firefox"


def test_firefox_perfil(monkeypatch):
    _base(monkeypatch)
    monkeypatch.setenv("HEADLESS", "0")
    monkeypatch.setenv("NAVEGADOR", "firefox-perfil")
    cfg = Config.carregar()
    assert cfg.navegador == "firefox-perfil" and cfg.perfil == "~/.monitor-faltas/perfil-firefox-real"
