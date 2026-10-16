import os
from dataclasses import dataclass, field
from pathlib import Path


def _carregar_dotenv(caminho=".env"):
    # pra rodar local sem precisar de lib extra; não sobrescreve o que já está no ambiente
    p = Path(caminho)
    if not p.exists():
        return
    for linha in p.read_text("utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        k, v = linha.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_carregar_dotenv()


def _env(nome, padrao=None, obrigatorio=False):
    valor = os.environ.get(nome, "").strip()
    if not valor:
        if obrigatorio:
            raise SystemExit(f"Variável de ambiente {nome} não definida (veja o README)")
        return padrao
    return valor


def _lista_int(texto):
    return sorted({int(x) for x in texto.replace(";", ",").split(",") if x.strip()})


def _dict_int(texto):
    # "FDIA=20, EIXO-III=20" -> {"FDIA": 20, "EIXO-III": 20}
    saida = {}
    for parte in texto.replace(";", ",").split(","):
        if "=" in parte:
            k, v = parte.split("=", 1)
            saida[k.strip().upper()] = int(v)
    return saida


@dataclass
class Config:
    usuario: str
    senha: str
    limite: int = 18
    niveis: list = field(default_factory=lambda: [10, 12, 14, 16, 18])
    semestre: str | None = None
    senha_painel: str | None = None
    url_painel: str | None = None
    gmail_usuario: str | None = None
    gmail_senha_app: str | None = None
    email_destino: str | None = None
    limites_especificos: dict = field(default_factory=dict)
    headless: bool = True
    log_detalhado: bool = False
    pasta_saida: str = "site"

    @classmethod
    def carregar(cls):
        gmail = _env("GMAIL_USUARIO")
        return cls(
            usuario=_env("UNIVILLE_USUARIO", obrigatorio=True),
            senha=_env("UNIVILLE_SENHA", obrigatorio=True),
            limite=int(_env("LIMITE_FALTAS", "18")),
            niveis=_lista_int(_env("NIVEIS_ALERTA", "10,12,14,16,18")),
            semestre=_env("SEMESTRE"),
            senha_painel=_env("SENHA_PAINEL"),
            url_painel=_env("URL_PAINEL"),
            gmail_usuario=gmail,
            gmail_senha_app=_env("GMAIL_SENHA_APP"),
            email_destino=_env("EMAIL_DESTINO", gmail),
            limites_especificos=_dict_int(_env("LIMITES_ESPECIFICOS", "")),
            headless=_env("HEADLESS", "1") != "0",
            log_detalhado=_env("LOG_DETALHADO", "0") == "1",
            pasta_saida=_env("PASTA_SAIDA", "site"),
        )

    def limite_de(self, sigla):
        return self.limites_especificos.get(sigla.upper(), self.limite)

    @property
    def email_configurado(self):
        return bool(self.gmail_usuario and self.gmail_senha_app and self.email_destino)
