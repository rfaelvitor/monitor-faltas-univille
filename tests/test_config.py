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


def test_manter_sessao_renova_ou_marca_expirada(tmp_path, monkeypatch):
    import json
    import time

    from faltas import manter_sessao

    arq = tmp_path / "sessao.json"
    arq.write_text(json.dumps({"salvo_em": time.time() - 3600, "login_em": time.time() - 7200,
                               "cookies": [{"name": "ENTURMA4_8", "value": "a", "domain": ".univille.edu.br", "path": "/"}]}))

    class Resp:
        def __init__(self, corpo, sc=()):
            self.corpo, self.headers = corpo, type("H", (), {"get_all": lambda s, n: list(sc)})()

        def read(self):
            return self.corpo

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    monkeypatch.setattr(manter_sessao.urllib.request, "urlopen",
                        lambda *a, **k: Resp(b"<html><title>Meu Espa\xe7o</title></html>", ["ENTURMA4_8=b; Path=/"]))
    manter_sessao.executar(arq)
    dados = json.loads(arq.read_text())
    assert dados["cookies"][0]["value"] == "b" and "expirou_em" not in dados

    monkeypatch.setattr(manter_sessao.urllib.request, "urlopen",
                        lambda *a, **k: Resp(b'<form id="loginForm"><input id="login"></form>'))
    manter_sessao.executar(arq)
    assert "expirou_em" in json.loads(arq.read_text())
    assert "EXPIROU" in (tmp_path / "sessao-teste.log").read_text()
