"""Login pelo Firefox de uso normal (Selenium), usando uma cópia do perfil da pessoa.

O Firefox do Playwright começa sem histórico e o Google pede o desafio de imagens
com frequência. Com uma cópia do perfil de verdade (cookies do Google, histórico)
o teste de 25/10/2026 entrou sem captcha. Liga com NAVEGADOR=firefox-perfil.
"""
import base64
import configparser
import os
import shutil
import time
from pathlib import Path

from . import parser
from .portal import BASE, URL_HOME, DesafioCaptcha, ErroLogin, decodificar_bytes

JS_DESAFIO = """return [...document.querySelectorAll("iframe[src*='recaptcha/api2/bframe']")].some(f => {
    let el = f;
    while (el && el !== document.body) {
        const s = getComputedStyle(el);
        if (s.visibility === 'hidden' || s.display === 'none' || parseFloat(s.opacity) === 0) return false;
        el = el.parentElement;
    }
    const r = f.getBoundingClientRect();
    return r.width > 50 && r.height > 50 && r.bottom > 0 && r.top < innerHeight;
})"""

# baixa a página pelo próprio navegador (mesmos cookies) e devolve os bytes, porque o portal usa cp1252
JS_GET = """const [url, pronto] = [arguments[0], arguments[arguments.length - 1]];
fetch(url, {credentials: 'include'}).then(async r => {
    const b = new Uint8Array(await r.arrayBuffer());
    let s = '';
    for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000));
    pronto({status: r.status, tipo: r.headers.get('content-type') || '', corpo: btoa(s)});
}).catch(e => pronto({status: 0, erro: String(e)}));"""

IGNORAR = ("cache2", "startupCache", "*.lock", "parent.lock", "lock", ".parentlock",
           "crashes", "minidumps", "datareporting", "saved-telemetry-pings")
# o que importa pro Google: cookies e histórico. Atualiza a cada execução, o resto só na primeira cópia
ATUALIZAR = ("cookies.sqlite", "cookies.sqlite-wal", "places.sqlite", "places.sqlite-wal")


def perfil_padrao_firefox():
    moz = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "Mozilla" / "Firefox"
    ini = configparser.ConfigParser()
    ini.read(moz / "profiles.ini", encoding="utf-8")
    caminho = None
    for s in ini.sections():
        if s.startswith("Install") and ini[s].get("Default"):
            caminho = ini[s]["Default"]
    if not caminho:
        for s in ini.sections():
            if ini[s].get("Default") == "1" and ini[s].get("Path"):
                caminho = ini[s]["Path"]
    if not caminho:
        raise ErroLogin("Não achei o perfil do Firefox (profiles.ini). Defina PERFIL_FIREFOX_ORIGEM no .env")
    p = Path(caminho)
    return p if p.is_absolute() else moz / p


def _copiar(src, dst):
    try:
        shutil.copy2(src, dst)
    except OSError:
        pass  # arquivo travado com o Firefox aberto


def preparar_copia(origem, destino):
    origem, destino = Path(origem), Path(destino)
    if not (destino / "prefs.js").exists():
        shutil.copytree(origem, destino, ignore=shutil.ignore_patterns(*IGNORAR), copy_function=_copiar, dirs_exist_ok=True)
    else:
        for nome in ATUALIZAR:
            if (origem / nome).exists():
                _copiar(origem / nome, destino / nome)
    for nome in ("parent.lock", ".parentlock", "lock"):
        (destino / nome).unlink(missing_ok=True)


class PortalFirefox:
    def __init__(self, usuario, senha, headless=False, espera_captcha=0, perfil=None, origem=None):
        self.usuario = usuario
        self.senha = senha
        self.headless = headless
        self.espera_captcha = espera_captcha
        self.perfil = Path(perfil or "~/.monitor-faltas/perfil-firefox-real").expanduser()
        self.origem = Path(origem).expanduser() if origem else None
        self.logado = False

    def __enter__(self):
        from selenium import webdriver

        preparar_copia(self.origem or perfil_padrao_firefox(), self.perfil)
        op = webdriver.FirefoxOptions()
        op.add_argument("-profile")
        op.add_argument(str(self.perfil))
        if self.headless:
            op.add_argument("-headless")
        self.d = webdriver.Firefox(options=op)
        self.d.set_page_load_timeout(60)
        self.d.set_script_timeout(60)
        return self

    def __exit__(self, *exc):
        try:
            self.d.quit()
        except Exception:
            pass

    def _achar(self, css):
        from selenium.webdriver.common.by import By
        return self.d.find_elements(By.CSS_SELECTOR, css)

    def get(self, caminho):
        url = caminho if caminho.startswith("http") else BASE + caminho
        erro = ""
        for tentativa in range(3):
            try:
                r = self.d.execute_async_script(JS_GET, url)
                if 200 <= r.get("status", 0) < 300:
                    return decodificar_bytes(base64.b64decode(r["corpo"]), r.get("tipo", ""))
                erro = r.get("erro") or f"HTTP {r.get('status')}"
            except Exception as e:
                erro = str(e)
            time.sleep(3 * (tentativa + 1))
        raise RuntimeError(f"Falha ao abrir {url}: {erro}")

    def login(self):
        from selenium.webdriver.common.keys import Keys

        self.d.get(URL_HOME)
        time.sleep(2)
        if not self._achar("#loginForm"):
            self.logado = True
            print("Já estava logado")
            return
        time.sleep(3)  # o gerenciador de senhas do perfil preenche sozinho; espera pra limpar depois
        for css, valor in (("#login", self.usuario), ("#password", self.senha)):
            el = self._achar(css)[0]
            el.clear()
            el.send_keys(Keys.CONTROL, "a")
            el.send_keys(Keys.DELETE)
            el.send_keys(valor)
        time.sleep(1.5)
        self._achar("#loginForm input[type=submit]")[0].click()

        desafio = False
        prazo = time.time() + 60
        while time.time() < prazo:
            try:
                if self._achar(".item-community") or "Meu Espa" in self.d.title:
                    self.logado = True
                    if desafio:
                        print("Login feito depois do desafio de imagens")
                    return
                if not desafio and self.d.execute_script(JS_DESAFIO):
                    desafio = True
                    if self.espera_captcha:
                        print(f"Desafio de imagens na tela, esperando até {self.espera_captcha}s alguém resolver")
                        self.d.switch_to.window(self.d.current_window_handle)
                        prazo = time.time() + self.espera_captcha
            except Exception:
                pass
            time.sleep(1)

        print(f"Login parado em: {self.d.title!r} (desafio visível: {desafio})")
        if desafio:
            raise DesafioCaptcha(
                "O Google pediu o desafio de imagens no login (reCAPTCHA) e ninguém resolveu a tempo. "
                "Rode o monitor de novo quando estiver no computador e resolva o desafio na janela do navegador."
            )
        if parser.tem_formulario_login(self.d.page_source):
            raise ErroLogin("Login não concluído: confira UNIVILLE_USUARIO e UNIVILLE_SENHA")
        raise ErroLogin("Login demorou demais para responder")

    def home(self):
        if not ("Meu Espa" in self.d.title or self._achar(".item-community")):
            self.d.get(URL_HOME)
        fim = time.time() + 30
        while time.time() < fim and not self._achar(".item-community"):
            time.sleep(1)
        html = self.d.page_source
        if parser.tem_formulario_login(html):
            raise ErroLogin("Sessão perdida logo após o login")
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
