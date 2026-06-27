"""
Script de test simple pour vérifier votre connexion à Microsoft Foundry
"""

import os
import sys
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv(".env.test")

PROJECT_ENDPOINT = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
API_KEY = os.getenv("FOUNDRY_API_KEY")

print("=" * 80)
print("🧪 TEST DE CONNEXION À MICROSOFT FOUNDRY")
print("=" * 80)

# Vérifier que les variables sont présentes
print("\n1️⃣ Vérification des credentials...")
if not PROJECT_ENDPOINT:
    print("❌ FOUNDRY_PROJECT_ENDPOINT non trouvé dans .env.test")
    sys.exit(1)
if not API_KEY:
    print("❌ FOUNDRY_API_KEY non trouvée dans .env.test")
    sys.exit(1)

print(f"✓ PROJECT_ENDPOINT: {PROJECT_ENDPOINT}")
print(f"✓ API_KEY: {API_KEY[:20]}...***")

# Essayer de créer le client OpenAI pour Foundry
print("\n2️⃣ Tentative de connexion à Foundry avec OpenAI client...")
try:
    from openai import AzureOpenAI
    
    # Créer le client OpenAI configuré pour Foundry
    openai_client = AzureOpenAI(
        api_key=API_KEY,
        azure_endpoint=PROJECT_ENDPOINT,
        api_version="2024-05-01-preview"
    )
    print("✓ Client OpenAI créé avec succès")
    
except ImportError:
    print("❌ Librairie 'openai' non installée")
    print("   Installez avec: pip install openai")
    sys.exit(1)
except Exception as e:
    print(f"❌ Erreur de connexion: {e}")
    sys.exit(1)

# Tester les embeddings
print("\n3️⃣ Test des embeddings...")
try:
    test_text = "Ceci est un test d'embedding"
    response = openai_client.embeddings.create(
        model="text-embedding-3-large",
        input=test_text,
    )
    
    embedding = response.data[0].embedding
    print(f"✓ Embedding créé avec succès ({len(embedding)} dimensions)")
    print(f"  Premiers éléments: {embedding[:3]}")
    
except Exception as e:
    print(f"❌ Erreur lors de l'embedding: {e}")
    print(f"   Message complet: {str(e)}")
    sys.exit(1)

# Tester le chat
print("\n4️⃣ Test du chat...")
try:
    response = openai_client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "Tu es un assistant utile."},
            {"role": "user", "content": "Dis simplement 'RAG fonctionne!' en une phrase."},
        ],
        temperature=0.2,
        max_tokens=50,
    )
    
    answer = response.choices[0].message.content
    print(f"✓ Chat fonctionne!")
    print(f"  Réponse: {answer}")
    
except Exception as e:
    print(f"❌ Erreur lors du chat: {e}")
    print(f"   Message complet: {str(e)}")
    sys.exit(1)

print("\n" + "=" * 80)
print("✅ TOUS LES TESTS SONT PASSÉS - VOTRE CONFIGURATION EST CORRECTE!")
print("=" * 80)
print("\nVous pouvez maintenant utiliser votre RAG. 🚀")
