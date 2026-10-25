"""Ponto de entrada: python -m faltas"""
import json
import os
import shutil
import sys
import traceback
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import cripto, email_alerta, parser, publicar_github, regras
from .config import Config
from .portal import Portal

FUSO = ZoneInfo("America/Sao_Paulo")
RAIZ = Path(__file__).resolve().parent.parent
MODELO_PAINEL = RAIZ / "painel" / "index.html"


def carregar_estado_anterior(cfg):
    """Busca o último resultado: primeiro no disco (uso local), depois no painel publicado."""
    local = Path(cfg.pasta_saida) / "data.enc.json"
    local_aberto = Path(cfg.pasta_saida) / "data.json"
    pacote = None
    if cfg.senha_painel and local.exists():
        pacote = json.loads(local.read_text("utf-8"))
    elif not cfg.senha_painel and local_aberto.exists():
        return json.loads(local_aberto.read_text("utf-8"))
    elif cfg.url_painel:
        nome = "data.enc.json" if cfg.senha_painel else "data.json"
        url = cfg.url_painel.rstrip("/") + "/" + nome
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                pacote = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            print(f"Sem estado anterior publicado ({type(e).__name__}), tratando como primeira execução")
            return None
        if not cfg.senha_painel:
            return pacote
    if pacote is None:
        return None
    try:
        return cripto.decifrar(pacote, cfg.senha_painel)
    except Exception:
        print("Não consegui decifrar o estado anterior (SENHA_PAINEL mudou?), começando do zero")
        return None


def coletar(cfg):
    with Portal(cfg.usuario, cfg.senha, headless=cfg.headless, espera_captcha=cfg.espera_captcha,
                perfil=cfg.perfil, sessao=cfg.sessao, navegador=cfg.navegador) as portal:
        portal.login()
        disciplinas = parser.filtrar_semestre(parser.ler_disciplinas(portal.home()), cfg.semestre)
        if not disciplinas:
            raise RuntimeError("Nenhuma disciplina encontrada na home (layout mudou?)")

        resultado = []
        trabalhos = []
        for d in disciplinas:
            try:
                for t in portal.trabalhos(d["codigo"]):
                    trabalhos.append({**t, "codigo_disciplina": d["codigo"], "sigla": d["sigla"], "disciplina": d["nome"]})
            except Exception as e:
                # trabalhos são extra: se falhar numa disciplina, as faltas seguem
                print(f"Não consegui ler os trabalhos de uma disciplina ({type(e).__name__})")
            melhor = None
            for prof in portal.professores(d["codigo"]):
                url, freq = portal.frequencia(d["codigo"], prof["codigo"])
                total = freq["b1"]["faltas"] + freq["b2"]["faltas"]
                tem_dados = freq["b1"]["aulas"] or freq["b2"]["aulas"]
                candidato = {"professor": prof, "url": url, "freq": freq, "total": total, "tem_dados": bool(tem_dados)}
                # vários professores: fica com o maior total (pior caso)
                if melhor is None or (candidato["tem_dados"], total) > (melhor["tem_dados"], melhor["total"]):
                    melhor = candidato

            limite = cfg.limite_de(d["sigla"])
            if melhor is None:
                item = {**d, "limite": limite, "total": 0, "sem_dados": True, "url": None,
                        "docente": "", "b1": parser._bimestre_vazio(), "b2": parser._bimestre_vazio()}
            else:
                docente = melhor["freq"]["b1"]["docente"] or melhor["freq"]["b2"]["docente"] or melhor["professor"]["nome"]
                item = {**d, "limite": limite, "total": melhor["total"], "sem_dados": not melhor["tem_dados"],
                        "url": "https://www.univille.edu.br" + melhor["url"], "docente": docente,
                        "b1": melhor["freq"]["b1"], "b2": melhor["freq"]["b2"]}
            item["status"] = regras.status_de(item["total"], limite, cfg.niveis)
            item["margem"] = regras.margem(item["total"], limite)
            resultado.append(item)

    ordem = ["reprovado", "limite", "alerta", "atencao", "ok"]
    resultado.sort(key=lambda x: (ordem.index(x["status"]), -x["total"], x["nome"]))
    return resultado, trabalhos


def atualizar_historico(anterior, disciplinas, hoje):
    historico = list((anterior or {}).get("historico", []))
    ultimos = {}
    for h in historico:
        ultimos[h["codigo"]] = h["total"]
    for d in disciplinas:
        if ultimos.get(d["codigo"]) != d["total"]:
            historico.append({"data": hoje, "codigo": d["codigo"], "sigla": d["sigla"], "total": d["total"]})
    return historico[-500:]


def publicar(cfg, dados):
    saida = Path(cfg.pasta_saida)
    saida.mkdir(parents=True, exist_ok=True)
    shutil.copy(MODELO_PAINEL, saida / "index.html")
    if cfg.senha_painel:
        (saida / "data.enc.json").write_text(json.dumps(cripto.cifrar(dados, cfg.senha_painel)), "utf-8")
        (saida / "data.json").unlink(missing_ok=True)
    else:
        print("AVISO: SENHA_PAINEL não definida, o painel vai ser publicado SEM criptografia")
        (saida / "data.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1), "utf-8")
        (saida / "data.enc.json").unlink(missing_ok=True)


def resumo_log(cfg, disciplinas):
    contagem = {}
    for d in disciplinas:
        contagem[d["status"]] = contagem.get(d["status"], 0) + 1
    print(f"{len(disciplinas)} disciplinas verificadas: " + ", ".join(f"{k}={v}" for k, v in contagem.items()))
    if cfg.log_detalhado:
        for d in disciplinas:
            print(f"  {d['sigla']:<10} {d['b1']['faltas']:>3} + {d['b2']['faltas']:>3} = {d['total']:>3}/{d['limite']}  {d['status']}")


def ja_verificado_hoje(anterior, agora):
    try:
        return datetime.fromisoformat(anterior["atualizado_em"]).astimezone(FUSO).date() == agora.date()
    except Exception:
        return False


def executar():
    """Roda a verificação. Devolve False se pulou (já tinha rodado hoje)."""
    cfg = Config.carregar()
    agora = datetime.now(FUSO)
    anterior = carregar_estado_anterior(cfg)

    if cfg.uma_vez_por_dia and not cfg.forcar and anterior and ja_verificado_hoje(anterior, agora):
        print("Já verificado hoje, nada a fazer")
        return False

    disciplinas, trabalhos = coletar(cfg)
    semestre = disciplinas[0]["semestre"] if disciplinas else None
    resumo_log(cfg, disciplinas)

    enviados = dict((anterior or {}).get("alertas_enviados", {}))
    primeira_vez = anterior is None or (anterior.get("semestre") != semestre)
    novos, enviados_novo = regras.calcular_alertas(disciplinas, enviados, cfg.niveis)

    avisados_trab = None if primeira_vez else (anterior or {}).get("trabalhos_avisados")
    avisos_trab, avisados_trab_novo = regras.calcular_avisos_trabalhos(trabalhos, avisados_trab, agora)
    pendentes = regras.pendentes(trabalhos, agora)
    print(f"{len(trabalhos)} trabalhos lidos, {len(pendentes)} pendentes, {len(avisos_trab)} aviso(s) novo(s)")

    if primeira_vez:
        assunto, corpo = email_alerta.montar_boas_vindas(disciplinas, cfg.url_painel, pendentes)
        ok = email_alerta.enviar(cfg, assunto, corpo)
        print("Primeira execução do semestre: resumo inicial" + (" enviado" if ok else " não enviado"))
    elif novos or avisos_trab:
        assunto, corpo = email_alerta.montar_alerta(novos, disciplinas, cfg.url_painel, avisos_trab, pendentes)
        ok = email_alerta.enviar(cfg, assunto, corpo)
        print(f"{len(novos)} alerta(s) de falta, {len(avisos_trab)} de trabalho")
        if not ok and cfg.email_configurado:
            enviados_novo = enviados  # tenta de novo na próxima
            avisados_trab_novo = avisados_trab
    else:
        print("Nenhum nível novo atingido")

    dados = {
        "versao": 1,
        "atualizado_em": agora.isoformat(timespec="minutes"),
        "semestre": semestre,
        "niveis": cfg.niveis,
        "limite_padrao": cfg.limite,
        "disciplinas": disciplinas,
        "alertas_enviados": enviados_novo,
        "trabalhos": trabalhos,
        "trabalhos_avisados": avisados_trab_novo,
        "historico": atualizar_historico(None if primeira_vez else anterior, disciplinas, agora.date().isoformat()),
    }
    publicar(cfg, dados)
    print("Painel gerado em", cfg.pasta_saida)
    # fora do GitHub Actions o próprio script manda o painel pro Pages
    if cfg.github_token and cfg.github_repo and not os.environ.get("GITHUB_ACTIONS"):
        try:
            publicar_github.enviar(cfg.github_repo, cfg.github_token, cfg.pasta_saida)
        except Exception as e:
            print(f"Não consegui publicar o painel: {e}")
    return True


def _saida_github(nome, valor):
    arq = os.environ.get("GITHUB_OUTPUT")
    if arq:
        with open(arq, "a", encoding="utf-8") as f:
            f.write(f"{nome}={valor}\n")


def _pode_avisar_erro_hoje():
    """No máximo um e-mail de erro por dia (o workflow pode tentar de hora em hora)."""
    marca = Path.home() / ".monitor-faltas" / "ultimo-erro.txt"
    hoje = datetime.now(FUSO).date().isoformat()
    try:
        if marca.read_text().strip() == hoje:
            return False
    except OSError:
        pass
    try:
        marca.parent.mkdir(parents=True, exist_ok=True)
        marca.write_text(hoje)
    except OSError:
        pass
    return True


def main():
    try:
        rodou = executar()
        _saida_github("rodou", "true" if rodou else "false")
    except SystemExit:
        raise
    except Exception as e:
        traceback.print_exc()
        _saida_github("rodou", "false")
        try:
            if _pode_avisar_erro_hoje():
                cfg = Config.carregar()
                assunto, corpo = email_alerta.montar_erro(f"{type(e).__name__}: {e}")
                email_alerta.enviar(cfg, assunto, corpo)
            else:
                print("Erro já avisado por e-mail hoje")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
