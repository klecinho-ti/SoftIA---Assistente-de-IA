# ============================================================
# SOFTIA - TAREFA POR COMANDO (PowerShell escrito pela IA)
# ============================================================
#
# Portado do JARVIS-CyberBot (actions/tarefa_comando.py) em
# 19/09/2026, a pedido do Klecio: a IA escreve UM comando de
# PowerShell para a tarefa pedida, e o comando roda aqui, na
# máquina do usuário — sem VPS, sem Codex, com a própria API do
# Gemini escrevendo o comando.
#
# Por que este jeito em vez de uma função para cada tarefa:
# um comando de PowerShell alcança qualquer coisa que o Windows
# faz (ver espaço em disco, compactar pasta, listar processos,
# etc.), sem precisar programar uma função nova para cada pedido.
#
# O FREIO (continua valendo, copiado do JARVIS sem mudança):
# - lista de padrões PROIBIDOS por texto (formatar, apagar disco,
#   desligar o PC, mexer no registro, desligar antivírus...);
# - só PowerShell, sem Invoke-Expression de texto vindo de fora;
# - prazo de 90s: comando travado não trava o SOFTIA;
# - o freio é por PADRÃO (lista de proibidos), não por lista de
#   permitidos — de propósito, para não travar tarefas legítimas
#   que ninguém previu. Por isso o comando aparece sempre na
#   resposta: dá para auditar o que rodou.
# ============================================================

import re
import subprocess

from google import genai

from core.config import GEMINI_API_KEY


PRAZO_S = 90

# Modelo usado para escrever o comando. Mesmo escolhido no resto
# do SOFTIA para tarefas de texto fora da conversa por voz.
MODELO_COMANDO = "gemini-3.6-flash"

# Padrões que NUNCA rodam, por mais que o modelo insista. Cada um
# existe porque o estrago seria irreversível ou inutilizaria a
# máquina do usuário.
PROIBIDOS = [
    # CUIDADO COM \bformat\b SOLTO: ele bate em Format-Table e
    # Format-List, que são inofensivos e comuns. Por isso o padrão
    # exige "format-volume" ou "format" seguido de letra de disco.
    (r"\bformat-volume\b|\bformat\s+[a-z]:", "formatar disco"),
    (r"\bremove-item\b[^|]*\b[a-z]:\\\s*(-recurse|$)", "apagar a raiz de um disco"),
    (r"\bremove-item\b[^|]*(windows|system32|program files)", "apagar pasta do sistema"),
    (r"\brd\b\s+/s|\brmdir\b\s+/s.*\b[a-z]:\\?\s*$", "apagar disco inteiro"),
    (r"\bdel\b\s+/[sf].*\b[a-z]:\\\*", "apagar disco inteiro"),
    (r"\bstop-computer\b|\bshutdown\b|\brestart-computer\b", "desligar ou reiniciar o PC"),
    (r"\bclear-disk\b|\bdiskpart\b", "mexer nas partições"),
    (r"\bset-itemproperty\b[^|]*hklm:", "alterar o registro do sistema"),
    (r"\bnew-itemproperty\b[^|]*hklm:", "alterar o registro do sistema"),
    (r"\breg\b\s+(delete|add)\b", "alterar o registro do sistema"),
    (r"\binvoke-expression\b|\biex\b\s*\(", "executar texto como código"),
    (r"\b(irm|iwr|invoke-webrequest|curl|wget)\b[^|]*\|\s*(iex|invoke-expression)",
     "baixar da internet e executar"),
    (r"\bstart-process\b[^|]*\.(exe|msi|bat|cmd)\b[^|]*-verb\s+runas", "executar como administrador"),
    (r"\bnet\b\s+user\b.*\b/add\b", "criar usuário do Windows"),
    (r"\bdisable-\w*(firewall|defender)", "desligar a proteção do Windows"),
    (r"\bset-mppreference\b", "desligar o antivírus"),
    (r"\bcipher\b\s+/w", "apagar espaço livre de forma irreversível"),
    (r"\bvssadmin\b.*delete", "apagar os pontos de restauração"),
    (r"\bstop-process\b[^|]*\b(explorer|winlogon|csrss|lsass|services|softia|pythonw)\b",
     "encerrar processo crítico do sistema ou o próprio SOFTIA"),
]


# Diz se o comando pode rodar. Devolve (liberado, motivo).
def revisar(comando):
    texto = " ".join(str(comando or "").split()).lower()

    if not texto:
        return False, "comando vazio"

    if len(texto) > 4000:
        return False, "comando longo demais"

    for padrao, motivo in PROIBIDOS:
        if re.search(padrao, texto):
            return False, motivo

    return True, ""


# Tira cerca de código e conversa fiada, deixando só o comando.
def _limpar_resposta(bruto):
    texto = str(bruto or "").strip()

    correspondencia = re.search(
        r"```(?:powershell|ps1|cmd|bat)?\s*(.+?)```",
        texto,
        re.S | re.I,
    )

    if correspondencia:
        texto = correspondencia.group(1)

    linhas = [l.rstrip() for l in texto.splitlines()]

    uteis = [
        l for l in linhas
        if l.strip() and not l.strip().startswith("#")
    ]

    if not uteis:
        return ""

    # SÓ A PRIMEIRA LINHA por padrão: se o modelo emendar uma frase
    # de explicação depois do comando, o PowerShell engasga inteiro.
    # Só continua nas linhas seguintes quando a linha atual
    # claramente pede emenda (termina com | ` ; { ( , ou a próxima
    # começa com | } )).
    comando = [uteis[0]]

    for anterior, atual in zip(uteis, uteis[1:]):
        emenda = anterior.rstrip().endswith(("|", "`", ";", "{", "(", ","))
        emenda = emenda or atual.lstrip().startswith(("|", "}", ")"))

        if not emenda:
            break

        comando.append(atual)

    return "\n".join(comando).strip()


# Roda o comando no PowerShell, com prazo. Devolve o que aconteceu.
def executar(comando):
    liberado, motivo = revisar(comando)

    if not liberado:
        return {
            "ok": False,
            "recusado": True,
            "motivo": motivo,
            "saida": "",
            "comando": comando,
        }

    try:
        resultado = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy", "Bypass",
                "-Command", comando,
            ],
            capture_output=True,
            text=True,
            timeout=PRAZO_S,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        saida = (resultado.stdout or "").strip()
        erro = (resultado.stderr or "").strip()

        # O PowerShell devolve código 0 mesmo tendo impresso um erro
        # não-terminante. Regra conservadora: só é falha quando não
        # veio NADA de saída e veio erro — assim um aviso de rotina
        # não derruba um comando que funcionou.
        return {
            "ok": resultado.returncode == 0 and not (erro and not saida),
            "recusado": False,
            "codigo": resultado.returncode,
            "saida": (saida or erro)[:3000],
            "comando": comando,
        }

    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "recusado": False,
            "motivo": f"passou de {PRAZO_S}s",
            "saida": "",
            "comando": comando,
        }

    except Exception as erro:
        return {
            "ok": False,
            "recusado": False,
            "motivo": f"{type(erro).__name__}: {str(erro)[:150]}",
            "saida": "",
            "comando": comando,
        }


# Instrução enviada à Gemini para escrever o comando. O nome do
# arquivo original citava o Codex; aqui quem escreve é a Gemini,
# mas as regras são as mesmas.
_PEDIDO_DE_COMANDO = (
    "Você escreve UM comando de PowerShell para Windows 11 que realize a "
    "tarefa abaixo na máquina do usuário.\n"
    "\n"
    "REGRAS:\n"
    "- Responda APENAS com o comando, sem explicação, sem cerca de código, "
    "sem comentário.\n"
    "- Um comando só. Pode usar ponto e vírgula ou pipe, mas nada de script "
    "de várias linhas com função.\n"
    "- NÃO use nada destrutivo: formatar, apagar disco, apagar pasta do "
    "Windows, desligar o PC, mexer no registro do sistema, desligar "
    "antivírus ou firewall.\n"
    "- Prefira o caminho mais simples e direto.\n"
    "- Caminhos do usuário ficam em $env:USERPROFILE (Desktop, Documents, "
    "etc).\n"
    "- Se a tarefa devolver dados, faça o comando IMPRIMIR o resultado.\n"
    "- IMPRIMA EM LINHAS ROTULADAS, uma por item, no formato 'Rótulo: "
    "valor' (ex.: Write-Output \"CPU: 10%\"). NADA de tabela, "
    "Format-Table ou Select-Object solto com várias colunas.\n"
    "- Se o pedido tiver VÁRIAS partes (CPU, memória e disco, por "
    "exemplo), o MESMO comando tem de trazer TODAS elas, cada uma na sua "
    "linha.\n"
    "- Se o destino já existir, SOBRESCREVA: use -Force no "
    "Compress-Archive, no Expand-Archive, no Copy-Item e no New-Item.\n"
    "- Crie a pasta de destino se ela não existir.\n"
    "\n"
    "TAREFA: "
)


# Pede à Gemini para escrever o comando, revisa e executa.
# Devolve uma frase pronta para o SOFTIA responder ao usuário.
#
# tarefa: o que o usuário pediu, em português, nas palavras dele.
def executar_tarefa_por_comando(tarefa):
    if not tarefa or not str(tarefa).strip():
        return "Preciso saber qual tarefa você quer que eu faça."

    try:
        cliente = genai.Client(
            api_key=GEMINI_API_KEY
        )

        resposta = cliente.models.generate_content(
            model=MODELO_COMANDO,
            contents=_PEDIDO_DE_COMANDO + str(tarefa),
        )

        comando = _limpar_resposta(resposta.text)

    except Exception as erro:
        return f"Não consegui preparar o comando: {erro}"

    if not comando:
        return "Não consegui montar um comando para essa tarefa."

    resultado = executar(comando)

    if resultado["recusado"]:
        return (
            f"Não vou executar isso: {resultado['motivo']}. "
            f"Comando que seria rodado: {resultado['comando']}"
        )

    if not resultado["ok"]:
        motivo = resultado.get("motivo") or resultado.get("saida") or "erro desconhecido"
        return f"A tarefa não deu certo: {motivo}"

    saida = resultado["saida"]

    if saida:
        return f"Feito, senhor.\n\n{saida}"

    return "Feito, senhor."
