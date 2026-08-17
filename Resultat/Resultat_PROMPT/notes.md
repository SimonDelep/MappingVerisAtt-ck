# Generation du 10-08
## Kimi-K3

| Capability | Complet | Notes |
| ------------------------- | ---- | ----- |
| action.hacking            | Non  | l.183, attribut "justification" incomplete, manque data (sans doute) |   
| action.malware            | Non  | l.948, nouvel attribut veris\_id incomplet, manque data (sans doute) |
| action.social             | Non  | fichier non fini correctement, manque de data (sans doute) |
| attribute.availability    | Oui  | fichier fini correctement |
| attribute.confidentiality | Vide | - |
| attribute.integrity       | Vide | - |
| value\_chain.develoment   | Vide | - |

Pour la generation de certaines capability, la limite du contexte doit etre atteinte, ce qui pourrais expliquer le fais que les fichiers soient incomplet, meme dans la forme du json

## Deepseek-v4-Pro

Aucun des fichiers de capability n'as ete rempli, aucune idee de pourquoi

# Generation du 13-08

Toutes les generation sont completes
## Kimi-K3:
Fichiers : 7/7 scopes presents                                
GLOBAL (tous scopes agreges) :                                                                          
Paires experts=1250  solution= 770  communes= 298                     
Precision= 38.7%  Rappel= 23.8%  F1= 29.5%  Jaccard= 17.3%                                                                                                                      
PAR CAPABILITY\_GROUP :    
  |scope                         | exp |  sol |  comm  |  Prec  |  Rapp  |    F1 |
  |------------------------------|-----|------|--------|--------|--------|-------|
  |action.hacking                |534  |359   |134     |  37.3% | 25.1%  |30.0%  |
  |action.malware                |405  |175   |70      |  40.0% | 17.3%  |24.1%  |
  |action.social                 | 79  | 63   |20      |  31.7% | 25.3%  |28.2%  |
  |attribute.integrity           | 91  | 95   |24      |  25.3% | 26.4%  |25.8%  |
  |attribute.confidentiality     | 73  | 19   |19      |  100.0%| 26.0%  |41.3%  |
  |attribute.availability        | 44  | 34   |20      |  58.8% | 45.5%  |51.3%  |
  |value\_chain.development      | 25  | 25   |11      |  44.0% | 44.0%  |44.0%  |

## Deepseek-v4-Pro
Fichiers : 7/7 scopes presents                                                                    
GLOBAL (tous scopes agreges): 

Paires experts=1250  solution=2231  communes= 523 
Precision= 23.4%  Rappel= 41.8%  F1= 30.0%  Jaccard= 17.7%                                            
                                                                                                    
PAR CAPABILITY_GROUP :                                                                              
  |scope                         |exp | sol |comm |  Prec |  Rapp |  F1   |
  |-----------------------------------|-----|-----|-------|-------|------ |
  |action.hacking                |534 | 766 | 163 | 21.3% | 30.5% | 25.1% |
  |action.malware                |405 | 853 | 180 | 21.1% | 44.4% | 28.6% |
  |action.social                 | 79 |  80 |  25 | 31.2% | 31.6% | 31.4% |
  |attribute.integrity           | 91 | 351 |  47 | 13.4% | 51.6% | 21.3% |
  |attribute.confidentiality     | 73 | 117 |  69 | 59.0% | 94.5% | 72.6% |
  |attribute.availability        | 44 |  55 |  29 | 52.7% | 65.9% | 58.6% |
  |value_chain.development       | 25 |   9 |   8 | 88.9% | 32.0% | 47.1% |
