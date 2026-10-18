import base64

from faltas import publicar_github


def test_envia_arquivos_pro_branch(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<html>")
    (tmp_path / "data.enc.json").write_text("{}")
    chamadas = []

    def falso(metodo, url, token, corpo=None):
        chamadas.append((metodo, url.split("/repos/")[1], corpo))
        if url.endswith("/branches/painel"):
            return 200, {}
        if metodo == "GET" and "index.html" in url:
            return 200, {"sha": "abc", "content": base64.b64encode(b"<html>").decode()}
        if metodo == "GET":
            return 404, {}
        return 201, {}

    monkeypatch.setattr(publicar_github, "_req", falso)
    publicar_github.enviar("eu/repo", "tok", tmp_path)
    puts = [c for c in chamadas if c[0] == "PUT"]
    # index.html igual ao publicado não é reenviado; data.enc.json é novo
    assert len(puts) == 1 and puts[0][1] == "eu/repo/contents/data.enc.json"
    assert puts[0][2]["branch"] == "painel" and "sha" not in puts[0][2]
