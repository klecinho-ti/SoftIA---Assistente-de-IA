# ============================================================
# SOFTIA - GERAÇÃO DE CÓDIGO
# ============================================================
#
# Portado do JARVIS-CyberBot (actions/code_helper.py) em 19/09/2026,
# a pedido do Klecio: mesma ideia (o SOFTIA escreve um código a partir
# de uma descrição e salva na Área de Trabalho), mas falando direto
# com a API do Gemini — sem VPS, sem Codex, só a chave do próprio
# usuário, igual ao resto do SOFTIA.
#
# ============================================================

# Path facilita localizar e montar caminhos de arquivo.
from pathlib import Path
# re remove as cercas de markdown (```) que o modelo às vezes
# coloca em volta do código, mesmo quando instruído a não fazer isso.
import re

# Cliente oficial da API do Gemini — o mesmo SDK usado no resto do SOFTIA.
from google import genai

# Chave de API do usuário, lida do .env ou do config.json salvo
# pela janela de Configurações.
from core.config import GEMINI_API_KEY
# Reaproveita a função que já localiza a Área de Trabalho do usuário
# (com ou sem OneDrive) e a que limpa nomes de arquivo inválidos.
from actions.file_actions import area_de_trabalho, limpar_nome


# Modelo usado para gerar código. Mesmo escolhido no resto do SOFTIA
# para tarefas de texto (fora da conversa por voz, que usa o modelo Live).
MODELO_CODIGO = "gemini-3.6-flash"

# Extensão de arquivo para cada linguagem que o usuário pode pedir.
_EXTENSAO_POR_LINGUAGEM = {
    "python": ".py",
    "javascript": ".js",
    "typescript": ".ts",
    "html": ".html",
    "css": ".css",
    "java": ".java",
    "c++": ".cpp",
    "cpp": ".cpp",
    "c": ".c",
    "bash": ".sh",
    "shell": ".sh",
    "powershell": ".ps1",
    "sql": ".sql",
    "json": ".json",
    "rust": ".rs",
    "go": ".go",
}


# Cria o cliente do Gemini sob demanda, com a chave atual do usuário.
# Criar aqui (em vez de uma vez só no início do programa) garante que
# uma chave trocada na janela de Configurações já valha na próxima vez
# que o SOFTIA escrever um código, sem precisar reiniciar.
def _cliente_gemini():
    return genai.Client(
        api_key=GEMINI_API_KEY
    )


# Remove as cercas de markdown (```python ... ```) que às vezes
# aparecem em volta do código, mesmo quando o modelo é instruído
# a devolver só o código puro.
def _limpar_codigo(texto):
    texto = texto.strip()
    texto = re.sub(r"^```[a-zA-Z]*\n?", "", texto)
    texto = re.sub(r"\n?```$", "", texto)
    return texto.strip()


# Monta um caminho de arquivo que ainda não existe, acrescentando
# um número quando já houver um arquivo com o mesmo nome. Isso segue
# o mesmo princípio do resto do SOFTIA: nunca sobrescrever nada.
def _caminho_disponivel(pasta, nome_base, extensao):
    caminho = pasta / f"{nome_base}{extensao}"

    contador = 2
    while caminho.exists():
        caminho = pasta / f"{nome_base} ({contador}){extensao}"
        contador += 1

    return caminho


# Gera código a partir de uma descrição em linguagem natural e salva
# o resultado em um novo arquivo na Área de Trabalho.
#
# descricao    : o que o código deve fazer, nas palavras do usuário.
# linguagem    : linguagem de programação pedida (padrão: python).
# nome_arquivo : nome desejado para o arquivo, sem extensão (opcional).
def escrever_codigo(descricao, linguagem="python", nome_arquivo=""):
    if not descricao:
        return "Preciso de uma descrição do que o código deve fazer."

    linguagem = (linguagem or "python").strip().lower()

    prompt = f"""Você é um desenvolvedor {linguagem} experiente.
Escreva um código {linguagem} limpo, funcional e bem comentado para a
descrição abaixo.

Regras:
- Devolva SOMENTE o código. Sem explicação, sem markdown, sem crases.
- Acrescente comentários úteis no meio do código.
- Trate erros e casos de borda corretamente.
- Use boas práticas modernas da linguagem.

Descrição: {descricao}

Código:"""

    try:
        cliente = _cliente_gemini()

        resposta = cliente.models.generate_content(
            model=MODELO_CODIGO,
            contents=prompt,
        )

        codigo = _limpar_codigo(resposta.text)

    except Exception as erro:
        return f"Não consegui gerar o código: {erro}"

    extensao = _EXTENSAO_POR_LINGUAGEM.get(
        linguagem,
        ".py",
    )

    nome_base = limpar_nome(nome_arquivo) or "codigo_softia"

    try:
        pasta = area_de_trabalho()
        caminho = _caminho_disponivel(pasta, nome_base, extensao)
        caminho.write_text(codigo, encoding="utf-8")

    except Exception as erro:
        return f"O código foi gerado, mas não pôde ser salvo: {erro}"

    linhas = codigo.splitlines()
    previa = "\n".join(linhas[:10])
    if len(linhas) > 10:
        previa += f"\n... (mais {len(linhas) - 10} linhas)"

    return (
        f"Código escrito e salvo em: {caminho}\n\n"
        f"Prévia:\n{previa}"
    )
