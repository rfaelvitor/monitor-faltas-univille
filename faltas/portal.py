"""Acesso ao portal com navegador real (Playwright).

O login tem reCAPTCHA invisível do Google, então não dá pra fazer um POST
direto. O script abre o Chromium, preenche usuário e senha e clica em
"enviar" como uma pessoa faria. Se o Google mostrar um desafio de imagem,
o script para e avisa (não tenta resolver captcha).
"""
import re
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

from . import parser

BASE = "https://www.univille.edu.br"
URL_HOME = f"{BASE}/account/MySpace.html"


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
    def __init__(self, usuario, senha, headless=True, espera_captcha=0, perfil=None):
        self.perfil = perfil
        self.usuario = usuario
        self.senha = senha
        self.headless = headless
        self.espera_captcha = espera_captcha

    def __enter__(self):
        self._pw = sync_playwright().start()
        opcoes = dict(locale="pt-BR", timezone_id="America/Sao_Paulo")
        if self.perfil:
            # perfil persistente: guarda cookies e histórico entre execuções, como um navegador de uso normal.
            # Reaproveita a sessão do portal quando ainda vale e deixa o Google menos desconfiado
            pasta = Path(self.perfil).expanduser()
            pasta.mkdir(parents=True, exist_ok=True)
            self._ctx = self._pw.chromium.launch_persistent_context(str(pasta), headless=self.headless, **opcoes)
            self._browser = None
        else:
            self._browser = self._pw.chromium.launch(headless=self.headless)
            self._ctx = self._browser.new_context(**opcoes)
        self.page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        return self

    def __exit__(self, *exc):
        (self._browser or self._ctx).close()
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

        desafio_apareceu = False
        prazo = time.time() + 60
        while time.time() < prazo:
            try:
                if p.locator(".item-community").count() or "Meu Espa" in p.title():
                    return
                if not desafio_apareceu and self._desafio_na_tela():
                    desafio_apareceu = True
                    if self.espera_captcha:
                        # não resolve nada sozinho: só dá tempo de a pessoa resolver na janela
                        print(f"Desafio de imagens na tela, esperando até {self.espera_captcha}s alguém resolver")
                        p.bring_to_front()
                        prazo = time.time() + self.espera_captcha
            except Exception:
                pass  # página trocando no meio da checagem
            p.wait_for_timeout(1000)

        print(f"Login parado em: {p.title()!r} (desafio visível: {desafio_apareceu})")
        if desafio_apareceu:
            raise DesafioCaptcha(
                "O Google pediu um desafio de imagem no login (reCAPTCHA). "
                "Isso costuma acontecer com IPs de servidor; tente de novo mais tarde "
                "ou rode o monitor no seu computador (README)."
            )
        if parser.tem_formulario_login(p.content()):
            raise ErroLogin("Login não concluído: confira UNIVILLE_USUARIO e UNIVILLE_SENHA")
        raise ErroLogin("Login demorou demais para responder")

    def _desafio_na_tela(self):
        # o iframe do desafio sempre existe, escondido fora da tela; só conta se o Google mostrar
        return self.page.evaluate(
            """() => [...document.querySelectorAll("iframe[src*='recaptcha/api2/bframe']")].some(f => {
                let el = f;
                while (el && el !== document.body) {
                    const s = getComputedStyle(el);
                    if (s.visibility === 'hidden' || s.display === 'none' || parseFloat(s.opacity) === 0) return false;
                    el = el.parentElement;
                }
                const r = f.getBoundingClientRect();
                return r.width > 50 && r.height > 50 && r.bottom > 0 && r.top < innerHeight;
            })"""
        )

    def home(self):
        # a lista de disciplinas da home é montada por JavaScript, então lê a página renderizada
        p = self.page
        if not ("Meu Espa" in p.title() or p.locator(".item-community").count()):
            p.goto(URL_HOME, wait_until="domcontentloaded", timeout=60_000)
        try:
            p.wait_for_selector(".item-community", timeout=30_000)
        except PWTimeout:
            pass
        html = p.content()
        if parser.tem_formulario_login(html):
            raise ErroLogin("Sessão perdida logo após o login")
        if ".item-community" not in html and "item-community" not in html:
            print(f"Home sem disciplinas: título {p.title()!r}, {len(html)} bytes")
        return html

    def professores(self, slug):
        return parser.ler_professores(self.get(f"/community/{slug}/GradeBook.html?action=student"))

    def frequencia(self, slug, cod_professor):
        url = f"/community/{slug}/GradeBook.html?action=studentPresence&codeTeacher={cod_professor}"
        return url, parser.ler_frequencia(self.get(url))
