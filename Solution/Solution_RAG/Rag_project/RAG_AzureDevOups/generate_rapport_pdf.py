"""
Génère le rapport PDF du projet RAG NordTrail Gear.
Usage: python generate_rapport_pdf.py
"""

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUTPUT = Path(__file__).parent / "Rapport_RAG_NordTrail_Gear.pdf"

TEAM = [
    "Simon Delepine (SDEL28070300)",
    "Thomas Gourjault (GOUT24110300)",
    "Matthis Lahargoue (LAHM11100200)",
    "Marin Boehm (BOEM27080300)",
]

# Colors
GREEN_DARK = colors.HexColor("#1B3D2F")
GREEN_MID = colors.HexColor("#2D6A4F")
GRAY = colors.HexColor("#555555")
LIGHT_BG = colors.HexColor("#F4F7F5")


def build_styles():
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontSize=22,
            textColor=GREEN_DARK,
            spaceAfter=12,
            alignment=TA_CENTER,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontSize=12,
            textColor=GREEN_MID,
            alignment=TA_CENTER,
            spaceAfter=20,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontSize=16,
            textColor=GREEN_DARK,
            spaceBefore=18,
            spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontSize=13,
            textColor=GREEN_MID,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["Normal"],
            fontSize=10,
            leading=13,
            leftIndent=14,
            bulletIndent=0,
            spaceAfter=4,
        ),
        "code": ParagraphStyle(
            "Code",
            parent=base["Code"],
            fontSize=8,
            leading=10,
            backColor=LIGHT_BG,
            leftIndent=6,
            rightIndent=6,
        ),
        "caption": ParagraphStyle(
            "Caption",
            parent=base["Normal"],
            fontSize=8,
            textColor=GRAY,
            alignment=TA_CENTER,
        ),
    }
    return styles


def bullet_list(items: list[str], style) -> list:
    return [Paragraph(f"• {item}", style) for item in items]


def make_table(headers: list[str], rows: list[list[str]], col_widths=None):
    data = [headers] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), GREEN_DARK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def code_block(text: str, style) -> Preformatted:
    return Preformatted(text.strip(), style, maxLineLength=95)


def build_story(styles):
    s = styles
    story = []

    # ---- Page de titre ----
    story.append(Spacer(1, 2 * cm))
    story.append(Paragraph("Rapport de projet", s["title"]))
    story.append(Paragraph("RAG — NordTrail Gear", s["title"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            "Retrieval Augmented Generation avec Azure OpenAI et Azure AI Search",
            s["subtitle"],
        )
    )
    story.append(Paragraph("Cours IA — UQAC", s["subtitle"]))
    story.append(Paragraph(f"Date : {date.today().strftime('%d %B %Y')}", s["subtitle"]))
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph("<b>Équipe</b>", s["h2"]))
    for member in TEAM:
        story.append(Paragraph(member, s["body"]))
    story.append(PageBreak())

    # ---- Table des matières (manuelle) ----
    story.append(Paragraph("Table des matières", s["h1"]))
    toc = [
        "1. Introduction",
        "2. Contexte et objectifs",
        "3. Architecture du système",
        "4. Structure du dépôt et modules",
        "5. Corpus documentaire",
        "6. Pipeline d'ingestion",
        "7. Pipeline de requête RAG",
        "8. Configuration et déploiement",
        "9. Tests et validation",
        "10. Conclusion et perspectives",
    ]
    story.extend(bullet_list(toc, s["bullet"]))
    story.append(PageBreak())

    # ---- 1. Introduction ----
    story.append(Paragraph("1. Introduction", s["h1"]))
    story.append(
        Paragraph(
            "Ce rapport présente le travail réalisé dans le cadre du cours IA à l'UQAC : "
            "la conception et l'implémentation d'un système RAG (Retrieval Augmented Generation) "
            "pour l'entreprise fictive <b>NordTrail Gear</b>, spécialisée en équipement outdoor "
            "(randonnée, trail, camping). Le système permet de répondre aux questions clients "
            "en s'appuyant sur une base documentaire interne plutôt que sur les connaissances "
            "générales du modèle de langage.",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "Le RAG combine deux étapes : la <b>récupération</b> de passages pertinents dans "
            "des documents indexés, puis la <b>génération</b> d'une réponse par un LLM "
            "conditionné par ce contexte. Cette approche réduit les hallucinations et garantit "
            "que les réponses reflètent les politiques réelles de l'entreprise (livraison, "
            "tailles, SAV, annulations).",
            s["body"],
        )
    )

    # ---- 2. Contexte ----
    story.append(Paragraph("2. Contexte et objectifs", s["h1"]))
    story.append(Paragraph("2.1 Problématique métier", s["h2"]))
    story.extend(
        bullet_list(
            [
                "Volume de courriels clients sur la livraison, les retours, les tailles et le SAV.",
                "Documents dispersés (FAQ, guides, procédures internes, catalogue, données JSON).",
                "Besoin d'un assistant capable de citer les règles applicables à chaque situation.",
            ],
            s["bullet"],
        )
    )
    story.append(Paragraph("2.2 Objectifs techniques", s["h2"]))
    story.extend(
        bullet_list(
            [
                "Indexer automatiquement des fichiers PDF, Markdown, CSV et JSON.",
                "Découper les textes en chunks adaptés à la recherche vectorielle.",
                "Stocker des embeddings et interroger un index par similarité sémantique.",
                "Produire des réponses via Azure OpenAI en injectant le contexte récupéré.",
                "Proposer une voie locale (ChromaDB) pour développer sans coût cloud à chaque test.",
            ],
            s["bullet"],
        )
    )

    # ---- 3. Architecture ----
    story.append(Paragraph("3. Architecture du système", s["h1"]))
    story.append(
        Paragraph(
            "Le projet expose <b>deux pipelines complémentaires</b> partageant le même dossier "
            "source <i>documents/</i> mais différant par le stockage vectoriel et la stratégie de chunking.",
            s["body"],
        )
    )
    story.append(Paragraph("3.1 Pipeline Azure (production)", s["h2"]))
    story.append(
        code_block(
            """
documents/  -->  ingest_azure.py  -->  Azure OpenAI (embeddings)
                         |
                         v
                 Azure AI Search (index vectoriel)
                         |
                         v
              rag_test.py : question --> retrieve --> LLM --> réponse
            """,
            s["code"],
        )
    )
    story.append(Paragraph("3.2 Pipeline local Chroma (développement)", s["h2"]))
    story.append(
        code_block(
            """
documents/  -->  utils.py (load, clean, chunk par mots)
                         |
                         v
              ingest.py --> embeddings.py --> vectorstore.py (ChromaDB)
            """,
            s["code"],
        )
    )
    story.append(
        Paragraph(
            "<b>Différence importante :</b> <i>ingest_azure.py</i> découpe le texte par "
            "<b>caractères</b> (CHUNK_SIZE=1500, overlap=150). Le pipeline local via "
            "<i>utils.chunk_text()</i> découpe par <b>mots</b>, ce qui préserve mieux "
            "l'intégrité des phrases lors du prototypage.",
            s["body"],
        )
    )

    # ---- 4. Modules ----
    story.append(PageBreak())
    story.append(Paragraph("4. Structure du dépôt et modules Python", s["h1"]))
    story.append(
        make_table(
            ["Fichier", "Rôle", "Fonctions clés"],
            [
                [
                    "config.py",
                    "Configuration",
                    "Charge .env ; valide OPENAI_API_KEY et SEARCH_API_KEY ; "
                    "paramètres chunk, chemins, noms de modèles.",
                ],
                [
                    "utils.py",
                    "Prétraitement",
                    "load_document_text() multi-formats ; clean_text() ; "
                    "chunk_text() par mots ; list_document_files().",
                ],
                [
                    "embeddings.py",
                    "Vectorisation",
                    "Client AzureOpenAI ; get_embedding() / get_embeddings().",
                ],
                [
                    "vectorstore.py",
                    "Stockage local",
                    "ChromaDB persistant ; reset_collection() ; query_collection() ; cosine.",
                ],
                [
                    "ingest.py",
                    "Ingestion locale",
                    "Orchestre utils + embeddings + Chroma ; exclut emails_clients_test.csv.",
                ],
                [
                    "ingest_azure.py",
                    "Ingestion cloud",
                    "Extracteurs PDF/MD/CSV/JSON ; chunk caractères ; upload Azure Search.",
                ],
                [
                    "rag_test.py",
                    "Requête RAG",
                    "VectorizedQuery ; recherche hybride ; prompt + chat completions.",
                ],
                [
                    "test_foundry.py",
                    "Diagnostic",
                    "Test connexion Microsoft Foundry via .env.test.",
                ],
            ],
            col_widths=[3.2 * cm, 2.8 * cm, 10.5 * cm],
        )
    )
    story.append(Spacer(1, 12))

    story.append(Paragraph("4.1 config.py — Configuration centralisée", s["h2"]))
    story.append(
        Paragraph(
            "Toutes les variables sensibles proviennent d'un fichier <i>.env</i> (jamais versionné). "
            "Les paramètres couvrent Azure OpenAI (clé, endpoint, version API, noms de déploiements "
            "embedding et chat), Azure AI Search (endpoint, clé, nom d'index) et Chroma "
            "(chemin ./db/chroma_store, collection nordtrail_documents). La fonction "
            "<i>validate_config()</i> interrompt l'exécution si des clés essentielles manquent.",
            s["body"],
        )
    )

    story.append(Paragraph("4.2 utils.py — Chargement et découpage", s["h2"]))
    story.extend(
        bullet_list(
            [
                "PDF : extraction page par page avec pypdf, préfixe [Page N].",
                "Markdown / TXT : lecture UTF-8 directe.",
                "CSV : chaque ligne convertie en texte clé:valeur lisible.",
                "JSON : sérialisation indentée (listes ou objet unique).",
                "Nettoyage : suppression \\x00, espaces multiples, lignes vides excessives.",
            ],
            s["bullet"],
        )
    )

    story.append(Paragraph("4.3 embeddings.py et vectorstore.py", s["h2"]))
    story.append(
        Paragraph(
            "<i>embeddings.py</i> instancie un client Azure OpenAI et appelle le déploiement "
            "configuré (ex. mon-embedding). La version initiale traite les textes un par un "
            "pour faciliter le débogage. <i>vectorstore.py</i> encapsule ChromaDB en mode "
            "persistant avec distance cosine, adaptée aux embeddings OpenAI (typiquement 1536 dimensions).",
            s["body"],
        )
    )

    story.append(Paragraph("4.4 ingest.py — Ingestion locale", s["h2"]))
    story.append(
        Paragraph(
            "Pour chaque fichier du dossier documents/ (sauf exclusions), le script charge le texte, "
            "le nettoie, le découpe, génère les embeddings et les enregistre avec métadonnées "
            "(source, type, chunk_index, chunk_id). La collection est réinitialisée à chaque "
            "ingestion complète via <i>reset_collection()</i>. Fichier exclu explicitement : "
            "<i>emails_clients_test.csv</i>, réservé à l'évaluation et non à l'indexation.",
            s["body"],
        )
    )

    story.append(Paragraph("4.5 ingest_azure.py — Ingestion cloud", s["h2"]))
    story.extend(
        bullet_list(
            [
                "Extracteurs dédiés par extension (.pdf, .md, .csv, .json).",
                "Chunking par fenêtre glissante en caractères (config CHUNK_SIZE / CHUNK_OVERLAP).",
                "Vectorisation via Azure OpenAI puis upload_documents() vers l'index Azure AI Search.",
                "Identifiant de chunk : {nom_fichier}_chunk_{i} ; texte préfixé par le nom du fichier.",
            ],
            s["bullet"],
        )
    )

    story.append(Paragraph("4.6 rag_test.py — Boucle RAG complète", s["h2"]))
    story.append(
        Paragraph(
            "Le script charge <i>.env.test</i>, configure les clients Search et OpenAI, puis pour "
            "chaque question : (1) vectorise la question, (2) construit une VectorizedQuery sur "
            "le champ vector, (3) exécute une recherche hybride (texte + vecteur), (4) assemble "
            "un prompt « réponds strictement avec le contexte », (5) appelle le modèle chat. "
            "Dix questions types couvrent livraison France, frais Belgique, colis endommagé, "
            "tailles trail, point relais, etc.",
            s["body"],
        )
    )

    # ---- 5. Corpus ----
    story.append(PageBreak())
    story.append(Paragraph("5. Corpus documentaire", s["h1"]))
    story.append(
        make_table(
            ["Fichier", "Type", "Statut", "Contenu principal"],
            [
                ["faq_livraison.md", "Markdown", "Indexé", "Zones, délais, frais, colis endommagé, point relais"],
                ["guide_tailles.md", "Markdown", "Indexé", "Vestes, pantalons, chaussures trail, sacs, gants"],
                ["procedure_sav_interne.md", "Markdown", "Indexé", "Procédure SAV, escalade, traçabilité"],
                ["conditions_annulation.md", "Markdown", "Indexé", "Annulation, modification, retours"],
                ["catalogue_produits.csv", "CSV", "Indexé", "Produits, prix, tailles, garantie, notes"],
                ["clients_exemples.json", "JSON", "Indexé", "Profils clients fictifs (CL-001, etc.)"],
                ["commandes_exemples.json", "JSON", "Indexé", "Commandes, statuts, tracking, montants"],
                ["emails_clients_test.csv", "CSV", "Exclu", "14 scénarios d'évaluation RAG (intents attendus)"],
            ],
            col_widths=[4.2 * cm, 2 * cm, 1.8 * cm, 8.5 * cm],
        )
    )
    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            "Les documents Markdown sont structurés (version, date, objectif) et rédigés "
            "explicitement pour alimenter le service client et l'assistant RAG. Le fichier "
            "<i>emails_clients_test.csv</i> contient pour chaque courriel : sujet, corps, "
            "intent attendu, documents attendus et résumé de réponse — il sert de jeu de test "
            "sans polluer l'index de recherche.",
            s["body"],
        )
    )

    # ---- 6. Ingestion ----
    story.append(Paragraph("6. Pipeline d'ingestion — fonctionnement détaillé", s["h1"]))
    story.append(Paragraph("6.1 Étapes communes", s["h2"]))
    story.extend(
        bullet_list(
            [
                "Extraction du texte brut selon le format du fichier.",
                "Nettoyage (caractères invalides, normalisation des espaces).",
                "Découpage en chunks avec chevauchement pour ne pas perdre le contexte aux frontières.",
                "Génération d'embeddings (vecteurs numériques représentant le sens du passage).",
                "Stockage dans l'index avec identifiant unique et métadonnées de traçabilité.",
            ],
            s["bullet"],
        )
    )
    story.append(Paragraph("6.2 Commande d'ingestion Azure", s["h2"]))
    story.append(code_block("python ingest_azure.py", s["code"]))
    story.append(
        Paragraph(
            "Sortie attendue : liste des fichiers traités, nombre de chunks par document, "
            "total de chunks indexés dans Azure AI Search.",
            s["body"],
        )
    )
    story.append(Paragraph("6.3 Commande d'ingestion locale", s["h2"]))
    story.append(code_block("python ingest.py", s["code"]))

    # ---- 7. Requête RAG ----
    story.append(Paragraph("7. Pipeline de requête RAG", s["h1"]))
    story.append(
        Paragraph(
            "Lorsqu'un utilisateur pose une question, le système ne répond pas directement "
            "depuis le modèle. Il cherche d'abord les passages les plus proches sémantiquement "
            "dans l'index, puis construit un prompt du type :",
            s["body"],
        )
    )
    story.append(
        code_block(
            'Tu es un assistant basé sur des documents. Réponds strictement en utilisant '
            "le contexte suivant.\nContexte : {passages récupérés}\nQuestion : {question}",
            s["code"],
        )
    )
    story.append(
        Paragraph(
            "La recherche dans <i>rag_test.py</i> combine recherche textuelle et requête "
            "vectorielle (VectorizedQuery, k_nearest_neighbors configurable). Le paramètre "
            "<i>top</i> contrôle le nombre de documents retournés (souvent 1 en test, extensible à 3+).",
            s["body"],
        )
    )

    # ---- 8. Config ----
    story.append(PageBreak())
    story.append(Paragraph("8. Configuration et déploiement", s["h1"]))
    story.append(Paragraph("8.1 Variables d'environnement (.env)", s["h2"]))
    story.append(
        make_table(
            ["Variable", "Description"],
            [
                ["AZURE_OPENAI_API_KEY", "Clé API Azure OpenAI"],
                ["AZURE_OPENAI_ENDPOINT", "Endpoint régional (ex. canadacentral)"],
                ["AZURE_OPENAI_EMBEDDING_MODEL", "Nom du déploiement embedding"],
                ["AZURE_OPENAI_CHAT_MODEL", "Nom du déploiement chat"],
                ["AZURE_SEARCH_API_KEY", "Clé admin Azure AI Search"],
                ["AZURE_SEARCH_ENDPOINT", "URL du service Search"],
                ["AZURE_SEARCH_INDEX_NAME", "Nom de l'index (index-rag-canadien)"],
                ["CHUNK_SIZE / CHUNK_OVERLAP", "Paramètres de découpage (caractères, pipeline Azure)"],
                ["DOCUMENTS_FOLDER", "Chemin vers ./documents"],
            ],
            col_widths=[5.5 * cm, 11 * cm],
        )
    )
    story.append(Spacer(1, 12))
    story.append(Paragraph("8.2 Mise en route", s["h2"]))
    story.extend(
        bullet_list(
            [
                "Copier .env.example vers .env et renseigner les clés Azure.",
                "Installer les dépendances : openai, azure-search-documents, chromadb, pypdf, python-dotenv, etc.",
                "Ingérer : python ingest_azure.py",
                "Tester : python rag_test.py",
                "Option : python test_foundry.py pour valider Microsoft Foundry.",
            ],
            s["bullet"],
        )
    )
    story.append(
        Paragraph(
            "La documentation SETUP.md décrit également les commandes Azure CLI pour "
            "récupérer endpoints et clés depuis le portail ou la ligne de commande.",
            s["body"],
        )
    )

    # ---- 9. Tests ----
    story.append(Paragraph("9. Tests et validation", s["h1"]))
    story.append(Paragraph("9.1 Questions intégrées dans rag_test.py", s["h2"]))
    story.extend(
        bullet_list(
            [
                "Délais de livraison standard en France métropolitaine.",
                "Montant minimum pour livraison offerte en France.",
                "Procédure si colis arrivé endommagé.",
                "Choix de taille pour chaussures de trail (espace devant les orteils).",
                "Frais de livraison en Belgique, délai point relais.",
                "Volume de sac recommandé pour randonnée à la journée.",
            ],
            s["bullet"],
        )
    )
    story.append(Paragraph("9.2 Jeu d'évaluation emails_clients_test.csv", s["h2"]))
    story.append(
        Paragraph(
            "Quatorze scénarios de courriels clients avec intents (demande_retour, "
            "annulation_commande, modification_adresse, question_douane, demande_garantie, "
            "echange_taille, etc.) et documents attendus. Ce fichier permet d'évaluer "
            "la pertinence des réponses RAG sans l'inclure dans l'index.",
            s["body"],
        )
    )

    # ---- 10. Conclusion ----
    story.append(Paragraph("10. Conclusion et perspectives", s["h1"]))
    story.append(Paragraph("10.1 Bilan", s["h2"]))
    story.extend(
        bullet_list(
            [
                "Système RAG de bout en bout : ingestion multi-formats, index vectoriel, génération conditionnée.",
                "Architecture modulaire et secrets externalisés dans .env.",
                "Double voie Azure / Chroma pour production et prototypage.",
                "Corpus métier cohérent pour un cas e-commerce outdoor réaliste.",
            ],
            s["bullet"],
        )
    )
    story.append(Paragraph("10.2 Limites actuelles", s["h2"]))
    story.extend(
        bullet_list(
            [
                "Embeddings générés séquentiellement (lent sur gros volumes).",
                "top-k souvent fixé à 1 — contexte parfois insuffisant.",
                "Deux stratégies de chunking différentes entre pipelines local et Azure.",
                "Pas encore d'interface utilisateur ni de métriques automatiques sur le CSV de test.",
            ],
            s["bullet"],
        )
    )
    story.append(Paragraph("10.3 Pistes d'amélioration", s["h2"]))
    story.extend(
        bullet_list(
            [
                "Batch embeddings et monitoring des coûts API.",
                "Augmenter top-k et fusion de plusieurs chunks dans le prompt.",
                "Interface Streamlit ou API REST pour démonstration.",
                "Scoring automatique (précision intent, citation des bons documents).",
                "Harmonisation du chunking et métadonnées source dans l'index Azure.",
            ],
            s["bullet"],
        )
    )

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1, color=GREEN_MID))
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            f"Rapport généré automatiquement — Projet RAG_AzureDevOups — {date.today().isoformat()}",
            s["caption"],
        )
    )

    return story


def main():
    styles = build_styles()
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="Rapport RAG NordTrail Gear",
        author="Équipe UQAC — Cours IA",
    )

    def on_page(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GRAY)
        canvas.drawString(2 * cm, 1.2 * cm, f"RAG NordTrail Gear — {date.today().year}")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(build_story(styles), onFirstPage=on_page, onLaterPages=on_page)
    print(f"Rapport PDF créé : {OUTPUT}")
    print(f"Pages : {doc.page}")


if __name__ == "__main__":
    main()
