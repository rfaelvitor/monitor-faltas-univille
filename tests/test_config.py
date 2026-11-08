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


def test_erro_so_na_ultima_tentativa(monkeypatch):
    from datetime import datetime
    from faltas.main import deve_avisar_erro
    _base(monkeypatch)
    monkeypatch.setenv("HORA_ULTIMA_TENTATIVA", "22")
    cfg = Config.carregar()
    assert not deve_avisar_erro(cfg, datetime(2026, 11, 9, 14, 0))
    assert deve_avisar_erro(cfg, datetime(2026, 11, 9, 22, 5))
    monkeypatch.delenv("HORA_ULTIMA_TENTATIVA")
    assert deve_avisar_erro(Config.carregar(), datetime(2026, 11, 9, 8, 0))


def test_firefox_que_nao_abre_cai_no_chromium(monkeypatch):
    import contextlib
    from faltas import main, portal_firefox

    class Quebrado:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            raise RuntimeError("Process unexpectedly closed")

        def __exit__(self, *a):
            pass

    class Falso(Quebrado):
        def __init__(self, *a, **k):
            self.k = k

        def __enter__(self):
            return self

    monkeypatch.setattr(portal_firefox, "PortalFirefox", Quebrado)
    monkeypatch.setattr(main, "Portal", Falso)
    _base(monkeypatch)
    monkeypatch.setenv("HEADLESS", "0")
    monkeypatch.setenv("NAVEGADOR", "firefox-perfil")
    with contextlib.ExitStack() as pilha:
        p = main.abrir_navegador(Config.carregar(), pilha)
    assert p.k["navegador"] == "chromium" and p.k["perfil"] == "~/.monitor-faltas/perfil"
