"""Manda o painel pro GitHub Pages quando o monitor roda no seu computador.

Grava index.html e data.enc.json no branch "painel" do seu repositório pela API
do GitHub. O Pages publica esse branch sozinho (Settings > Pages > Deploy from a branch).
Precisa de um token fine-grained com permissão Contents: read and write só nesse repo.
"""
import base64
import json
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"
ARQUIVOS = ["index.html", "data.enc.json"]


def _req(metodo, url, token, corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(url, data=dados, method=metodo, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "monitor-faltas-univille",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _garantir_branch(repo, branch, token):
    status, _ = _req("GET", f"{API}/repos/{repo}/branches/{branch}", token)
    if status == 200:
        return
    status, info = _req("GET", f"{API}/repos/{repo}", token)
    if status != 200:
        raise RuntimeError(f"Não acessei o repositório {repo} (HTTP {status}). Confira GITHUB_REPO e o token")
    status, ref = _req("GET", f"{API}/repos/{repo}/git/ref/heads/{info['default_branch']}", token)
    status, _ = _req("POST", f"{API}/repos/{repo}/git/refs", token,
                     {"ref": f"refs/heads/{branch}", "sha": ref["object"]["sha"]})
    if status not in (200, 201):
        raise RuntimeError(f"Não consegui criar o branch {branch} (HTTP {status})")


def enviar(repo, token, pasta, branch="painel"):
    _garantir_branch(repo, branch, token)
    for nome in ARQUIVOS:
        arq = Path(pasta) / nome
        if not arq.exists():
            continue
        url = f"{API}/repos/{repo}/contents/{nome}"
        status, atual = _req("GET", f"{url}?ref={branch}", token)
        corpo = {
            "message": f"Atualiza {nome}",
            "content": base64.b64encode(arq.read_bytes()).decode(),
            "branch": branch,
        }
        if status == 200:
            if atual.get("content") and base64.b64decode(atual["content"]) == arq.read_bytes():
                continue  # nada mudou
            corpo["sha"] = atual["sha"]
        status, resp = _req("PUT", url, token, corpo)
        if status not in (200, 201):
            raise RuntimeError(f"Falha ao publicar {nome} (HTTP {status}): {resp.get('message', '')}")
    print("Painel enviado pro GitHub Pages")
