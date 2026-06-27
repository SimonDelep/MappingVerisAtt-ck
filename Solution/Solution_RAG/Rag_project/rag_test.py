


import os
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchField, SearchFieldDataType, 
    VectorSearch, VectorSearchProfile, HnswAlgorithmConfiguration
)
# Correction : Ajout du modèle requis pour exécuter la requête vectorielle
from azure.search.documents.models import VectorizedQuery
from openai import AzureOpenAI



load_dotenv(".env.test")

OPENAI_KEY = os.getenv("OPENAI_KEY")
SEARCH_KEY = os.getenv("SEARCH_KEY")
OPENAI_ENDPOINT = os.getenv("OPENAI_ENDPOINT")
SEARCH_ENDPOINT = os.getenv("SEARCH_ENDPOINT")
INDEX_NAME = os.getenv("INDEX_NAME")


# Initialisation des clients Azure
ai_client = AzureOpenAI(api_key=OPENAI_KEY, api_version="2024-02-01", azure_endpoint=OPENAI_ENDPOINT)
index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=AzureKeyCredential(SEARCH_KEY))
search_client = SearchClient(endpoint=SEARCH_ENDPOINT, index_name=INDEX_NAME, credential=AzureKeyCredential(SEARCH_KEY))

def configurer_base_vectorielle():
    """Crée l'index vectoriel dans Azure AI Search si inexistant."""
    try:
        index_client.get_index(INDEX_NAME)
        print("L'index vectoriel existe déjà.")
    except Exception:
        print("Création de l'index vectoriel...")
        champs = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchField(name="text", type=SearchFieldDataType.String, searchable=True),
            SearchField(name="vector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                        searchable=True, vector_search_dimensions=1536, vector_search_profile_name="mon-profil-hnsw")
        ]
        vector_search = VectorSearch(
            profiles=[VectorSearchProfile(name="mon-profil-hnsw", algorithm_configuration_name="mon-algo-hnsw")],
            algorithms=[HnswAlgorithmConfiguration(name="mon-algo-hnsw")]
        )
        index = SearchIndex(name=INDEX_NAME, fields=champs, vector_search=vector_search)
        index_client.create_index(index)
        print("Index créé avec succès !")

def vectoriser_texte(texte):
    """Convertit une chaîne de caractères en vecteur numérique via text-embedding-3-small."""
    res = ai_client.embeddings.create(input=[texte], model="mon-embedding")
    return res.data[0].embedding

def ajouter_document_test():
    """Ajoute un document exemple indexé dans votre RAG."""
    texte_doc = "La politique officielle de l'UQAC autorise jusqu'à deux jours de télétravail par semaine pour le personnel administratif."
    vecteur = vectoriser_texte(texte_doc)
    
    search_client.upload_documents(documents=[{
        "id": "1",
        "text": texte_doc,
        "vector": vecteur
    }])
    print("Document de test indexé avec succès !")

def interroger_rag(question):
    """Recherche le contexte pertinent et génère la réponse finale."""
    vecteur_question = vectoriser_texte(question)
    
    # Correction : Construction conforme de la requête vectorielle avec le paramètre 'kind' implicite
    requete_vectorielle = VectorizedQuery(
        vector=vecteur_question, 
        k_nearest_neighbors=1, 
        fields="vector"
    )
    
    # Recherche hybride/vectorielle dans Azure AI Search
    resultats = search_client.search(
        search_text=question,
        vector_queries=[requete_vectorielle],
        top=1
    )
    
    # Extraction du document trouvé
    docs_trouves = [doc['text'] for doc in resultats]
    contexte = docs_trouves[0] if docs_trouves else "Aucun document pertinent trouvé."
    
    # Soumission au LLM
    prompt = f"Tu es un assistant basé sur des documents. Réponds strictement en utilisant le contexte suivant.\nContexte : {contexte}\nQuestion : {question}"
    completion = ai_client.chat.completions.create(
        model="mon-llm-chat",
        messages=[{"role": "user", "content": prompt}]
    )
    return completion.choices[0].message.content

if __name__ == "__main__":
    configurer_base_vectorielle()
    
    print("\n" + "=" * 80)
    print("🚀 TEST DU RAG - Questions liées aux documents NordTrail Gear")
    print("=" * 80)
    
    questions = [
        "Quels sont les délais de livraison standard en France métropolitaine ?",
        "À partir de quel montant d'achat la livraison est-elle offerte en France ?",
        "Que faire si un colis arrive endommagé ?",
        "Comment choisir la bonne taille pour des chaussures de trail ?",
        "Quels sont les frais de livraison standard en Belgique ?",
        "Quel est le délai de garde d'un colis en point relais ?",
        "Combien d'espace doit-on garder devant les orteils avec des chaussures de trail ?",
        "Que faire si ma commande est indiquée livrée mais je ne l'ai pas reçue ?",
        "Quels sont les délais de préparation après validation du paiement ?",
        "Quel volume de sac à dos est recommandé pour une randonnée à la journée ?"
    ]
    
    for i, question in enumerate(questions, 1):
        print(f"\n📌 Question {i}: {question}")
        try:
            reponse = interroger_rag(question)
            print(f"✅ Réponse: {reponse}")
        except Exception as e:
            print(f"❌ Erreur: {e}")
    
    print("\n" + "=" * 80)
    print("✅ Tests terminés")
    print("=" * 80)