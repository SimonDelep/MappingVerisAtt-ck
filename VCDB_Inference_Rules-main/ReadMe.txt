Description du projet : Analyse de la VCDB

Ce projet analyse la base de données d'incidents de cybersécurité VCDB (VERIS Community Database) pour identifier des corrélations entre différentes techniques d'attaque. Il utilise l'algorithme FP-Growth pour extraire des règles d'association et effectue un mapping dynamique avec la base MITRE ATT&CK pour suggérer des remédiations techniques.

## Fonctionnalités
Minage de données : Identification des techniques qui apparaissent souvent ensemble (ex: Phishing + C2 + Ransomware).
Clustering : Groupement des règles par scénarios types (Scénarios d'attaque).
Liaison MITRE ATT&CK : Traduction automatique du vocabulaire VERIS vers les IDs MITRE (T1xxx) via un fichier de mapping officiel.
Remédiations Dynamiques : Récupération en temps réel des descriptions de remédiation depuis le JSON officiel de MITRE.
Documentations : Export Excel incluant le nombre d'incidents réels et la liste des IDs d'incidents correspondants.

##  Arborescence du Projet
Pour que le script fonctionne, le dossier doit être organisé comme suit :

Doc/				   # Votre dossier qui contient toutes les ressources incluant VCDB , script etc ...    
├── VCDB/                         # Dossier VCDB cloné ou téléchargé												   /!\ à télécharger de vôtre coté
│   └── data/
│       └── json/
│           └── validated/        # Contient les milliers de fichiers .json que nous cherchons à analyser
├── Python_FPgrowth/              # Script qui analyse la VCDB
│   ├── Analyse_VCDB.xlsx         # Fichier de sortie (crée par le script)
│   ├── .gitignore                
│   └── README.md                 # Ce fichier
└── veris_mitre_mapping.csv   	   # Le fichier de mapping VERIS/MITRE												   /!\ à télécharger de vôtre coté

Si vous souhaitez avoir une arboréscence différente , veuillez faire attention à modifier les chemins d'accès des 2 éléments avec le symbol /!\.


Bibliothèques nécessaires :

- pandas 
- mlxtend 
- scikit-learn 
- openpyxl 
- requests

commande : python -m pip install pandas mlxtend scikit-learn openpyxl requests

Ensuite exectutez simplement le code , vous aurez des informations basiques affichées dans le terminal ensuite un fichier excel seras crée où les informations les plus détaillées s'y trouvent.
Dans ce excel nous retrouvons les colones comme suit : ID_GROUPE, SCÉNARIO_TYPE, ANTÉCÉDENTS, CONSÉQUENTS, NB_INCIDENTS, LISTE_ID_INCIDENTS, MITRE_ID, ACTIONS_RECOMMANDÉES, lift.