# Monitor de faltas da Univille

Verifica todo dia as suas faltas em cada disciplina no portal da Univille, soma 1º + 2º bimestre e avisa por e-mail quando você chega perto do limite. Também avisa dos trabalhos pendentes antes do prazo. Tudo fica num painel web que abre no celular.

Roda no seu próprio computador com Windows, pelo Agendador de Tarefas. Quando o semestre muda, ele pega as disciplinas novas sozinho.

![Painel de faltas](docs/painel.png)

## O que ele faz

- Entra no portal com a sua matrícula e senha
- Lista as disciplinas do semestre atual na home (Meu Espaço)
- Em cada disciplina:
  - abre o Diário de Classe, passa por todos os professores e lê o "Controle de Frequência / Conteúdo"
  - lê a página "Trabalhos / Atividades"
- Soma as faltas do 1º e do 2º bimestre. Se a disciplina tiver mais de um professor, considera o maior total
- Manda e-mail quando uma disciplina atinge 10, 12, 14, 16 ou 18 faltas (configurável). Um e-mail por nível, sem repetir
- Avisa de cada trabalho não entregue em até 4 momentos: quando ele aparece, 3 dias antes do prazo, 1 dia antes e, uma vez, se o prazo passar sem entrega. Trabalho com resposta enviada não gera aviso
- Publica um painel no GitHub Pages com os dados **criptografados** (só abre com a sua senha)

O limite padrão é 18 faltas: passou disso, reprova.

## Por que no seu computador e não na nuvem

O login do portal tem reCAPTCHA do Google. Em servidores (GitHub Actions e parecidos) o Google desconfia do IP e pede o desafio de imagens em toda execução, então não dá pra rodar 100% na nuvem. O script **não tenta burlar o captcha**.

No seu computador ele abre um navegador de verdade e usa sempre o mesmo perfil (`%USERPROFILE%\.monitor-faltas\perfil`). Um navegador que volta todo dia costuma ser reconhecido pelo Google e passa direto. Quando o Google ainda pedir as imagens, a janela fica aberta e você resolve; o script espera até 4 minutos e faz o resto sozinho.

A sessão do portal em si não dá pra reaproveitar de um dia pro outro: o cookie de sessão some quando o navegador fecha e expira rápido no servidor.

## Como usar (passo a passo)

Você vai precisar de Windows, uma conta no GitHub e um Gmail. Leva uns 15 minutos.

### 1. Crie a sua cópia do repositório

Clique em **Use this template → Create a new repository** (ou faça um fork). Deixe o repositório **público**, porque o GitHub Pages gratuito só funciona em repositório público. Seus dados não ficam expostos: o painel vai criptografado e matrícula e senhas ficam só no seu computador.

### 2. Gere uma senha de app no Gmail

O script manda e-mail pelo próprio Gmail. O Google exige uma "senha de app" (não é a sua senha normal):

1. Ative a verificação em duas etapas na sua conta Google, se ainda não tiver
2. Acesse <https://myaccount.google.com/apppasswords>
3. Crie uma senha com o nome "monitor faltas" e copie os 16 caracteres

### 3. Crie um token do GitHub (pra publicar o painel)

1. Acesse <https://github.com/settings/personal-access-tokens/new>
2. Nome: `monitor-faltas`. Validade: a que preferir (quando vencer, é só gerar outro e trocar no `.env`)
3. **Repository access → Only select repositories** → escolha o seu repositório
4. **Permissions → Repository permissions → Contents: Read and write**. Mais nada
5. Gere e copie o token

### 4. Rode o instalador

Abra o **PowerShell** (menu Iniciar → digite PowerShell) e cole, trocando `SEU_USUARIO/SEU_REPO`:

```powershell
$env:MONITOR_REPO="SEU_USUARIO/SEU_REPO"; irm "https://raw.githubusercontent.com/$env:MONITOR_REPO/main/windows/instalar.ps1" | iex
```

Ele pergunta matrícula, senha do portal, uma senha pro painel (você inventa), Gmail, senha de app e o token, e então:

- instala o [uv](https://docs.astral.sh/uv/), que baixa um Python portátil (não precisa instalar Python)
- baixa o código e o navegador (Chromium)
- cria a tarefa **"Monitor de faltas Univille"** no Agendador: todo dia às 8h. Se o computador estiver desligado nesse horário, roda assim que você ligar
- oferece rodar a primeira verificação na hora

Pra trocar o horário, rode o instalador de novo com `$env:MONITOR_HORARIO="19:00";` antes do comando. Rodar o instalador de novo também atualiza o código e mantém a configuração.

### 5. Ative o GitHub Pages

Depois da primeira verificação aparece um branch `painel` no repositório. Em **Settings → Pages → Build and deployment**, escolha **Source: Deploy from a branch**, branch **painel**, pasta **/ (root)**.

O painel fica em:

```
https://SEU_USUARIO.github.io/SEU_REPO/
```

Na primeira verificação chega um e-mail "Monitor ativado" com a situação de todas as disciplinas e os trabalhos pendentes.

## Uso no dia a dia

- A tarefa roda sem janela de terminal. Só o navegador aparece por cerca de um minuto, porque é nele que você resolve o desafio de imagens quando o Google pedir
- Uma verificação por dia. Pra forçar outra: `powershell -ExecutionPolicy Bypass -File %USERPROFILE%\.monitor-faltas\rodar.ps1 -Forcar`
- Log da última execução: `%USERPROFILE%\.monitor-faltas\logs\ultima-execucao.log`
- A cada execução o código é atualizado a partir do branch `main` do seu repositório
- Se der erro (senha errada, portal fora do ar, captcha não resolvido), chega no máximo um e-mail de erro por dia

## Configuração

Fica em `%USERPROFILE%\.monitor-faltas\.env` (abra com o Bloco de Notas). O instalador já preenche o principal.

| Variável | Padrão | Para que serve |
|---|---|---|
| `UNIVILLE_USUARIO` / `UNIVILLE_SENHA` | | Login do portal |
| `SENHA_PAINEL` | | Senha que abre o painel. Se trocar, o histórico antigo não abre mais |
| `GMAIL_USUARIO` / `GMAIL_SENHA_APP` | | Envio dos e-mails |
| `EMAIL_DESTINO` | o próprio Gmail | Para onde mandar os alertas |
| `GITHUB_TOKEN` / `GITHUB_REPO` | | Publicação do painel |
| `URL_PAINEL` | GitHub Pages do repo | Link que vai nos e-mails |
| `LIMITE_FALTAS` | `18` | Limite de faltas para reprovar |
| `NIVEIS_ALERTA` | `10,12,14,16,18` | Em quais totais mandar e-mail |
| `LIMITES_ESPECIFICOS` | vazio | Limite diferente por sigla, ex: `FDIA=20,EIXO-III=20` |
| `SEMESTRE` | o mais recente | Forçar um semestre, ex: `2026-2` |
| `ESPERA_CAPTCHA` | `240` | Segundos que o script espera você resolver o desafio de imagens |
| `PERFIL_NAVEGADOR` | `~/.monitor-faltas/perfil` | Pasta do perfil do navegador. `0` desliga (navegador novo a cada vez, mais captcha) |

## Rodar manualmente (qualquer sistema)

Útil pra testar ou pra quem usa Linux/Mac (aí o agendamento fica por conta do `cron`).

```bash
git clone https://github.com/SEU_USUARIO/SEU_REPO.git
cd SEU_REPO
python -m venv .venv
source .venv/bin/activate          # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env               # e preencha o .env
python -m faltas
```

O painel é gerado na pasta `site/`. Para ver: `python -m http.server -d site` e abra <http://localhost:8000>.

## Como funciona por dentro

```
Agendador de Tarefas (todo dia, ou ao ligar o PC)
   │
   ├─ rodar.vbs → rodar.ps1 (sem janela): atualiza o código e chama python -m faltas
   ├─ lê o estado anterior (painel cifrado salvo no PC) e decifra
   ├─ abre o Chromium com o perfil salvo e faz login no portal
   ├─ Meu Espaço → disciplinas do semestre
   ├─ cada disciplina → professores → Controle de Frequência
   ├─ cada disciplina → Trabalhos / Atividades
   ├─ soma faltas, calcula situação, folga e prazos dos trabalhos
   ├─ compara com o que já foi avisado → manda um e-mail só, se tiver novidade
   └─ cifra os dados e envia pro branch painel (GitHub Pages)
```

| Arquivo | Papel |
|---|---|
| `faltas/portal.py` | Login e navegação no portal com Playwright |
| `faltas/parser.py` | Leitura do HTML (disciplinas, professores, faltas, trabalhos) |
| `faltas/regras.py` | Situação de cada disciplina e quando avisar |
| `faltas/email_alerta.py` | Montagem e envio dos e-mails |
| `faltas/cripto.py` | Criptografia AES-GCM dos dados do painel |
| `faltas/publicar_github.py` | Envia o painel pro branch `painel` pela API do GitHub |
| `faltas/main.py` | Orquestra tudo |
| `painel/index.html` | Painel (decifra os dados no navegador) |
| `windows/` | Instalador e scripts do Agendador de Tarefas |
| `tests/` | Testes com HTML de exemplo (sem acessar o portal) |

Rodar os testes: `pip install -r requirements-dev.txt && python -m pytest`

## Privacidade e segurança

- Matrícula, senha do portal, senha de app do Gmail e token ficam só no `.env` do seu computador
- O token do GitHub só tem permissão de escrever arquivos no seu repositório do monitor
- O painel publicado contém só um arquivo cifrado com AES-256-GCM. Sem a `SENHA_PAINEL` não dá pra ler. Use uma senha boa
- O script só lê páginas. Não altera nada no portal

## Limitações

- **reCAPTCHA no login.** O perfil salvo reduz bastante os desafios, mas o Google ainda pode pedir as imagens de vez em quando. Se ninguém resolver em 4 minutos, a verificação do dia falha e chega um e-mail de erro
- **Computador precisa ligar.** Se o PC ficar dias desligado, não há verificação nesses dias
- **Mudança de layout.** Se a Univille mudar o portal, a leitura pode quebrar. Aí chega um e-mail de erro e é preciso ajustar o `parser.py`
- **Faltas justificadas** aparecem no painel mas não são descontadas do total, porque não está claro como o portal já as considera
- **Trabalho em equipe** só conta como entregue quando aparece resposta final enviada
- **Trabalhos antigos.** Na primeira execução, trabalhos que já venceram sem entrega entram calados, pra não chegar um e-mail com o semestre inteiro
- O limite padrão é 18 para todas as disciplinas. Se alguma tiver limite diferente, ajuste com `LIMITES_ESPECIFICOS`

## Licença

MIT. Projeto independente, sem vínculo oficial com a Univille.
