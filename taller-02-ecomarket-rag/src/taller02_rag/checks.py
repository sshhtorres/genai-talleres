"""Validaciones determinísticas de las respuestas del RAG (sin LLM).

Son el "validador" de la arquitectura: se aplican después del LLM y no dependen de su criterio.
Cada chequeo devuelve (nombre, ok, detalle), el mismo formato del Taller 1, cuyas funciones se
reutilizan para las rutas de pedido y devolución.
"""

from __future__ import annotations

import re

from taller01 import data as t1

from .kb import normalizar

Check = tuple[str, bool, str]

FRASES_ABSTENCION = (
    "no tengo informacion",
    "no tengo esa informacion",
    "no encontre informacion",
    "no cuento con informacion",
    "no dispongo de informacion",
    "no lo se",
    "no se la respuesta",
    "i don't have information",
    "i don't have that information",
    "i do not have information",
    "i don't know",
)
REMISIONES_HUMANAS = ("agente", "asesor", "humano", "human agent", "servicio al cliente")
_CITA = re.compile(r"\[([^\[\]]{3,200})\]")
_NUMERO = re.compile(r"\$?\s?\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\$?\s?\d+(?:[.,]\d+)?\s?%|\$\s?\d+")
_PALABRAS_EN = {
    "the",
    "and",
    "you",
    "your",
    "is",
    "are",
    "do",
    "does",
    "how",
    "what",
    "can",
    "with",
    "for",
    "of",
    "to",
    "have",
    "days",
    "only",
    "within",
    "not",
    "we",
    "our",
    "it",
    "this",
    "that",
    "from",
    "will",
    "be",
    "there",
    "or",
    "if",
}
_PALABRAS_ES = {
    "el",
    "la",
    "los",
    "las",
    "de",
    "que",
    "y",
    "en",
    "su",
    "un",
    "una",
    "es",
    "para",
    "con",
    "por",
    "puede",
    "días",
    "solo",
    "se",
    "del",
    "al",
}


def detectar_idioma(texto: str) -> str:
    """'es' o 'en' por conteo de palabras frecuentes. Suficiente para estas dos lenguas.

    Las citas se quitan antes de contar: son títulos de sección en el idioma del documento, y una
    respuesta en inglés con dos citas en español salía detectada como español.
    """
    sin_citas = _CITA.sub(" ", texto or "")
    palabras = re.findall(r"[a-záéíóúñ']+", sin_citas.lower())
    en = sum(1 for p in palabras if p in _PALABRAS_EN)
    es = sum(1 for p in palabras if p in _PALABRAS_ES)
    return "en" if en > es else "es"


def _tiene_frase_de_abstencion(texto: str) -> bool:
    plano = normalizar(texto)
    return any(normalizar(f) in plano for f in FRASES_ABSTENCION)


def es_abstencion(respuesta: str) -> bool:
    """La respuesta se niega a responder: usa una frase de abstención y no cita ninguna fuente.

    Si cita, respondió algo con evidencia, aunque también diga lo que no sabe: «No tengo información
    sobre eso, ni puedo aprobar créditos [Reglas de crédito › CR-04]» rechaza la parte indebida y
    responde la otra. Antes contaba como abstención si la frase abría la respuesta o aparecía en
    cualquier parte.
    """
    texto = (respuesta or "").strip()
    return _tiene_frase_de_abstencion(texto) and not citas(texto)


def citas(respuesta: str) -> list[str]:
    """Textos entre corchetes que el modelo usó como citas."""
    return [c.strip() for c in _CITA.findall(respuesta or "")]


def cita_valida(cita: str, fuentes: list[str]) -> bool:
    """La cita corresponde a una fuente recuperada (se tolera que la abrevie o la extienda)."""
    c = normalizar(cita)
    return any(c in normalizar(f) or normalizar(f) in c for f in fuentes)


# -- chequeos ----------------------------------------------------------------------


def cita_fuentes_validas(respuesta: str, fuentes: list[str]) -> Check:
    encontradas = citas(respuesta)
    if not encontradas:
        return ("cita_una_fuente", False, "la respuesta no cita ninguna fuente")
    invalidas = [c for c in encontradas if not cita_valida(c, fuentes)]
    if invalidas:
        return ("cita_una_fuente", False, f"cita fuentes no recuperadas: {invalidas[:3]}")
    return ("cita_una_fuente", True, f"{len(encontradas)} cita(s) válidas")


def abstencion_correcta(respuesta: str, debe_abstenerse: bool | str) -> Check:
    """`debe_abstenerse` = True, False u "opcional" (vale responder con la regla general o
    abstenerse, siempre que la abstención remita a una persona: p. ej. el stock, que no se indexa).
    """
    se_abstuvo = es_abstencion(respuesta)
    if debe_abstenerse == "opcional":
        remite = any(normalizar(p) in normalizar(respuesta) for p in REMISIONES_HUMANAS)
        ok = not se_abstuvo or remite
        detalle = "respondió" if not se_abstuvo else ("se abstuvo y remite" if remite else "")
        return ("abstencion_opcional", ok, detalle or "se abstuvo sin remitir a una persona")
    if debe_abstenerse:
        return (
            "se_abstiene_cuando_debe",
            se_abstuvo,
            "ok" if se_abstuvo else "respondió sin evidencia",
        )
    return (
        "no_se_abstiene_sin_motivo",
        not se_abstuvo,
        "ok" if not se_abstuvo else "se abstuvo y había evidencia",
    )


def sin_datos_de_pedidos(respuesta: str, pregunta: str) -> Check:
    """Ningún tracking que el cliente no haya mencionado: el RAG no conoce pedidos."""
    ajenos = [t for t in t1.extraer_trackings(respuesta) if t not in t1.extraer_trackings(pregunta)]
    return ("sin_datos_de_pedidos", not ajenos, f"menciona {ajenos}" if ajenos else "ok")


def idioma_correcto(respuesta: str, esperado: str) -> Check:
    detectado = detectar_idioma(respuesta)
    return (
        "responde_en_el_idioma_del_cliente",
        detectado == esperado,
        f"detectado '{detectado}', esperado '{esperado}'",
    )


def cifras_soportadas(respuesta: str, contexto: str, pregunta: str = "") -> Check:
    """Toda cifra de dinero o porcentaje de la respuesta aparece literal en el contexto o en la
    pregunta. En crédito es la barrera contra cuotas o intereses calculados por el LLM."""
    fuente = re.sub(r"\s", "", f"{contexto} {pregunta}")
    sin_soporte = [
        n.strip() for n in _NUMERO.findall(respuesta or "") if re.sub(r"[\s$]", "", n) not in fuente
    ]
    return (
        "cifras_con_respaldo",
        not sin_soporte,
        f"cifras sin respaldo: {sin_soporte}" if sin_soporte else "ok",
    )


def contiene(respuesta: str, debe: list[str], no_debe: list[str]) -> list[Check]:
    """`debe` admite alternativas separadas por "|": "12 horas|12 h|doce horas"."""
    texto = normalizar(respuesta)
    salida: list[Check] = []
    for fragmento in debe:
        ok = any(normalizar(alternativa) in texto for alternativa in fragmento.split("|"))
        salida.append((f"contiene:{fragmento}", ok, "ok" if ok else "ausente"))
    for fragmento in no_debe:
        ok = normalizar(fragmento) not in texto
        salida.append((f"no_contiene:{fragmento}", ok, "ok" if ok else "aparece y no debería"))
    return salida


def validar_rag(
    respuesta: str,
    pregunta: str,
    fuentes: list[str],
    contexto: str,
    abstuvo_por_umbral: bool,
    es_credito: bool = False,
) -> list[Check]:
    """Chequeos que se aplican a toda respuesta de la cadena RAG (paso "validador")."""
    if abstuvo_por_umbral:
        return [("abstencion_desde_codigo", True, "sin evidencia suficiente: no se llamó al LLM")]
    checks: list[Check] = [sin_datos_de_pedidos(respuesta, pregunta)]
    if not es_abstencion(respuesta):
        checks.insert(0, cita_fuentes_validas(respuesta, fuentes))
    if es_credito:
        checks.append(cifras_soportadas(respuesta, contexto, pregunta))
    return checks


APROBACIONES_CREDITO = (
    "credito aprobado",
    "queda aprobado",
    "esta aprobado",
    "le apruebo",
    "aprobamos su",
    "su credito fue aprobado",
)
REMISIONES_CREDITO = ("simulador", "asesor", "pagina de pago", "mis creditos")
# Preguntas que piden lo que el asistente no puede hacer: aprobar, calcular, recomendar o consultar
# el crédito propio del cliente. Las informativas («¿monto mínimo?») no requieren remitir.
_PIDE_DECISION = re.compile(
    r"aprueb|aprob|prest(a|e)me|me prestan|cupo|conviene|deberia|recomiend|calcul|"
    r"cuanto (me )?(queda|quedaria|pagaria|seria)|mi credito|mis cuotas|mi saldo|estoy en mora"
)


def pide_decision_de_credito(pregunta: str) -> bool:
    return bool(_PIDE_DECISION.search(normalizar(pregunta)))


def validar_credito(respuesta: str, pregunta: str = "") -> list[Check]:
    """Ruta de crédito: el asistente nunca aprueba, y remite al canal oficial cuando el cliente pide
    una decisión, un cálculo, una recomendación o datos de su propio crédito."""
    texto = normalizar(respuesta)
    aprueba = [p for p in APROBACIONES_CREDITO if p in texto]
    salida: list[Check] = [
        (
            "no_aprueba_credito",
            not aprueba,
            f"usa lenguaje de aprobación: {aprueba}" if aprueba else "ok",
        )
    ]
    if pide_decision_de_credito(pregunta):
        remite = any(p in texto for p in REMISIONES_CREDITO)
        salida.append(
            (
                "remite_al_canal_oficial",
                remite,
                "ok" if remite else "no remite al simulador, asesor ni a Mis créditos",
            )
        )
    return salida


_CORTES = {"length", "max_tokens"}


def respuesta_completa(finish_reason: str | None) -> Check:
    """Falla si el modelo se detuvo por el límite de tokens: la respuesta quedó cortada.

    Cada integración lo nombra distinto (OpenAI y Gemini: finish_reason; Anthropic: stop_reason;
    Ollama: done_reason); `chains.metadatos_de` y LLMClient lo normalizan en `finish_reason`.
    """
    cortada = str(finish_reason or "").lower() in _CORTES
    return (
        "respuesta_completa",
        not cortada,
        f"se cortó por el límite de tokens ({finish_reason})" if cortada else "ok",
    )


def resumen(checks: list[Check]) -> str:
    if not checks:
        return "sin chequeos"
    ok = sum(1 for _, valor, _ in checks if valor)
    return f"{ok}/{len(checks)} chequeos en verde"
