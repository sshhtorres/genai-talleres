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
    "no encontre informacion",
    "no cuento con informacion",
    "no dispongo de informacion",
    "i don't have information",
    "i do not have information",
)
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
    "no",
}


def detectar_idioma(texto: str) -> str:
    """'es' o 'en' por conteo de palabras frecuentes. Suficiente para estas dos lenguas."""
    palabras = re.findall(r"[a-záéíóúñ']+", (texto or "").lower())
    en = sum(1 for p in palabras if p in _PALABRAS_EN)
    es = sum(1 for p in palabras if p in _PALABRAS_ES)
    return "en" if en > es else "es"


def es_abstencion(respuesta: str) -> bool:
    plano = normalizar(respuesta)
    return any(normalizar(f) in plano for f in FRASES_ABSTENCION)


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


def abstencion_correcta(respuesta: str, debe_abstenerse: bool) -> Check:
    se_abstuvo = es_abstencion(respuesta)
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


def resumen(checks: list[Check]) -> str:
    if not checks:
        return "sin chequeos"
    ok = sum(1 for _, valor, _ in checks if valor)
    return f"{ok}/{len(checks)} chequeos en verde"
