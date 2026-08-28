# Biblioteca usada para consultar CPU, memória e discos do computador.
import psutil

# Biblioteca usada para consultar informações do sistema operacional
# e da arquitetura da máquina.
import platform

# Biblioteca usada para executar o PowerShell e obter o nome da
# placa de vídeo instalada.
import subprocess


def consultar_propriedade_cim(classe, propriedade):
    """
    Consulta uma propriedade de uma classe CIM/WMI do Windows
    usando o PowerShell (Get-CimInstance).

    É usada para obter nomes amigáveis de hardware que as
    bibliotecas padrão do Python não expõem diretamente,
    como o modelo comercial do processador e da placa de vídeo.
    """

    try:
        resultado = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Get-CimInstance {classe} | "
                f"Select-Object -ExpandProperty {propriedade}",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=10,
            check=False,
        )

        if resultado.returncode != 0:
            return []

        return [
            linha.strip()
            for linha in resultado.stdout.splitlines()
            if linha.strip()
        ]

    except (subprocess.SubprocessError, OSError):
        return []


def obter_nome_gpu():
    """
    Consulta o nome das placas de vídeo instaladas no computador.
    """

    return consultar_propriedade_cim(
        "Win32_VideoController",
        "Name",
    )


def obter_nome_cpu():
    """
    Consulta o nome comercial do processador instalado,
    como "Intel(R) Core(TM) i5-6300U".

    platform.processor() retorna apenas um identificador técnico,
    por isso o nome amigável é obtido via WMI.
    """

    nomes = consultar_propriedade_cim(
        "Win32_Processor",
        "Name",
    )

    return nomes[0] if nomes else (
        platform.processor() or "Processador não identificado"
    )


def formatar_bytes(valor):
    """
    Converte um valor em bytes para gigabytes com uma casa decimal.
    """

    return round(valor / (1024 ** 3), 1)


def obter_informacoes_hardware():
    """
    Reúne as principais informações de hardware do computador:

    - processador (nome, núcleos e uso atual);
    - memória RAM (total, em uso e percentual);
    - disco principal (total, livre e percentual);
    - placa de vídeo;
    - sistema operacional.

    Retorna um texto único e objetivo, pronto para ser falado
    pelo SOFTIA.
    """

    try:
        processador = obter_nome_cpu()
        nucleos_fisicos = psutil.cpu_count(logical=False)
        nucleos_logicos = psutil.cpu_count(logical=True)

        # intervalo=1 mede o uso real da CPU em um segundo,
        # em vez de retornar sempre 0.0.
        uso_cpu = psutil.cpu_percent(interval=1)

        memoria = psutil.virtual_memory()
        memoria_total = formatar_bytes(memoria.total)
        memoria_usada = formatar_bytes(memoria.used)

        disco = psutil.disk_usage("C:\\")
        disco_total = formatar_bytes(disco.total)
        disco_livre = formatar_bytes(disco.free)

        gpus = obter_nome_gpu()
        gpu_texto = ", ".join(gpus) if gpus else "não identificada"

        sistema = (
            f"{platform.system()} {platform.release()} "
            f"({platform.machine()})"
        )

        return (
            f"Processador: {processador}, "
            f"com {nucleos_fisicos} núcleos físicos e "
            f"{nucleos_logicos} núcleos lógicos, "
            f"uso atual de {uso_cpu:.0f}%. "
            f"Memória RAM: {memoria_usada} GB usados de "
            f"{memoria_total} GB, {memoria.percent:.0f}% em uso. "
            f"Disco C: {disco_livre} GB livres de "
            f"{disco_total} GB, {disco.percent:.0f}% ocupado. "
            f"Placa de vídeo: {gpu_texto}. "
            f"Sistema operacional: {sistema}."
        )

    except Exception as erro:
        return (
            "Não consegui coletar as informações de hardware "
            f"deste computador. Detalhes: {erro}"
        )
