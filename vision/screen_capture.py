# [Klecio] io permite criar arquivos temporários diretamente na memória RAM.
# [Klecio] Isso evita salvar imagens no disco antes de enviá-las ao Gemini.
import io

# [Klecio] mss é uma biblioteca extremamente rápida para captura de tela.
# [Klecio] Ela acessa diretamente os pixels do monitor.
import mss

# [Klecio] Pillow (PIL) será utilizada para transformar os pixels
# [Klecio] capturados pelo mss em uma imagem JPEG.
from PIL import Image


# [Klecio] Esta função captura a tela principal do computador
# [Klecio] e devolve uma imagem JPEG em formato de bytes.
# [Klecio] Esses bytes são enviados diretamente para o Gemini Vision.
def capturar_tela_bytes():
    """
    Captura a tela principal
    e retorna JPEG em bytes.
    """

    # [Klecio] Abre o capturador de tela.
    # [Klecio] O bloco "with" garante que os recursos
    # [Klecio] sejam liberados automaticamente ao final.
    with mss.mss() as sct:

        # [Klecio] monitors[1] normalmente representa o monitor principal.
        # [Klecio] monitors[0] corresponde à área virtual de todos os monitores,
        # [Klecio] garantindo que a IA enxergue qualquer monitor em uso,
        # [Klecio] não só o principal.
        monitor = sct.monitors[0]

        # [Klecio] Captura todos os pixels do monitor escolhido.
        screenshot = sct.grab(
            monitor
        )

        # [Klecio] Converte os pixels capturados em uma imagem Pillow.
        # [Klecio] O mss fornece os pixels em RGB, compatíveis com a Pillow.
        imagem = Image.frombytes(
            "RGB",
            screenshot.size,
            screenshot.rgb
        )

        # [Klecio] Cria um buffer em memória para armazenar o JPEG.
        buffer = io.BytesIO()

        # [Klecio] Salva a imagem no buffer.
        # [Klecio] quality=80 reduz o tamanho do arquivo,
        # [Klecio] mantendo boa qualidade para análise pela IA.
        imagem.save(
            buffer,
            format="JPEG",
            quality=80
        )

        # [Klecio] Retorna apenas os bytes da imagem JPEG.
        # [Klecio] Nenhum arquivo é criado no disco.
        return buffer.getvalue()