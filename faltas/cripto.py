"""Criptografia dos dados do painel.

O repositório é público, então o JSON com as faltas vai pro GitHub Pages
cifrado (AES-GCM, chave derivada da SENHA_PAINEL com PBKDF2). A página
decifra no navegador com a WebCrypto, usando os mesmos parâmetros.
"""
import base64
import json
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITERACOES = 250_000


def _chave(senha, sal, iteracoes):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=sal, iterations=iteracoes)
    return kdf.derive(senha.encode("utf-8"))


def cifrar(dados, senha):
    sal = os.urandom(16)
    iv = os.urandom(12)
    texto = json.dumps(dados, ensure_ascii=False).encode("utf-8")
    ct = AESGCM(_chave(senha, sal, ITERACOES)).encrypt(iv, texto, None)
    b64 = lambda b: base64.b64encode(b).decode("ascii")
    return {"v": 1, "iter": ITERACOES, "sal": b64(sal), "iv": b64(iv), "dados": b64(ct)}


def decifrar(pacote, senha):
    d = lambda k: base64.b64decode(pacote[k])
    chave = _chave(senha, d("sal"), int(pacote["iter"]))
    texto = AESGCM(chave).decrypt(d("iv"), d("dados"), None)
    return json.loads(texto)
