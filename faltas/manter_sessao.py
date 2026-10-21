"""Mantém a sessão do portal viva entre as verificações.

Roda a cada 30 minutos (tarefa separada no Agendador), sem abrir navegador: só pede a home do portal
com o cookie salvo em sessao.json. Se o portal renova a sessão a cada acesso, ela não expira e a
verificação diária entra sem captcha. Cada rodada anota uma linha em sessao-teste.log.
"""
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from . import parser
from .config import Config

URL = "https://www.univille.edu.br/account/MySpace.html"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"


def _anotar(caminho, texto):
    linha = f"{datetime.now():%Y-%m-%d %H:%M} | {texto}"
    print(linha)
    try:
        with open(caminho.with_name("sessao-teste.log"), "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except Exception:
        pass


def _renovar_valores(cookies, set_cookies):
    # se o portal mandar um valor novo pro cookie de sessão, guarda
    for sc in set_cookies:
        nome, _, resto = sc.partition("=")
        for c in cookies:
            if c["name"] == nome.strip():
                c["value"] = resto.split(";")[0]


def executar(caminho):
    caminho = Path(caminho).expanduser()
    if not caminho.exists():
        return
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    if dados.get("expirou_em"):
        return  # já expirou e foi anotado; só um novo login pelo navegador recomeça
    cookies = dados["cookies"]
    req = urllib.request.Request(URL, headers={
        "Cookie": "; ".join(f"{c['name']}={c['value']}" for c in cookies),
        "User-Agent": UA,
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            corpo = resp.read().decode("cp1252", errors="replace")
            set_cookies = resp.headers.get_all("Set-Cookie") or []
    except Exception as e:  # sem rede não prova que a sessão caiu
        _anotar(caminho, f"manter sessão: sem resposta do portal ({e})")
        return
    horas = (time.time() - dados.get("login_em", dados["salvo_em"])) / 3600
    if parser.tem_formulario_login(corpo):
        dados["expirou_em"] = time.time()
        _anotar(caminho, f"manter sessão: EXPIROU, {horas:.1f}h depois do login")
    else:
        _renovar_valores(cookies, set_cookies)
        dados["salvo_em"] = time.time()
        _anotar(caminho, f"manter sessão: ok, {horas:.1f}h depois do login")
    caminho.write_text(json.dumps(dados), encoding="utf-8")


def main():
    cfg = Config.carregar()
    if cfg.sessao:
        executar(cfg.sessao)


if __name__ == "__main__":
    main()
