# Contexte du Projet - Extracteur de Références Bibliographiques

## Objectif du Projet

Script Python pour extraire automatiquement les références bibliographiques d'articles scientifiques PDF en utilisant Cursor CLI Agent, et générer des tableaux structurés avec analyse des arguments étayés.

## État Actuel du Projet

### Fichiers Principaux

1. **`extract_references.py`** - Script principal
   - Traite un ou plusieurs PDF en parallèle
   - Utilise Cursor CLI via WSL sur Windows
   - Génère 3 formats de sortie : PDF, HTML interactif, Markdown
   - Support du traitement parallèle (max 4 fichiers simultanés)

2. **`split_pdf.py`** - Script de découpage
   - Découpe un PDF volumineux en blocs de 20 pages (configurable)
   - Crée un dossier `{nom}_chunks/` avec tous les blocs
   - Nécessite `pypdf` (dans requirements.txt)

3. **`requirements.txt`**
   - `reportlab>=4.0.0` - Pour génération PDF
   - `pypdf>=3.0.0` - Pour découpage PDF

## Fonctionnalités Implémentées

### Extraction de Références
- Extraction via Cursor CLI Agent avec prompt spécialisé
- Format de sortie : tableau markdown avec colonnes :
  - Référence
  - Thème (4-6 thèmes max, consolidation automatique)
  - Arguments étayés (comment la référence sert l'article analysé)
  - Note d'importance (0-100)
  - Année
  - Lien web (cliquable dans PDF/HTML)

### Formats de Sortie
- **PDF** : Tableau formaté avec couleurs par thème, légende
- **HTML** : Tableau interactif avec :
  - Tri par colonne (clic sur en-tête)
  - Filtrage par thème
  - Filtrage par note d'importance minimale
  - Recherche textuelle
  - Statistiques en temps réel
  - Couleurs par thème avec légende
- **Markdown** : Format brut pour fusion ultérieure

### Traitement Parallèle
- Support de plusieurs PDF en une seule commande
- Traitement en parallèle (ThreadPoolExecutor, max 4 workers)
- Affichage des résultats au fur et à mesure

### Découpage de PDF Volumineux
- Découpage en blocs de 20 pages (configurable)
- Nommage automatique : `{nom}_chunk_001_pages_1-20.pdf`
- Création d'un dossier dédié pour les chunks

## Configuration Technique

### Environnement
- **OS** : Windows avec WSL (Windows Subsystem for Linux)
- **Python** : 3.x avec venv
- **Cursor CLI** : Installé dans WSL (`~/.local/bin/agent`)
- **Commande** : `agent --model auto chat`

### Prompt Agent
Le prompt demande à l'agent de :
1. Extraire TOUTES les références bibliographiques
2. Identifier 4-6 thèmes maximum (consolidation automatique)
3. Décrire comment chaque référence sert l'article analysé (pas le contenu de l'article référencé)
4. Assigner une note d'importance (0-100)
5. Extraire l'année et chercher le lien web

## Problèmes Rencontrés et Solutions

### 1. PDF Volumineux (64 Mo)
- **Problème** : PDF de 64 Mo échoue avec code d'erreur 1
- **Solution** : Script `split_pdf.py` pour découper en blocs de 20 pages
- **État** : Implémenté et fonctionnel

### 2. Export Zotero
- **Problème** : Tentative d'export RIS et BibTeX pour Zotero
- **Résultat** : Abandonné (problème côté Zotero, pas le format)
- **État** : Fonctionnalité retirée, uniquement PDF/HTML/Markdown

### 3. Fichiers Markdown
- **Problème** : Pas de .md créé par défaut (uniquement si erreur)
- **Solution** : Modifié `save_table_to_file()` pour toujours créer .md
- **État** : Implémenté

## Prochaines Étapes (À Implémenter)

### Script de Fusion des Références
**Objectif** : Fusionner les tableaux markdown de plusieurs blocs en un tableau unique consolidé.

**Fonctionnalités nécessaires** :
1. Lire tous les fichiers `*_references.md` d'un dossier de chunks
2. Envoyer à un agent Cursor avec un prompt de fusion spécialisé
3. Dédupliquer les références qui apparaissent dans plusieurs blocs
4. Fusionner les "Arguments étayés" (combiner tous les usages)
5. Consolider les thèmes (maintenir 4-6 thèmes max)
6. Prendre la note d'importance la plus élevée ou moyenne
7. Générer un tableau final consolidé (PDF + HTML + MD)

**Prompt de fusion proposé** :
```
Tu es un agent IA spécialisé dans la fusion et consolidation de références bibliographiques.

TÂCHE : Tu reçois plusieurs tableaux markdown contenant des références bibliographiques extraites de différents blocs d'un même document. Ton rôle est de fusionner ces tableaux en un SEUL tableau consolidé.

RÈGLES DE FUSION :
1. DÉDUPLICATION : Si une même référence apparaît dans plusieurs blocs, fusionne-la en une seule entrée
2. ARGUMENTS ÉTAYÉS : Combine tous les usages de la référence trouvés dans les différents blocs. Format : "Usage 1: [description] | Usage 2: [description] | ..."
3. NOTE D'IMPORTANCE : Prend la note la plus élevée si la référence apparaît plusieurs fois
4. THÈMES : Consolide les thèmes pour avoir EXACTEMENT entre 4 et 6 thèmes différents au total
5. ANNÉE : Utilise l'année la plus fréquente ou la première trouvée
6. LIEN WEB : Utilise le premier lien web valide trouvé

FORMAT DE SORTIE : Exactement le même format que les tableaux d'entrée (markdown)
```

**Workflow complet proposé** :
```
PDF volumineux (64 Mo)
  ↓
split_pdf.py → Blocs de 20 pages
  ↓
extract_references.py (parallèle) → Tableaux par bloc (*.md, *.pdf, *.html)
  ↓
merge_references.py → Tableau unique consolidé
```

## Structure des Fichiers Générés

### Par Bloc (après split_pdf.py)
```
articles/
  {nom}_chunks/
    {nom}_chunk_001_pages_1-20.pdf
    {nom}_chunk_002_pages_21-40.pdf
    ...
```

### Après extract_references.py (par bloc)
```
articles/
  {nom}_chunks/
    {nom}_chunk_001_pages_1-20.pdf
    {nom}_chunk_001_pages_1-20_references.pdf
    {nom}_chunk_001_pages_1-20_references.html
    {nom}_chunk_001_pages_1-20_references.md  ← Pour fusion
    ...
```

### Après merge_references.py (résultat final)
```
articles/
  {nom}_references_merged.pdf
  {nom}_references_merged.html
  {nom}_references_merged.md
```

## Commandes d'Utilisation

### Traitement simple (PDF < 20 MB)
```powershell
python extract_references.py ".\articles\article.pdf"
```

### Traitement multiple en parallèle
```powershell
python extract_references.py ".\articles\article1.pdf" ".\articles\article2.pdf" ".\articles\article3.pdf"
```

### Découpage d'un PDF volumineux
```powershell
python split_pdf.py ".\articles\these_64mo.pdf"
```

### Traitement des blocs (à faire manuellement pour l'instant)
```powershell
python extract_references.py ".\articles\{nom}_chunks\{nom}_chunk_001_pages_1-20.pdf"
python extract_references.py ".\articles\{nom}_chunks\{nom}_chunk_002_pages_21-40.pdf"
# ... etc pour tous les blocs
```

## Points d'Attention

1. **Taille des PDF** : Recommandé < 20 MB, acceptable jusqu'à 50 MB, risqué > 50 MB
2. **Temps de traitement** : 10-30 minutes pour un PDF normal, peut être beaucoup plus long pour des PDF volumineux
3. **WSL requis** : Sur Windows, Cursor CLI doit être installé dans WSL
4. **Tokens utilisés** : Environ 1.2M tokens pour un PDF moyen (inclus dans le plan Cursor)
5. **Encodage** : Gestion UTF-8 avec fallback latin-1 pour les caractères accentués

## Notes Techniques

- Le script détecte automatiquement Windows et utilise WSL
- Format de clé BibTeX : `author_year` (abandonné, plus utilisé)
- Les thèmes sont automatiquement consolidés si > 6
- Les références sont triées par thème puis par année
- Les couleurs sont assignées automatiquement aux thèmes

## État des Fonctionnalités

✅ Extraction de références depuis PDF  
✅ Génération PDF avec couleurs par thème  
✅ Génération HTML interactif  
✅ Génération Markdown  
✅ Traitement parallèle de plusieurs PDF  
✅ Découpage de PDF volumineux  
⏳ Fusion des références de plusieurs blocs (À FAIRE)
