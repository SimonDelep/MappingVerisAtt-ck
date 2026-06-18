import os
import json
import pandas as pd
import requests
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import fpgrowth, association_rules
from sklearn.cluster import AgglomerativeClustering
from sklearn.preprocessing import MultiLabelBinarizer

# --- CONFIGURATION ---
# Paths are relative to this script's folder (VCDB_Inference_Rules-main).
path_to_vcdb = "./VCDB/data/json/validated/"  # Chemin vers votre VCDB (dossier 'validated')
N_CLUSTERS = 60  # à modifier si vous souhaitez + ou - de groupes
mapping_file_path = "../data/raw/mapping/attack-19.1_veris-1.4.1/veris-1.4.1_attack-19.1-enterprise.csv"  # VERIS↔ATT&CK mapping CSV

# --- ÉTAPE 0 : CHARGEMENT DE LA BASE MITRE ATT&CK (Techniques + Mitigations) ---
print(" CHARGEMENT DE LA BASE MITRE ATT&CK (Techniques & Remédiations) ")
mitre_db = {}
mitigations_db = {} 
relationships = []  

try:
    mitre_url = "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"
    mitre_data = requests.get(mitre_url, timeout=15).json()
    
    for obj in mitre_data['objects']:      
        if obj.get('type') == 'attack-pattern':
            ext_id = next((ref['external_id'] for ref in obj.get('external_references', []) if ref.get('source_name') == 'mitre-attack'), None)
            if ext_id:
                mitre_db[ext_id] = {"name": obj.get('name'), "id_stix": obj.get('id')}        

        elif obj.get('type') == 'course-of-action':
            mitigations_db[obj.get('id')] = obj.get('description', ' remédiation détaillée.')

        elif obj.get('type') == 'relationship' and obj.get('relationship_type') == 'mitigates':
            relationships.append({
                'mitigation_stix_id': obj.get('source_ref'),
                'attack_stix_id': obj.get('target_ref')
            })

    print(f"Succès : {len(mitre_db)} techniques et {len(mitigations_db)} remédiations chargées.")
except Exception as e:
    print(f"Erreur MITRE : {e}")

# --- ÉTAPE 0.1: PRÉPARATION DU MAPPING DYNAMIQUE ---
print(" PRÉPARATION DU MAPPING VERIS-TO-MITRE ")
mapping_dict = {}
if os.path.exists(mapping_file_path):
    df_map = pd.read_csv(mapping_file_path, on_bad_lines='skip', quotechar='"') 
    df_map.columns = [c.strip() for c in df_map.columns]
    
    for _, row in df_map.iterrows():
        veris_term = str(row.get('capability_description', '')).lower().strip()
        mitre_id = str(row.get('attack_object_id', '')).strip()
        if veris_term and mitre_id and mitre_id != 'nan':
            if veris_term not in mapping_dict:
                mapping_dict[veris_term] = set()
            mapping_dict[veris_term].add(mitre_id)
    print(f"Succès : {len(mapping_dict)} entrées de mapping chargées.")
else:
    print("Attention : Fichier de mapping introuvable.")

# --- FONCTION DE RÉCUPÉRATION DES REMÉDIATIONS ---
def get_mitre_mitigations(attack_id):
    """Trouve les mitigations les plus pertinentes pour un ID spécifique"""
    if attack_id not in mitre_db:
        return []
    
    stix_id = mitre_db[attack_id]['id_stix']
    linked_mitigations = []
    
    for rel in relationships:
        if rel['attack_stix_id'] == stix_id:
            mit_desc = mitigations_db.get(rel['mitigation_stix_id'])
            if mit_desc:
                clean_mit = mit_desc.split('.')[0].strip() + '.'
                if len(clean_mit) > 20: 
                    linked_mitigations.append(clean_mit)
    
    return linked_mitigations[:2] 

def get_mapping_dynamique(items_list):
    final_ids = set()
    all_remediations = []
    
    for item in items_list:
        item_lower = str(item).lower().strip()
        for veris_desc, mitre_ids in mapping_dict.items():
            if item_lower in veris_desc or veris_desc in item_lower:
                for m_id in mitre_ids:
                    final_ids.add(m_id)
                    all_remediations.extend(get_mitre_mitigations(m_id))
                break

    from collections import Counter
    top_remediations = [res for res, count in Counter(all_remediations).most_common(5)]
    
    ids_str = ", ".join(sorted(list(final_ids)))
    rem_str = " \n- ".join(top_remediations) 
    
    return ids_str, f"- {rem_str}"

# --- ÉTAPE 1 : CHARGEMENT DE LA VCDB ---
all_incidents_techniques = []
incident_ids = [] 

if os.path.exists(path_to_vcdb):
    for filename in os.listdir(path_to_vcdb):
        if filename.endswith(".json"):
            try:
                with open(os.path.join(path_to_vcdb, filename), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    items = []
                    actions = data.get('action', {})
                    for act_type in actions:
                        details = actions[act_type]
                        items.extend(details.get('techniques', []))
                        var = details.get('variety', [])
                        if isinstance(var, list): items.extend(var)
                        else: items.append(var)
                    clean = list(set([str(i) for i in items if i and str(i).lower() != 'unknown']))
                    if clean:
                        all_incidents_techniques.append(clean)
                        incident_ids.append(filename.replace(".json", "")) 
            except: continue
    print(f" ÉTAPE 1 : {len(all_incidents_techniques)} incidents chargés. ")

# --- ÉTAPE 2 & 3 : FP-GROWTH & CLUSTERING ---
if len(all_incidents_techniques) > 0:
    te = TransactionEncoder()
    te_ary = te.fit(all_incidents_techniques).transform(all_incidents_techniques)
    df = pd.DataFrame(te_ary, columns=te.columns_)
    
    frequent_itemsets = fpgrowth(df, min_support=0.015, use_colnames=True)     # ICI min_support important --> Il influe sur la quantité de données présentes dans l'Excel (lignes) . Augmenter cette valeur diminuera le nombre de données récupérées ; c'est un seuil de quantité avant qu'un type d'incident soit pris en compte ( cela évite de surcharger le Excel)
    rules = association_rules(frequent_itemsets, metric="lift", min_threshold=1.2)

    if not rules.empty:
        def find_source_incidents(row):
            pattern = set(list(row['antecedents']) + list(row['consequents']))
            matches = [incident_ids[idx] for idx, inc in enumerate(all_incidents_techniques) if pattern.issubset(set(inc))]
            return pd.Series([len(matches), ", ".join(matches)])

        rules[['NB_INCIDENTS', 'LISTE_ID_INCIDENTS']] = rules.apply(find_source_incidents, axis=1)

        # Clustering
        rules['combined_items'] = rules.apply(lambda x: list(set(list(x['antecedents']) + list(x['consequents']))), axis=1)
        mlb = MultiLabelBinarizer()
        binary_matrix = mlb.fit_transform(rules['combined_items'])
        n_clusters_final = min(N_CLUSTERS, len(rules))
        cluster = AgglomerativeClustering(n_clusters=n_clusters_final, metric='euclidean', linkage='ward')
        rules['ID_GROUPE'] = cluster.fit_predict(binary_matrix)

        def qualifier_groupe(df_groupe):
            all_words = [item for sublist in df_groupe['combined_items'] for item in sublist]
            return " + ".join(pd.Series(all_words).value_counts().head(7).index.tolist()).upper()

        noms_groupes = rules.groupby('ID_GROUPE').apply(qualifier_groupe, include_groups=False).to_dict()
        rules['SCÉNARIO_TYPE'] = rules['ID_GROUPE'].map(noms_groupes)

        # --- ÉTAPE 4 : MAPPING DYNAMIQUE ET REMÉDIATIONS ---
        print("\n--- GÉNÉRATION DES REMÉDIATIONS (ACTIONS CONCRÈTES) ---")
        rules[['MITRE_ID', 'ACTIONS_RECOMMANDÉES']] = rules.apply(lambda x: pd.Series(get_mapping_dynamique(x['combined_items'])), axis=1)

        rules['ANTÉCÉDENTS'] = rules['antecedents'].apply(lambda x: ", ".join(list(x)))
        rules['CONSÉQUENTS'] = rules['consequents'].apply(lambda x: ", ".join(list(x)))
        
        final_cols = ['ID_GROUPE', 'SCÉNARIO_TYPE', 'ANTÉCÉDENTS', 'CONSÉQUENTS', 
                      'NB_INCIDENTS', 'LISTE_ID_INCIDENTS', 'MITRE_ID', 'ACTIONS_RECOMMANDÉES', 'lift']
        
        excel_df = rules[final_cols].sort_values(by=['ID_GROUPE', 'lift'], ascending=[True, False])
        
        # Export
        excel_df.to_excel("Analyse_VCDB.xlsx", index=False)
        print(f"\n--- ANALYSE TERMINÉE : Fichier 'Analyse_VCDB_Remediations.xlsx' généré. ---")
    else:
        print("Aucune règle trouvée.")