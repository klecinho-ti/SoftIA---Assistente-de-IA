# [Klecio] OpenCV (cv2) é responsável por acessar a webcam
# [Klecio] e capturar os frames da câmera.
import cv2

# [Klecio] Pillow (PIL) será utilizada para transformar
# [Klecio] o frame do OpenCV em uma imagem JPEG.
from PIL import Image

# [Klecio] io.BytesIO cria um arquivo totalmente em memória.
# [Klecio] Assim não precisamos salvar nenhuma imagem no disco.
import io

# [Klecio] time fornece funções relacionadas ao tempo.
# [Klecio] Aqui ele é utilizado apenas para aguardar
# [Klecio] alguns milissegundos antes da captura.
import time


# [Klecio] Esta função captura uma fotografia da webcam
# [Klecio] e devolve a imagem em formato JPEG (bytes).
# [Klecio] Os bytes serão enviados diretamente ao Gemini.
def capturar_camera_bytes():
    """
    Captura uma imagem da webcam padrão.
    Descarta alguns frames iniciais para dar tempo
    da câmera ajustar foco, luz e exposição.
    """

    # [Klecio] Abre a webcam padrão do computador.
    # [Klecio] O índice 0 normalmente representa
    # [Klecio] a primeira câmera disponível.
    camera = cv2.VideoCapture(0)

    # [Klecio] Confirma se a câmera foi aberta corretamente.
    # [Klecio] Caso contrário interrompe a execução.
    if not camera.isOpened():
        raise RuntimeError("Não foi possível acessar a webcam.")

    # Dá um pequeno tempo para a câmera estabilizar
    # [Klecio] Muitas webcams precisam de alguns instantes
    # [Klecio] para ajustar foco, brilho e exposição.
    time.sleep(0.2)

    # [Klecio] Variável que armazenará o último frame válido.
    frame = None

    # Descarta os primeiros frames ruins/desatualizados
    # [Klecio] Os primeiros frames normalmente possuem
    # [Klecio] baixa qualidade ou pertencem ao buffer antigo.
    # [Klecio] Por isso capturamos alguns antes da imagem final.
    for _ in range(4):

        # [Klecio] Lê um frame da câmera.
        # [Klecio] sucesso indica se a captura ocorreu corretamente.
        sucesso, frame = camera.read()

        # [Klecio] Em caso de erro, libera imediatamente
        # [Klecio] a webcam antes de interromper a função.
        if not sucesso:
            camera.release()
            raise RuntimeError("Não foi possível capturar imagem da webcam.")

    # [Klecio] Libera a webcam para que outros programas
    # [Klecio] possam utilizá-la normalmente.
    camera.release()

    # [Klecio] O OpenCV trabalha em BGR.
    # [Klecio] A Pillow utiliza RGB.
    # [Klecio] Portanto fazemos a conversão das cores.
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # [Klecio] Converte o array NumPy em uma imagem Pillow.
    imagem = Image.fromarray(frame_rgb)

    # [Klecio] Cria um arquivo temporário somente na memória RAM.
    buffer = io.BytesIO()

    # [Klecio] Salva a imagem no buffer em formato JPEG.
    # [Klecio] quality=90 oferece ótima qualidade
    # [Klecio] mantendo um tamanho relativamente pequeno.
    imagem.save(
        buffer,
        format="JPEG",
        quality=90
    )

    # [Klecio] Retorna apenas os bytes do JPEG.
    # [Klecio] Esses bytes podem ser enviados diretamente
    # [Klecio] para a IA sem criar arquivos no disco.
    return buffer.getvalue()