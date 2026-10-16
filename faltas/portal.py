"""Acesso ao portal com navegador real (Playwright).

O login tem reCAPTCHA invisível do Google, então não dá pra fazer um POST
direto. O script abre o Chromium, preenche usuário e senha e clica em
"enviar" como uma pessoa faria. Se o Google mostrar um desafio de imagem,
o script para e avisa (não tenta resolver captcha).
"""
import re
import time

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

from . import parser

BASE = "https://www.univille.edu.br"
URL_HOME = f"{BASE}/account/MySpace.html"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


class ErroLogin(Exception):
    pass


class DesafioCaptcha(ErroLogin):
    pass


def _decodificar(resposta):
    corpo = resposta.body()
    tipo = resposta.headers.get("content-type", "")
    m = re.search(r"charset=([\w-]+)", tipo)
    charset = (m.group(1) if m else "windows-1252").lower()
    if charset in ("iso-8859-1", "latin-1"):
        charset = "windows-1252"  # o portal declara latin-1 mas usa cp1252
    return corpo.decode(charset, errors="replace")


class Portal:
    def __init__(self, usuario, senha, headless=True):
        self.usuario = usuario
        self.senha = senha
        self.headless = headless

    def __enter__(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._ctx = self._browser.new_context(
            user_agent=USER_AGENT, locale="pt-BR", timezone_id="America/Sao_Paulo"
        )
        self.page = self._ctx.new_page()
        return self

    def __exit__(self, *exc):
        self._browser.close()
        self._pw.stop()

    def get(self, caminho):
        url = caminho if caminho.startswith("http") else BASE + caminho
        for tentativa in range(3):
            try:
                resp = self._ctx.request.get(url, timeout=45_000)
                if resp.ok:
                    return _decodificar(resp)
                erro = f"HTTP {resp.status}"
            except Exception as e:  # rede instável no runner
                erro = str(e)
            time.sleep(3 * (tentativa + 1))
        raise RuntimeError(f"Falha ao abrir {url}: {erro}")

    def login(self):
        p = self.page
        p.goto(URL_HOME, wait_until="domcontentloaded", timeout=60_000)
        if not p.locator("#loginForm").count():
            return  # já logado

        p.fill("#login", self.usuario)
        p.fill("#password", self.senha)
        p.wait_for_timeout(1500)  # deixa o script do reCAPTCHA carregar
        p.click("#loginForm input[type=submit]")

        prazo = time.time() + 60
        while time.time() < prazo:
            if p.locator(".item-community").count() or "Meu Espa" in p.title():
                return
            # desafio visível do reCAPTCHA (janela com imagens)
            desafio = p.locator("iframe[src*='recaptcha/api2/bframe']")
            if desafio.count() and desafio.first.is_visible():
                raise DesafioCaptcha(
                    "O Google pediu um desafio de imagem no login (reCAPTCHA). "
                    "Isso costuma acontecer com IPs de servidor; tente de novo mais tarde "
                    "ou rode o monitor no seu computador (README)."
                )
            p.wait_for_timeout(1000)

        html = p.content()
        if parser.tem_formulario_login(html):
            raise ErroLogin("Login não concluído: confira UNIVILLE_USUARIO e UNIVILLE_SENHA")
        raise ErroLogin("Login demorou demais para responder")

    def home(self):
        html = self.get(URL_HOME)
        if parser.tem_formulario_login(html):
            raise ErroLogin("Sessão perdida logo após o login")
        return html

    def professores(self, slug):
        return parser.ler_professores(self.get(f"/community/{slug}/GradeBook.html?action=student"))

    def frequencia(self, slug, cod_professor):
        url = f"/community/{slug}/GradeBook.html?action=studentPresence&codeTeacher={cod_professor}"
        return url, parser.ler_frequencia(self.get(url))
