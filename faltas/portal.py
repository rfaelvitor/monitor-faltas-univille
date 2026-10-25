"""Acesso ao portal com navegador real (Playwright).

O login tem reCAPTCHA invisível do Google, então não dá pra fazer um POST
direto. O script abre o Chromium, preenche usuário e senha e clica em
"enviar" como uma pessoa faria. Se o Google mostrar um desafio de imagem,
o script para e avisa (não tenta resolver captcha).
"""
import json
import re
import time
from datetime import datetime
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
    return decodificar_bytes(resposta.body(), resposta.headers.get("content-type", ""))


def decodificar_bytes(corpo, tipo):
    m = re.search(r"charset=([\w-]+)", tipo)
    charset = (m.group(1) if m else "windows-1252").lower()
    if charset in ("iso-8859-1", "latin-1"):
        charset = "windows-1252"  # o portal declara latin-1 mas usa cp1252
    return corpo.decode(charset, errors="replace")


class Portal:
    def __init__(self, usuario, senha, headless=True, espera_captcha=0, perfil=None, sessao=None, navegador="chromium"):
        self.navegador = navegador
        self.perfil = perfil
        # arquivo com o cookie de sessão do portal: tenta reaproveitar o login do dia anterior
        self.sessao = Path(sessao).expanduser() if sessao else None
        self._sessao_anterior = None
        self._login_em = None
        self.logado = False
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
            self._ctx = getattr(self._pw, self.navegador).launch_persistent_context(str(pasta), headless=self.headless, **opcoes)
            self._browser = None
        else:
            self._browser = getattr(self._pw, self.navegador).launch(headless=self.headless)
            self._ctx = self._browser.new_context(**opcoes)
        self.page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        self._carregar_sessao()
        return self

    def __exit__(self, *exc):
        if self.logado:
            self._salvar_sessao()
        (self._browser or self._ctx).close()
        self._pw.stop()

    def _carregar_sessao(self):
        if not self.sessao or not self.sessao.exists():
            return
        try:
            dados = json.loads(self.sessao.read_text(encoding="utf-8"))
            self._ctx.add_cookies(dados["cookies"])
            self._sessao_anterior = dados
        except Exception as e:  # arquivo corrompido não pode travar o login normal
            print(f"Sessão salva ignorada: {e}")

    def _salvar_sessao(self):
        if not self.sessao:
            return
        try:
            cookies = [c for c in self._ctx.cookies() if c["domain"].endswith("univille.edu.br")]
            agora = time.time()
            dados = {"salvo_em": agora, "login_em": self._login_em or agora, "cookies": cookies}
            self.sessao.parent.mkdir(parents=True, exist_ok=True)
            self.sessao.write_text(json.dumps(dados), encoding="utf-8")
        except Exception as e:
            print(f"Não consegui salvar a sessão: {e}")

    def _registrar_teste(self, resultado):
        # uma linha por execução, pra ver depois em quanto tempo a sessão do portal deixa de valer
        if not self.sessao:
            return
        ant = self._sessao_anterior
        if ant:
            desde_login = (time.time() - ant.get("login_em", ant["salvo_em"])) / 3600
            desde_uso = (time.time() - ant["salvo_em"]) / 3600
            idade = f"último login há {desde_login:.1f}h, último uso há {desde_uso:.1f}h"
        else:
            idade = "sem sessão salva"
        linha = f"{datetime.now():%Y-%m-%d %H:%M} | {resultado} | {idade}"
        print(f"Sessão: {linha}")
        try:
            with open(self.sessao.with_name("sessao-teste.log"), "a", encoding="utf-8") as f:
                f.write(linha + "\n")
        except Exception:
            pass

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
            # já logado: o cookie salvo ainda valia
            self._login_em = (self._sessao_anterior or {}).get("login_em")
            self.logado = True
            self._registrar_teste("sessão reaproveitada, sem login" if self._sessao_anterior else "já estava logado")
            return
        if self._sessao_anterior:
            self._registrar_teste("sessão salva expirou, login normal")

        p.fill("#login", self.usuario)
        p.fill("#password", self.senha)
        p.wait_for_timeout(1500)  # deixa o script do reCAPTCHA carregar
        p.click("#loginForm input[type=submit]")

        desafio_apareceu = False
        prazo = time.time() + 60
        while time.time() < prazo:
            try:
                if p.locator(".item-community").count() or "Meu Espa" in p.title():
                    self._login_em = time.time()
                    self.logado = True
                    if desafio_apareceu:
                        print("Login feito depois do desafio de imagens")
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
                "O Google pediu o desafio de imagens no login (reCAPTCHA) e ninguém resolveu a tempo. "
                "Rode o monitor de novo quando estiver no computador e resolva o desafio na janela do navegador."
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

    def trabalhos(self, slug):
        html = self.get(f"/community/{slug}/Homework.html")
        if parser.tem_formulario_login(html):
            raise ErroLogin("Sessão perdida ao abrir os trabalhos")
        return parser.ler_trabalhos(html)
