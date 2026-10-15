"""El script RAG de clase, modernizado: los mismos 7 pasos, con las APIs actuales de LangChain.

Es un puente didáctico entre el ejemplo de clase (`rag_ejemplo_original.py`) y el paquete del
taller (`src/taller02_rag/`): conserva su estructura paso a paso, pero corrige lo que en LangChain
1.x ya no funciona o no conviene. Al final del archivo, la tabla "Qué cambió y por qué".

Requisitos: Ollama en marcha con los modelos del perfil `ollama` y `embeddinggemma`:
    ollama pull embeddinggemma:300m && ollama pull gemma4:e4b

Uso (desde la raíz del repositorio). Chroma no es dependencia del taller (arrastra `chromadb`
completo), así que `uv run --with` lo instala solo para esta ejecución:
    uv run --with "langchain-chroma==1.1.0" python taller-02-ecomarket-rag/scripts/rag_ejemplo_modernizado.py

Los IDs de modelo se leen de providers.toml, como en todo el repositorio.
"""

from __future__ import annotations

import sys

# -- Imports (versiones actuales) -------------------------------------------------------------
# langchain.text_splitter          -> langchain_text_splitters
# langchain_community Ollama/OllamaEmbeddings -> langchain_ollama (ChatOllama, OllamaEmbeddings)
# langchain_community Chroma        -> langchain_chroma
# RetrievalQA (obsoleto)            -> una cadena LCEL explícita
import httpx
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from genai_common import get_profile
from genai_common.embeddings import get_embedding_profile

# -- Paso 1. Base de conocimiento --------------------------------------------------------------
# Igual que en el original: el mismo documento, escrito en el propio script. El paquete del taller,
# en cambio, carga cuatro documentos en cuatro formatos desde data/kb/. (Este texto de clase cuenta
# los 30 días desde la compra; la política del taller, como la del Taller 1, desde la entrega.)
DOCUMENTO_ECO_MARKET = """
Política de Devoluciones de EcoMarket:

Nuestra política de devoluciones permite a los clientes devolver productos dentro de los 30 días posteriores a la fecha de compra. Para ser elegible para una devolución, el artículo debe estar sin usar, en su embalaje original y en las mismas condiciones en que lo recibió. Los productos perecederos, como alimentos y flores, no son elegibles para devolución. Las devoluciones de ropa de segunda mano también están sujetas a una revisión estricta para garantizar que el artículo no haya sido usado después de la compra. Para iniciar una devolución, visite nuestra sección de ayuda en el sitio web y siga los pasos.
"""


# -- Paso 2. Modelo de embeddings ---------------------------------------------------------------
# El original usaba OllamaEmbeddings(model="llama2"): un LLM de chat como modelo de embeddings. No
# fue entrenado para recuperación y su español es débil. Aquí: embeddinggemma, un modelo de
# embeddings multilingüe de ~300 M parámetros.
#
# Detalle importante: EmbeddingGemma espera un prefijo distinto para la pregunta y para el
# documento. Ollama no los añade por su cuenta; si se omiten no hay error, pero la recuperación
# empeora en silencio. Esta clase los antepone (el paquete del taller hace lo mismo en
# genai_common.embeddings.AsymmetricEmbeddings).
class EmbeddingsConPrefijos(Embeddings):
    def __init__(self, base: OllamaEmbeddings, prefijo_pregunta: str, prefijo_documento: str):
        self.base = base
        self.prefijo_pregunta = prefijo_pregunta
        self.prefijo_documento = prefijo_documento

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.base.embed_documents([self.prefijo_documento + t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self.base.embed_query(self.prefijo_pregunta + text)


perfil_emb = get_embedding_profile("embeddinggemma")
embeddings = EmbeddingsConPrefijos(
    OllamaEmbeddings(model=perfil_emb.model, base_url=perfil_emb.base_url),
    prefijo_pregunta=perfil_emb.query_prefix,
    prefijo_documento=perfil_emb.document_prefix,
)

# En el original, el try/except envolvía la CONSTRUCCIÓN del objeto, que no se conecta a nada: el
# error real aparecía después, dentro de Chroma.from_documents. Aquí se prueba la conexión justo
# donde ocurre, con un mensaje que dice qué hacer.
try:
    embeddings.embed_query("prueba de conexión")
except (httpx.HTTPError, ConnectionError, OSError) as exc:
    sys.exit(
        f"No se pudo usar {perfil_emb.model} en {perfil_emb.base_url} ({exc}).\n"
        f"¿Está Ollama en marcha y descargado el modelo? -> ollama pull {perfil_emb.model}"
    )
except Exception as exc:  # p. ej. ollama.ResponseError si el modelo no está descargado
    sys.exit(f"Ollama respondió con un error: {exc}\n-> ollama pull {perfil_emb.model}")

# -- Paso 3. División en chunks -------------------------------------------------------------------
# Los mismos parámetros del original. Con un documento de menos de 1.000 caracteres sale UN solo
# chunk: la recuperación es trivial (siempre devuelve todo). Funciona por accidente; con una base
# real hay que elegir la estrategia por tipo de documento (ver src/taller02_rag/chunking.py).
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
docs = text_splitter.create_documents(
    [DOCUMENTO_ECO_MARKET], metadatas=[{"fuente": "Política de Devoluciones de EcoMarket"}]
)
print(f"Paso 3: {len(docs)} chunk(s) de un documento de {len(DOCUMENTO_ECO_MARKET)} caracteres.")

# -- Paso 4. Base vectorial ------------------------------------------------------------------------
# Chroma en memoria, como en el original: se reindexa (y se recalculan los embeddings) en cada
# ejecución y nada persiste. El paquete del taller usa Postgres + pgvector con indexación
# idempotente, separada de la consulta.
print("Creando y cargando la base de datos vectorial...")
vectorstore = Chroma.from_documents(documents=docs, embedding=embeddings)

# -- Paso 5. Modelo de lenguaje --------------------------------------------------------------------
# El original usaba Ollama(model="llama2"), un modelo local antiguo con español limitado. Aquí, el
# modelo del perfil `ollama` de providers.toml (Gemma 4), con el razonamiento desactivado: piensa
# por defecto y, para responder sobre un contexto ya recuperado, solo agrega latencia.
perfil_llm = get_profile("ollama")
llm = ChatOllama(
    model=perfil_llm.model,
    base_url=perfil_llm.extra["langchain"]["base_url"],
    reasoning=False,
    temperature=0.2,
)

# -- Paso 6. Cadena de recuperación + generación -----------------------------------------------------
# El original: RetrievalQA tipo "stuff" con el prompt por defecto (en inglés, sin reglas ni citas).
# "Stuff" = pegar todos los chunks recuperados en un único prompt. Aquí la misma idea en LCEL, con
# cada eslabón visible, un prompt propio en español y las fuentes devueltas junto a la respuesta.
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Eres el asistente de atención al cliente de EcoMarket. Responde solo con la "
            "información del contexto; si no está, di que no la tienes. Responde en español.",
        ),
        ("human", "Contexto:\n{contexto}\n\nPregunta: {pregunta}"),
    ]
)


def formatear(documentos: list[Document]) -> str:
    return "\n\n".join(d.page_content for d in documentos)


qa_chain = RunnableParallel(
    documentos=retriever,  # pregunta -> chunks recuperados
    pregunta=RunnablePassthrough(),
).assign(
    respuesta=RunnableLambda(
        lambda x: {"contexto": formatear(x["documentos"]), "pregunta": x["pregunta"]}
    )
    | prompt
    | llm
    | StrOutputParser()
)

# -- Paso 7. Interacción ------------------------------------------------------------------------------
# El original: bucle con input() y qa_chain.run(pregunta). `.run` está obsoleto (`.invoke`) y no
# devolvía las fuentes, así que no se podía auditar la respuesta.
if __name__ == "__main__":
    print("\n¡El sistema RAG para EcoMarket está listo!")
    print("Escribe una pregunta y presiona Enter. Escribe 'salir' para terminar.")

    while True:
        pregunta = input("\nTu pregunta: ")
        if pregunta.lower() == "salir":
            break

        print("Buscando y generando respuesta...")
        resultado = qa_chain.invoke(pregunta)

        print("\nRespuesta del Asistente:\n")
        print(resultado["respuesta"])
        print("\nFuentes:")
        for documento in resultado["documentos"]:
            # El chunk empieza con el título, que ya es la fuente: se muestra lo que sigue.
            fuente = documento.metadata.get("fuente", "")
            texto = documento.page_content.strip().removeprefix(f"{fuente}:").strip()
            print(f"  · {fuente}: {texto[:80]}…")


# -- Qué cambió y por qué -------------------------------------------------------------------------------
# | Paso | Original                                 | Modernizado                                  | Por qué                                                                  |
# |------|------------------------------------------|----------------------------------------------|--------------------------------------------------------------------------|
# | 0    | Imports de langchain/langchain_community | langchain_text_splitters, langchain_ollama,  | Rutas de LangChain 1.x; RetrievalQA pasó a langchain-classic (obsoleto)  |
# |      | (TextLoader y os importados sin usar)    | langchain_chroma, langchain_core             |                                                                          |
# | 1    | String con la política                   | Igual                                        | (el paquete del taller usa 4 documentos en 4 formatos)                  |
# | 2    | OllamaEmbeddings("llama2")               | embeddinggemma con prefijos de tarea         | Un LLM de chat no es un modelo de embeddings; sin prefijos se degrada    |
# | 2, 5 | try/except al construir los objetos      | Prueba de conexión donde ocurre              | Construir el objeto no se conecta: el error salía después, en el paso 4  |
# | 3    | Recursive(1000, 200)                     | Igual, mostrando que sale 1 chunk            | Con un documento corto la recuperación es trivial                        |
# | 4    | Chroma.from_documents en memoria         | Igual (langchain_chroma)                     | Prototipo; el taller usa pgvector persistente e idempotente              |
# | 5    | Ollama("llama2")                         | ChatOllama(Gemma 4, reasoning=False)         | Modelo actual, mejor español; sin razonamiento la respuesta tarda menos  |
# | 6    | RetrievalQA "stuff", prompt por defecto  | Cadena LCEL explícita con prompt propio      | Eslabones visibles, prompt en español y fuentes en el resultado          |
# | 6    | as_retriever() sin k explícito           | search_kwargs={"k": 4}                       | El mismo valor por defecto (4), pero visible                             |
# | 7    | qa_chain.run(pregunta)                   | qa_chain.invoke(pregunta) + fuentes          | .run está obsoleto y no devolvía las fuentes                             |
