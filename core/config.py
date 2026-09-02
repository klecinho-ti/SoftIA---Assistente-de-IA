import os
from dotenv import load_dotenv

from core.api_key_manager import carregar_configuracoes

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Modelo usado pelo SOFTIA
GEMINI_LIVE_MODEL = "gemini-3.1-flash-live-preview"

# ============================================================
# MODELOS DISPONÍVEIS PARA TESTE
# ============================================================
#MODELO = "gemini-2.5-flash-native-audio-preview-12-2025"
#MODELO = "gemini-2.5-flash-native-audio-preview-09-2025"
#MODELO = "gemini-3.1-flash-live-preview"


# Vozes oferecidas na janela de Configurações do SOFTIA.
VOZ_FEMININA = "Vindemiatrix"
VOZ_MASCULINA = "Puck"


def obter_configuracoes_atuais():
    """
    Lê, em tempo real, as configurações mais recentes salvas pelo
    usuário na janela de Configurações (nome da assistente, voz e
    senha de autenticação).

    Ler sempre do arquivo (em vez de guardar em uma constante fixa)
    é o que permite que uma mudança feita na janela de Configurações
    valha já na próxima chamada, sem reiniciar nem reinstalar o SOFTIA.
    """

    return carregar_configuracoes()


def obter_voz_atual():
    """
    Retorna o nome técnico da voz do Gemini correspondente ao gênero
    de voz escolhido pelo usuário (feminina ou masculina).
    """

    genero = obter_configuracoes_atuais()["voz_genero"]

    return (
        VOZ_MASCULINA
        if genero == "masculina"
        else VOZ_FEMININA
    )

# ============================================================
# VOZES DISPONÍVEIS PARA TESTE
# ============================================================
#
# Zephyr   - brilhante
# Puck     - animada
# Charon   - informativa
# Kore     - feminia e firme
# Fenrir   - empolgada
# Leda     - jovem
# Orus     - firme
# Aoede    - leve
# Callirrhoe - descontraída
# Autonoe  - brilhante
# Enceladus - suave/sussurrante
# Iapetus  - clara
# Umbriel  - descontraída
# Algieba  - suave
# Despina  - suave
# Erinome  - clara
# Algenib  - rouca
# Rasalgethi - informativa
# Laomedeia - animada
# Achernar - suave
# Alnilam  - firme
# Schedar  - equilibrada
# Gacrux   - madura
# Pulcherrima - direta
# Achird   - amigável
# Zubenelgenubi - casual
# Vindemiatrix - feminina gentil
# Sadachbia - animada
# Sadaltager - experiente
# Sulafat  - calorosa