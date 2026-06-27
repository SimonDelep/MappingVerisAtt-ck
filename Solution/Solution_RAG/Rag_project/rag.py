import config

from embeddings import get_azure_client
from retrieve import retrieve


OPENAI_CHAT_MODEL = getattr(config, "OPENAI_CHAT_MODEL", None)
TOP_K = int(getattr(config, "TOP_K", 5))


def build_context(retrieved_chunks: list[dict]) -> str:
    """
    Construit le contexte documentaire injecté dans le prompt.
    Chaque chunk garde sa source pour assurer la traçabilité.
    """
    context_parts = []

    for index, chunk in enumerate(retrieved_chunks, start=1):
        metadata = chunk.get("metadata", {})
        source = metadata.get("source", "source inconnue")
        chunk_id = metadata.get("chunk_id", chunk.get("id", "chunk inconnu"))
        document = chunk.get("document", "")

        context_parts.append(
            f"[Source {index}]\n"
            f"Document : {source}\n"
            f"Chunk : {chunk_id}\n"
            f"Contenu :\n{document}"
        )

    return "\n\n".join(context_parts)


def get_unique_sources(retrieved_chunks: list[dict]) -> list[str]:
    """
    Retourne la liste unique des documents utilisés.
    """
    sources = []

    for chunk in retrieved_chunks:
        metadata = chunk.get("metadata", {})
        source = metadata.get("source", "source inconnue")

        if source not in sources:
            sources.append(source)

    return sources


def generate_answer(question: str, context: str, sources: list[str]) -> str:
    """
    Génère une réponse client à partir du contexte récupéré.
    """
    if not OPENAI_CHAT_MODEL:
        raise ValueError(
            "OPENAI_CHAT_MODEL est manquant. Vérifie AZURE_OPENAI_CHAT_DEPLOYMENT dans dev.env."
        )

    client = get_azure_client()

    system_prompt = """
Tu es un assistant de service client pour NordTrail Gear.

Ton rôle :
- répondre aux courriels clients ;
- utiliser uniquement les informations présentes dans le contexte documentaire ;
- rester clair, professionnel et direct ;
- ne pas inventer de règle ;
- ne pas promettre un remboursement, une annulation ou une garantie si les documents ne le permettent pas ;
- demander les informations manquantes si nécessaire ;
- recommander une escalade vers un agent humain en cas de doute, litige, fraude ou cas ambigu.

Tu dois produire une réponse prête à être envoyée au client.
""".strip()

    user_prompt = f"""
Contexte documentaire récupéré :

{context}

Courriel ou question client :

{question}

Sources disponibles :
{", ".join(sources)}

Rédige une réponse claire au client.

Contraintes :
- réponds uniquement avec les informations du contexte ;
- si le contexte est insuffisant, dis qu'une vérification par le service client est nécessaire ;
- mentionne à la fin les sources utilisées sous la forme :
Sources utilisées :
- nom_du_document
""".strip()

    response = client.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content


def rag_query(question: str, top_k: int = TOP_K) -> dict:
    """
    Pipeline RAG complet :
    1. reçoit une question client ;
    2. récupère les chunks pertinents ;
    3. construit le contexte ;
    4. génère une réponse ;
    5. retourne la réponse avec les sources.
    """
    if not question or not question.strip():
        raise ValueError("La question ne peut pas être vide.")

    retrieved_chunks = retrieve(query=question, top_k=top_k)

    if not retrieved_chunks:
        return {
            "question": question,
            "answer": (
                "Je n’ai pas trouvé d’information suffisante dans la base documentaire. "
                "Cette demande doit être vérifiée par un agent du service client."
            ),
            "sources": [],
            "retrieved_chunks": [],
        }

    context = build_context(retrieved_chunks)
    sources = get_unique_sources(retrieved_chunks)

    answer = generate_answer(
        question=question,
        context=context,
        sources=sources,
    )

    return {
        "question": question,
        "answer": answer,
        "sources": sources,
        "retrieved_chunks": retrieved_chunks,
    }


def print_rag_result(result: dict) -> None:
    """
    Affiche proprement le résultat du RAG.
    """
    print("\n" + "=" * 80)
    print("Réponse générée")
    print("=" * 80)
    print(result["answer"])

    print("\n" + "=" * 80)
    print("Sources récupérées")
    print("=" * 80)

    if not result["sources"]:
        print("Aucune source récupérée.")
    else:
        for source in result["sources"]:
            print(f"- {source}")

    print("\n" + "=" * 80)
    print("Chunks utilisés")
    print("=" * 80)

    for index, chunk in enumerate(result["retrieved_chunks"], start=1):
        metadata = chunk.get("metadata", {})
        source = metadata.get("source", "source inconnue")
        chunk_id = metadata.get("chunk_id", chunk.get("id", "chunk inconnu"))
        distance = chunk.get("distance", "N/A")

        print(f"{index}. {source} | {chunk_id} | distance = {distance}")


if __name__ == "__main__":
    print("=" * 80)
    print("RAG NordTrail Gear — Service client")
    print("=" * 80)

    question = input("\nCourriel ou question client : ").strip()

    result = rag_query(question=question, top_k=TOP_K)

    print_rag_result(result)
