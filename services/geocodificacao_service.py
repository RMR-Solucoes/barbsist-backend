import math
import json


import os


import re


import unicodedata


from difflib import SequenceMatcher


from pathlib import Path


from urllib.error import HTTPError, URLError


from urllib.parse import urlencode


from urllib.request import Request, urlopen


from dotenv import load_dotenv


from fastapi import HTTPException


load_dotenv(


    Path(__file__).resolve().parents[1] / ".env"


)


GEOAPIFY_URL = "https://api.geoapify.com/v1/geocode/search"


VIACEP_URL = "https://viacep.com.br/ws/{cep}/json/"


def _texto(valor):


    if valor is None:


        return ""


    return str(valor).strip()


def _normalizar(valor):


    texto = _texto(valor).lower()


    texto = unicodedata.normalize("NFKD", texto)


    texto = "".join(


        caractere


        for caractere in texto


        if not unicodedata.combining(caractere)


    )


    texto = re.sub(r"[^a-z0-9]+", " ", texto)


    return " ".join(texto.split())


def _somente_digitos(valor):


    return re.sub(r"\D", "", _texto(valor))


def _normalizar_cep(valor):


    return _somente_digitos(valor)


def _separar_logradouro_numero(endereco):


    texto = _texto(endereco)


    if not texto:


        return "", ""


    # Normaliza variantes de travessao apenas


    # para interpretar o endereco.


    # O valor original salvo pelo usuario nao e alterado.


    texto_parse = (


        texto


        .replace("\u2013", "-")


        .replace("\u2014", "-")


        .replace("\u2212", "-")


    )


    # Formatos explicitos:


    #


    # Rua X, 123


    # Rua X, 123, Bairro


    # Rua X, 123 - Bairro


    # Rua X, 123 com separador de bairro


    # Rua X, 123 com separador de bairro


    correspondencia = re.match(


        r"^(?P<rua>.*?\S)\s*,?\s+"


        r"(?P<numero>\d+[A-Za-z0-9\-\/]*)"


        r"(?:\s*[-,]\s*.*)?$",


        texto_parse,


    )


    if correspondencia:


        return (


            _texto(


                correspondencia.group("rua")


            ),


            _texto(


                correspondencia.group("numero")


            ),


        )


    # Fallback para endereco digitado


    # somente com espacos:


    #


    # Rua Baruel 501 Jardim Paulista


    #


    # Percorre os numeros da esquerda para


    # a direita e evita assumir que numeros


    # integrantes do nome da rua sejam o


    # numero do imovel.


    candidatos = []


    for candidato in re.finditer(


        r"(?<!\w)"


        r"(?P<numero>\d+[A-Za-z0-9\-\/]*)"


        r"(?!\w)",


        texto_parse,


    ):


        rua = _texto(


            texto_parse[


                :candidato.start()


            ]


        ).strip(" ,-")


        if not rua:


            continue


        if not any(


            caractere.isalpha()


            for caractere in rua


        ):


            continue


        numero = _texto(


            candidato.group("numero")


        )


        candidatos.append(


            (


                rua,


                numero,


            )


        )


        # Ex.:


        # Rua Baruel 501


        # Avenida Brasil 100


        #


        # Para "Rua 15 de Novembro 501",


        # o candidato 15 possui apenas


        # "Rua" antes dele e sera ignorado.


        if len(rua.split()) >= 2:


            return (


                rua,


                numero,


            )


    if candidatos:


        return candidatos[-1]


    return texto, ""


def _compativel(informado, retornado, limite=0.72):


    a = _normalizar(informado)


    b = _normalizar(retornado)


    if not a or not b:


        return False


    if a == b or a in b or b in a:


        return True


    return SequenceMatcher(None, a, b).ratio() >= limite


def _consultar_json(url, *, nome_servico):


    requisicao = Request(


        url,


        headers={


            "User-Agent": "BarbSist/1.0",


            "Accept": "application/json",


        },


        method="GET",


    )


    try:


        with urlopen(requisicao, timeout=12) as resposta:


            return json.load(resposta)


    except HTTPError as exc:


        raise HTTPException(


            status_code=502,


            detail=(


                f"O serviço {nome_servico} recusou a consulta. "


                "Tente novamente em instantes."


            ),


        ) from exc


    except (URLError, TimeoutError, OSError) as exc:


        raise HTTPException(


            status_code=502,


            detail=(


                f"Não foi possível consultar o serviço {nome_servico}. "


                "Verifique a conexão e tente novamente."


            ),


        ) from exc


    except ValueError as exc:


        raise HTTPException(


            status_code=502,


            detail=f"Resposta inválida do serviço {nome_servico}.",


        ) from exc


def _consultar_viacep(cep):


    cep_numerico = _normalizar_cep(cep)


    if len(cep_numerico) != 8:


        raise HTTPException(


            status_code=400,


            detail="Informe um CEP válido com 8 dígitos.",


        )


    payload = _consultar_json(


        VIACEP_URL.format(cep=cep_numerico),


        nome_servico="ViaCEP",


    )


    erro = payload.get("erro")


    if erro is True or str(erro).lower() == "true":


        raise HTTPException(


            status_code=404,


            detail="CEP não encontrado no ViaCEP.",


        )


    return payload


def _validar_endereco_postal(


    *,


    rua_informada,


    cidade_informada,


    estado_informado,


    viacep,


):


    rua_postal = _texto(viacep.get("logradouro"))


    bairro_postal = _texto(viacep.get("bairro"))


    cidade_postal = _texto(viacep.get("localidade"))


    estado_postal = _texto(viacep.get("uf"))


    cep_postal = _texto(viacep.get("cep"))


    if not rua_postal or not cidade_postal or not estado_postal:


        raise HTTPException(


            status_code=422,


            detail=(


                "O CEP foi localizado, mas não possui dados postais "


                "suficientes para validar a barbearia."


            ),


        )


    if not _compativel(rua_informada, rua_postal):


        raise HTTPException(


            status_code=422,


            detail=(


                "O CEP informado corresponde a "


                f"{rua_postal}, {bairro_postal}, "


                f"{cidade_postal}/{estado_postal}. "


                "Revise o logradouro antes de localizar."


            ),


        )


    if not _compativel(


        cidade_informada,


        cidade_postal,


        limite=0.88,


    ):


        raise HTTPException(


            status_code=422,


            detail=(


                "A cidade informada não corresponde ao CEP. "


                f"ViaCEP: {cidade_postal}/{estado_postal}."


            ),


        )


    if _normalizar(estado_informado) != _normalizar(estado_postal):


        raise HTTPException(


            status_code=422,


            detail=(


                "O estado informado não corresponde ao CEP. "


                f"ViaCEP: {cidade_postal}/{estado_postal}."


            ),


        )


    return {


        "rua": rua_postal,


        "bairro": bairro_postal,


        "cidade": cidade_postal,


        "estado": estado_postal,


        "cep": cep_postal,


    }


def _cidade_geoapify(resultado):


    return _texto(


        resultado.get("city")


        or resultado.get("town")


        or resultado.get("village")


        or resultado.get("municipality")


        or resultado.get("county")


    )


_UFS_BRASIL = {'AC': 'acre', 'AL': 'alagoas', 'AP': 'amapa', 'AM': 'amazonas', 'BA': 'bahia', 'CE': 'ceara', 'DF': 'distrito federal', 'ES': 'espirito santo', 'GO': 'goias', 'MA': 'maranhao', 'MT': 'mato grosso', 'MS': 'mato grosso do sul', 'MG': 'minas gerais', 'PA': 'para', 'PB': 'paraiba', 'PR': 'parana', 'PE': 'pernambuco', 'PI': 'piaui', 'RJ': 'rio de janeiro', 'RN': 'rio grande do norte', 'RS': 'rio grande do sul', 'RO': 'rondonia', 'RR': 'roraima', 'SC': 'santa catarina', 'SP': 'sao paulo', 'SE': 'sergipe', 'TO': 'tocantins'}

def _normalizar_estado_br(valor):
    texto = _normalizar(valor)
    for sigla, nome in _UFS_BRASIL.items():
        if texto == _normalizar(sigla) or texto == _normalizar(nome):
            return sigla
    return None


def _estados_compativeis(informado, retornado):
    uf1 = _normalizar_estado_br(informado)
    uf2 = _normalizar_estado_br(retornado)
    return bool(uf1 and uf2 and uf1 == uf2)


def _avaliar_geoapify(


    *,


    resultado,


    postal,


    numero,


):


    rua_geo = _texto(


        resultado.get("street")


        or resultado.get("address_line1")


    )


    numero_geo = _texto(resultado.get("housenumber"))


    cep_geo = _texto(resultado.get("postcode"))


    estado_geo = _texto(


        resultado.get("state_code")


        or resultado.get("state")


    )


    cidade_geo = _cidade_geoapify(resultado)


    rua_ok = bool(rua_geo) and _normalizar(postal["rua"]) == _normalizar(rua_geo)


    numero_ok = bool(numero) and (


        _normalizar(numero) == _normalizar(numero_geo)


    )


    cep_ok = (


        _normalizar_cep(postal["cep"])


        == _normalizar_cep(cep_geo)


    )


    estado_ok = True


    if estado_geo:


        estado_ok = _estados_compativeis(
            postal["estado"],
            estado_geo,
        )


    cidade_ok = True


    if cidade_geo:


        cidade_ok = _compativel(


            postal["cidade"],


            cidade_geo,


            limite=0.80,


        )


    validacoes = [


        "CEP validado pelo ViaCEP",


        "Rua validada pelo ViaCEP",


        f"Cidade postal validada: {postal['cidade']}/{postal['estado']}",


        (


            "Geoapify: rua compatível"


            if rua_ok


            else "Geoapify: rua divergente"


        ),


        (


            "Geoapify: CEP compatível"


            if cep_ok


            else "Geoapify: CEP divergente"


        ),


        (


            "Geoapify: número compatível"


            if numero_ok


            else "Geoapify: número divergente ou não confirmado"


        ),


        (


            "Geoapify: estado compatível"


            if estado_ok


            else "Geoapify: estado/região divergente; ViaCEP prevalece"


        ),


    ]


    if cidade_geo:


        validacoes.append(


            (


                "Geoapify: cidade compatível"


                if cidade_ok


                else (


                    "Geoapify: nome de localidade divergente "


                    f"({cidade_geo}); ViaCEP prevalece"


                )


            )


        )


    catalogo_permitido = bool(

        rua_ok

        and numero_ok

        and cep_ok

        and estado_geo

        and cidade_geo

        and estado_ok

        and cidade_ok

    )


    if catalogo_permitido:


        nivel = "CONFIAVEL"


    elif rua_ok and cep_ok:


        nivel = "CONFERIR"


    else:


        nivel = "IMPRECISA"


    return {


        "nivel_confianca": nivel,


        "catalogo_permitido": catalogo_permitido,


        "validacoes": validacoes,


    }


def geocodificar_endereco_barbearia(dados):


    api_key = _texto(os.getenv("GEOAPIFY_API_KEY"))


    if not api_key:


        raise HTTPException(


            status_code=503,


            detail=(


                "Geocodificação por endereço ainda não está configurada. "


                "Defina GEOAPIFY_API_KEY no backend."


            ),


        )


    endereco = _texto(dados.endereco)


    cidade = _texto(dados.cidade)


    estado = _texto(dados.estado)


    cep = _texto(dados.cep)


    if not endereco or not cidade or not estado or not cep:


        raise HTTPException(


            status_code=400,


            detail=(


                "Informe endereço, cidade, estado e CEP antes de "


                "localizar a barbearia."


            ),


        )


    rua_informada, numero = _separar_logradouro_numero(endereco)


    if not numero:


        raise HTTPException(


            status_code=400,


            detail=(


                "Informe o número junto ao endereço. "


                "Exemplo: Rua Finlândia 76. "


                "Se o local não possuir número, use a localização atual."


            ),


        )


    viacep = _consultar_viacep(cep)


    postal = _validar_endereco_postal(


        rua_informada=rua_informada,


        cidade_informada=cidade,


        estado_informado=estado,


        viacep=viacep,


    )


    # P8_12_N13C1_8
    # Busca textual baseada em endereco validado pelo ViaCEP.

    texto_busca = ", ".join(
        parte
        for parte in (
            postal["rua"] + ", " + numero,
            postal["bairro"],
            postal["cidade"],
            postal["estado"],
            postal["cep"],
            "Brasil",
        )
        if parte
    )

    parametros = {
        "text": texto_busca,
        "format": "json",
        "limit": 10,
        "lang": "pt",
        "filter": "countrycode:br",
        "apiKey": api_key,
    }

    payload = _consultar_json(


        f"{GEOAPIFY_URL}?{urlencode(parametros)}",


        nome_servico="Geoapify",


    )


    resultados = payload.get("results") or []


    if not resultados:


        raise HTTPException(


            status_code=424,


            detail=(


                "O endereço postal foi validado pelo ViaCEP, mas "


                "nenhuma coordenada foi encontrada. "


                "Use a localização atual da barbearia."


            ),


        )


    candidatos_validos = []

    for candidato in resultados:

        if not isinstance(candidato, dict):
            continue

        if str(
            candidato.get("country_code") or ""
        ).lower() != "br":
            continue

        avaliacao_candidato = _avaliar_geoapify(
            resultado=candidato,
            postal=postal,
            numero=numero,
        )

        if not avaliacao_candidato["catalogo_permitido"]:
            continue

        try:
            lat = float(candidato["lat"])
            lon = float(candidato["lon"])

            confianca = float(
                (candidato.get("rank") or {}).get(
                    "confidence", 0
                )
            )

        except (KeyError, TypeError, ValueError):
            continue

        if not (
            math.isfinite(lat)
            and math.isfinite(lon)
            and math.isfinite(confianca)
            and -90 <= lat <= 90
            and -180 <= lon <= 180
            and 0.85 <= confianca <= 1
        ):
            continue

        prioridade = int(
            candidato.get("result_type") == "building"
        )

        candidatos_validos.append(
            (prioridade, confianca, candidato)
        )

    if not candidatos_validos:
        raise HTTPException(
            status_code=424,
            detail=(
                "Nao foi encontrada localizacao suficientemente "
                "confiavel para o endereco comercial. "
                "Confira rua, numero, CEP, cidade e estado."
            ),
        )

    candidatos_validos.sort(
        key=lambda item: (item[0], item[1]),
        reverse=True,
    )

    resultado = candidatos_validos[0][2]


    try:


        latitude = float(resultado["lat"])


        longitude = float(resultado["lon"])


    except (KeyError, TypeError, ValueError) as exc:


        raise HTTPException(


            status_code=502,


            detail="O serviço de localização não retornou coordenadas válidas.",


        ) from exc


    rank = resultado.get("rank") or {}


    confianca = rank.get("confidence")


    if confianca is not None:


        try:


            confianca = float(confianca)


        except (TypeError, ValueError):


            confianca = None


    avaliacao = _avaliar_geoapify(


        resultado=resultado,


        postal=postal,


        numero=numero,


    )


    endereco_postal = ", ".join(


        parte


        for parte in (


            postal["rua"] + ", " + numero,


            postal["bairro"],


            postal["cidade"] + " - " + postal["estado"],


            postal["cep"],


            "Brasil",


        )


        if parte


    )


    return {


        "latitude": latitude,


        "longitude": longitude,


        "endereco_formatado": (


            resultado.get("formatted")


            or endereco_postal


        ),


        "confianca": confianca,


        "nivel_confianca": avaliacao["nivel_confianca"],


        "catalogo_permitido": avaliacao["catalogo_permitido"],


        "validacoes": avaliacao["validacoes"],


        "endereco_postal": endereco_postal,


        "bairro_postal": postal["bairro"],


        "cidade_postal": postal["cidade"],


        "estado_postal": postal["estado"],


        "cep_validado": postal["cep"],


    }
