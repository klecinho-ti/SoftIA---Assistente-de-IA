# [Klecio] json converte textos JSON em dicionários Python.
# [Klecio] Aqui ele interpreta a resposta estruturada devolvida pelo Gemini.
import json
# [Klecio] os permite acessar variáveis de ambiente.
# [Klecio] O modelo visual pode ser configurado externamente sem alterar este arquivo.
import os

# [Klecio] mss captura a tela com baixo custo e boa velocidade.
import mss
# [Klecio] Pillow transforma a captura bruta em uma imagem
# [Klecio] e permite convertê-la para JPEG em memória.
from PIL import Image
# [Klecio] Cliente oficial usado para chamar o modelo Gemini.
from google import genai
# [Klecio] types fornece estruturas da API,
# [Klecio] como Part e GenerateContentConfig.
from google.genai import types

# [Klecio] Importa a chave configurada no projeto.
from core.config import GEMINI_API_KEY


# [Klecio] Lê o nome do modelo da variável GEMINI_VISION_MODEL.
# [Klecio] Se ela não existir, usa o valor padrão definido abaixo.
MODELO_LOCALIZADOR = os.getenv(
    "GEMINI_VISION_MODEL",
    "gemini-3.1-flash-lite",
)

# [Klecio] Define a confiança mínima aceita.
# [Klecio] Resultados abaixo de 0.78 são recusados para evitar cliques incertos.
CONFIANCA_MINIMA = 0.78

# [Klecio] Lista de ações sensíveis ou destrutivas.
# [Klecio] Se o alvo do clique contiver um desses termos,
# [Klecio] a operação será bloqueada antes mesmo de capturar a tela.
TERMOS_BLOQUEADOS = (
    "excluir",
    "apagar",
    "deletar",
    "remover permanentemente",
    "esvaziar lixeira",
    "formatar",
    "comprar",
    "finalizar compra",
    "pagar",
    "confirmar pagamento",
    "transferir",
    "enviar dinheiro",
    "instalar",
    "desinstalar",
    "executar como administrador",
)


# [Klecio] Padroniza um texto para comparação.
# [Klecio] Converte para minúsculas, remove espaços duplicados
# [Klecio] e limpa as extremidades.
def _normalizar(texto):
    # [Klecio] split separa o texto ignorando espaços repetidos.
    # [Klecio] join reconstrói usando somente um espaço entre as palavras.
    return " ".join(str(texto).lower().split()).strip()


# [Klecio] Verifica se o alvo contém algum termo proibido.
def _alvo_bloqueado(alvo):
    # [Klecio] Normaliza o alvo antes da comparação.
    alvo_normalizado = _normalizar(alvo)

    # [Klecio] any retorna True assim que encontrar
    # [Klecio] pelo menos um termo bloqueado dentro do alvo.
    return any(
        termo in alvo_normalizado
        for termo in TERMOS_BLOQUEADOS
    )


# [Klecio] Captura somente o monitor principal
# [Klecio] e devolve a imagem, resolução e posição na área virtual.
def _capturar_tela_principal():
    # [Klecio] Abre o capturador de tela.
    # [Klecio] O bloco with garante o fechamento automático.
    with mss.mss() as sct:
        # [Klecio] No mss, monitors[1] normalmente representa
        # [Klecio] o primeiro monitor físico, considerado o principal.
        monitor = sct.monitors[1]
        # [Klecio] Captura todos os pixels da área do monitor.
        captura = sct.grab(monitor)

        # [Klecio] Converte os bytes RGB do mss em uma imagem Pillow.
        imagem = Image.frombytes(
            "RGB",
            captura.size,
            captura.rgb,
        )

        # [Klecio] io é importado localmente porque só é necessário nesta função.
        import io
        # [Klecio] Cria um arquivo em memória RAM.
        buffer = io.BytesIO()
        # [Klecio] Converte a captura para JPEG.
        # [Klecio] A qualidade 88 reduz tamanho sem perder muita nitidez.
        imagem.save(buffer, format="JPEG", quality=88)

        # [Klecio] Retorna a imagem e os dados necessários
        # [Klecio] para converter coordenadas locais em coordenadas absolutas.
        return {
            "imagem": buffer.getvalue(),
            "largura": captura.width,
            "altura": captura.height,
            "esquerda": monitor["left"],
            "topo": monitor["top"],
        }


# [Klecio] Limpa e interpreta o JSON devolvido pelo modelo.
def _extrair_json(texto):
    # [Klecio] Garante que o valor seja texto e remove espaços externos.
    texto = str(texto or "").strip()

    # [Klecio] Alguns modelos podem envolver o JSON em bloco Markdown.
    # [Klecio] Este trecho remove as linhas com crases antes do json.loads.
    if texto.startswith("```"):
        # [Klecio] Divide a resposta em linhas.
        linhas = texto.splitlines()
        # [Klecio] Mantém somente as linhas que não iniciam
        # [Klecio] ou encerram um bloco de código Markdown.
        linhas = [
            linha
            for linha in linhas
            if not linha.strip().startswith("```")
        ]
        texto = "\n".join(linhas).strip()

    # [Klecio] Converte o texto JSON em um dicionário Python.
    return json.loads(texto)


# [Klecio] Função principal do localizador visual.
# [Klecio] Valida o pedido, captura a tela, consulta o Gemini,
# [Klecio] verifica a confiança e converte as coordenadas.
def localizar_elemento_na_tela(alvo):
    """
    Localiza um elemento na tela e retorna coordenadas absolutas.

    O modelo devolve x e y normalizados de 0 a 1000, o que evita
    dependência direta da resolução da imagem.
    """

    # [Klecio] Limpa espaços duplicados do alvo solicitado.
    alvo = " ".join(str(alvo).split()).strip()

    # [Klecio] Impede a execução sem uma descrição do elemento.
    if not alvo:
        # [Klecio] Retorna a imagem e os dados necessários
        # [Klecio] para converter coordenadas locais em coordenadas absolutas.
        return {
            "sucesso": False,
            "mensagem": "O alvo do clique não foi informado.",
        }

    # [Klecio] Bloqueia pedidos considerados sensíveis.
    if _alvo_bloqueado(alvo):
        # [Klecio] Retorna a imagem e os dados necessários
        # [Klecio] para converter coordenadas locais em coordenadas absolutas.
        return {
            "sucesso": False,
            "mensagem": (
                "Esse clique foi bloqueado por segurança. "
                "Nenhuma ação foi executada."
            ),
        }

    # [Klecio] Impede a chamada da API quando a chave não está disponível.
    if not GEMINI_API_KEY:
        # [Klecio] Retorna a imagem e os dados necessários
        # [Klecio] para converter coordenadas locais em coordenadas absolutas.
        return {
            "sucesso": False,
            "mensagem": "GEMINI_API_KEY não encontrada.",
        }

    # [Klecio] Captura o monitor principal e guarda
    # [Klecio] imagem, tamanho e deslocamento.
    captura = _capturar_tela_principal()

    # [Klecio] Define o formato obrigatório da resposta JSON.
    # [Klecio] Isso reduz respostas livres e facilita a validação.
    esquema = {
        "type": "object",
        # [Klecio] Declara cada campo que o modelo deve retornar.
        "properties": {
            # [Klecio] Indica se o elemento foi realmente localizado.
            "encontrado": {"type": "boolean"},
            # [Klecio] Coordenada horizontal normalizada entre 0 e 1000.
            "x": {"type": "integer", "minimum": 0, "maximum": 1000},
            # [Klecio] Coordenada vertical normalizada entre 0 e 1000.
            "y": {"type": "integer", "minimum": 0, "maximum": 1000},
            # [Klecio] Grau de confiança entre 0 e 1.
            "confianca": {"type": "number", "minimum": 0, "maximum": 1},
            # [Klecio] Descrição textual do elemento identificado.
            "descricao": {"type": "string"},
        },
        "required": [
            "encontrado",
            "x",
            "y",
            "confianca",
            "descricao",
        ],
    }

    # [Klecio] Instrução enviada ao modelo visual.
    # [Klecio] Ela exige o centro clicável e coordenadas normalizadas.
    prompt = (
        "Você é um localizador visual de interface de computador. "
        "Encontre na captura de tela o elemento solicitado pelo usuário. "
        "Retorne o centro clicável do elemento. "
        "Use coordenadas normalizadas: x=0 é a borda esquerda, x=1000 a direita; "
        "y=0 é o topo e y=1000 a borda inferior. "
        "Se houver mais de um elemento parecido, escolha somente quando a descrição "
        "do usuário permitir distinguir claramente. Caso contrário, marque encontrado=false. "
        "Não invente coordenadas e não escolha elementos parcialmente escondidos. "
        f"Elemento solicitado: {alvo}"
    )

    # [Klecio] Cria o cliente autenticado do Gemini.
    client = genai.Client(api_key=GEMINI_API_KEY)

    # [Klecio] Envia o prompt e a imagem para o modelo.
    resposta = client.models.generate_content(
        model=MODELO_LOCALIZADOR,
        # [Klecio] A requisição contém texto e imagem no mesmo pedido.
        contents=[
            prompt,
            # [Klecio] Converte os bytes JPEG em uma parte multimodal.
            types.Part.from_bytes(
                data=captura["imagem"],
                mime_type="image/jpeg",
            ),
        ],
        # [Klecio] Configura resposta determinística e estruturada.
        config=types.GenerateContentConfig(
            # [Klecio] Temperature 0 reduz variações e criatividade.
            temperature=0,
            # [Klecio] Solicita que a resposta seja JSON.
            response_mime_type="application/json",
            # [Klecio] Obriga a resposta a seguir o esquema definido.
            response_schema=esquema,
        ),
    )

    # [Klecio] Converte a resposta textual em dicionário.
    dados = _extrair_json(resposta.text)

    # [Klecio] Lê com segurança o indicador de localização.
    encontrado = bool(dados.get("encontrado", False))
    # [Klecio] Lê e converte a confiança para float.
    confianca = float(dados.get("confianca", 0.0))

    # [Klecio] Recusa a ação se o modelo informou que não encontrou.
    if not encontrado:
        # [Klecio] Retorna a imagem e os dados necessários
        # [Klecio] para converter coordenadas locais em coordenadas absolutas.
        return {
            "sucesso": False,
            "mensagem": (
                "Não consegui localizar esse elemento com segurança. "
                "Nenhum clique foi executado."
            ),
        }

    # [Klecio] Recusa resultados abaixo da confiança mínima.
    if confianca < CONFIANCA_MINIMA:
        # [Klecio] Retorna a imagem e os dados necessários
        # [Klecio] para converter coordenadas locais em coordenadas absolutas.
        return {
            "sucesso": False,
            "mensagem": (
                "A localização visual ficou incerta. "
                "Nenhum clique foi executado."
            ),
        }

    # [Klecio] Converte x para inteiro e limita à faixa segura.
    x_normalizado = max(0, min(1000, int(dados["x"])))
    # [Klecio] Converte y para inteiro e limita à faixa segura.
    y_normalizado = max(0, min(1000, int(dados["y"])))

    # [Klecio] Converte x de 0–1000 para pixels reais da captura.
    x_local = round(
        (x_normalizado / 1000)
        * (captura["largura"] - 1)
    )

    # [Klecio] Converte y de 0–1000 para pixels reais da captura.
    y_local = round(
        (y_normalizado / 1000)
        * (captura["altura"] - 1)
    )

    return {
        "sucesso": True,
        # [Klecio] Soma o deslocamento horizontal do monitor,
        # [Klecio] produzindo uma coordenada absoluta do Windows.
        "x": captura["esquerda"] + x_local,
        # [Klecio] Soma o deslocamento vertical do monitor.
        "y": captura["topo"] + y_local,
        "confianca": confianca,
        "descricao": str(dados.get("descricao", alvo)),
        "mensagem": "Elemento localizado.",
    }