# Extracteur de Références Bibliographiques

Script simple pour extraire les références bibliographiques d'un article scientifique PDF en utilisant Cursor CLI Agent.

## Prérequis

1. **Cursor CLI installé** :
   
   **Sur Linux/Mac :**
   ```bash
   curl https://cursor.com/install -fsS | bash
   ```
   
   **Sur Windows :**
   Cursor CLI nécessite WSL (Windows Subsystem for Linux). Installation :
   
   1. Ouvrir PowerShell en tant qu'administrateur
   2. Exécuter : `wsl --install`
   3. Redémarrer l'ordinateur
   4. Dans le terminal WSL, exécuter :
      ```bash
      curl https://cursor.com/install -fsS | bash
      ```
   5. Vérifier l'installation : `agent --version`

2. **Python 3** (pour le script Python) ou **Bash** (pour le script shell)

3. **Dépendances Python** (pour la génération PDF) :
   ```bash
   pip install -r requirements.txt
   ```
   Ou simplement :
   ```bash
   pip install reportlab
   ```

## Installation

### Installation rapide sur Windows

1. **Installer WSL** (si pas déjà fait) :
   ```powershell
   # Ouvrir PowerShell en tant qu'administrateur
   wsl --install
   # Redémarrer l'ordinateur
   ```

2. **Installer Cursor CLI dans WSL** :
   ```bash
   # Ouvrir WSL
   wsl
   # Installer Cursor CLI
   curl https://cursor.com/install -fsS | bash
   # Vérifier l'installation
   agent --version
   ```

3. **Utiliser les scripts** :
   - Le script Python détecte automatiquement Windows et utilise WSL
   - Ou utiliser le script PowerShell dédié : `extract_references_wsl.ps1`

### Installation sur Linux/Mac

```bash
curl https://cursor.com/install -fsS | bash
agent --version
```

## Utilisation

### Script Python (recommandé - multiplateforme)

```bash
python extract_references.py <chemin_vers_pdf>
```

Exemple:
```bash
python extract_references.py article.pdf
```

### Script PowerShell (Windows avec WSL)

**Important :** Sur Windows, Cursor CLI nécessite WSL. Utilisez le script spécialisé :

```powershell
.\extract_references_wsl.ps1 -PdfPath <chemin_vers_pdf>
```

Exemple:
```powershell
.\extract_references_wsl.ps1 -PdfPath article.pdf
```

**Alternative :** Si vous avez WSL configuré, vous pouvez aussi utiliser directement le script bash dans WSL :
```bash
wsl
./extract_references.sh /mnt/c/chemin/vers/article.pdf
```

### Script Bash (Linux/Mac)

```bash
chmod +x extract_references.sh
./extract_references.sh <chemin_vers_pdf>
```

Exemple:
```bash
./extract_references.sh article.pdf
```

## Fonctionnement

Le script :
1. Vérifie que le fichier PDF existe
2. Envoie le PDF à l'agent Cursor avec le prompt spécialisé
3. L'agent extrait les références bibliographiques et crée un tableau
4. Affiche le résultat dans le terminal
5. **Sauvegarde automatiquement le tableau dans un fichier Markdown** (`<nom_du_pdf>_references.md`)

## Format de sortie

Le script génère automatiquement **deux fichiers** :

1. **Un fichier PDF** avec un tableau formaté contenant :
- **Référence** : Les références bibliographiques complètes
- **Thème** : Le thème principal de l'argument étayé. **Contrainte stricte** : L'agent doit utiliser exactement entre 4 et 6 thèmes différents maximum pour tout le document. Les références sont regroupées sous des thèmes larges et généraux (ex: "Méthodes GNSS-Acoustic", "Géodésie des fonds marins", "Optimisation et traitement de données", etc.)
- **Arguments étayés** : Description précise des arguments étayés par chaque référence
- **Note d'importance** : Un score de 0 à 100 indiquant l'importance de la référence pour l'article
- **Année** : L'année de publication de la référence
- **Lien web** : URL cliquable vers la page de l'article (trouvée dans le document ou recherchée sur internet)

Le tableau est **automatiquement trié** :
1. Par **thème** (regroupement par thème)
2. Puis **chronologiquement** (année croissante) au sein de chaque thème

2. **Un fichier HTML interactif** avec un tableau triable et filtrable contenant :
   - Toutes les mêmes colonnes que le PDF
   - **Tri interactif** : Cliquez sur les en-têtes pour trier (Référence, Thème, Note d'importance, Année, Lien web)
   - **Liens cliquables** : Les URLs dans la colonne "Lien web" sont cliquables et s'ouvrent dans un nouvel onglet
   - **Filtres** :
     - Filtre par thème (menu déroulant)
     - Filtre par note d'importance minimale
     - Recherche textuelle dans toutes les colonnes
   - **Statistiques en temps réel** : Nombre total de références, références visibles, note moyenne
   - **Couleurs par thème** : Même code couleur que le PDF
   - **Légende des thèmes** : Affichage de tous les thèmes avec leurs couleurs
   - **Design moderne** : Interface utilisateur élégante et responsive

Les fichiers de sortie sont créés dans le même répertoire que le PDF d'entrée :
- `<nom_du_pdf>_references.pdf` - Version PDF imprimable
- `<nom_du_pdf>_references.html` - Version HTML interactive
- `<nom_du_pdf>_references.ris` - **Export RIS pour Zotero** (importable directement)
- `<nom_du_pdf>_references.bib` - **Export BibTeX pour Zotero** (importable directement)

**Import dans Zotero :**

**Méthode 1 - Format RIS (recommandé) :**
1. Ouvrir Zotero
2. Fichier → Importer...
3. Choisir "Un fichier"
4. Sélectionner le fichier `<nom_du_pdf>_references.ris`
5. Les références seront importées avec leurs métadonnées

**Méthode 2 - Format BibTeX :**
1. Ouvrir Zotero
2. Fichier → Importer...
3. Choisir "Un fichier"
4. Sélectionner le fichier `<nom_du_pdf>_references.bib`
5. Les références seront importées avec leurs métadonnées

**Métadonnées incluses :**
- Auteurs (extraits de la référence)
- Titre (extrait de la référence)
- Année de publication
- URL/Lien web (si disponible)
- Thème (dans les notes personnalisées)
- Arguments étayés (dans les notes personnalisées)

**Note :** Les formats RIS et BibTeX sont des standards universels, compatibles avec Zotero, Mendeley, EndNote, et la plupart des gestionnaires de références.

**Note :** Si `reportlab` n'est pas installé, le script sauvegardera automatiquement en format Markdown (`.md`) à la place, mais le HTML et les exports Zotero seront toujours générés.

## Prompt de l'agent

L'agent reçoit un prompt spécialisé qui spécifie :
- Le format de sortie exact (tableau markdown avec 6 colonnes)
- Les colonnes requises : "Référence", "Thème", "Arguments étayés", "Note d'importance" (0-100), "Année", "Lien web"
- La recherche de liens web : L'agent doit chercher les URLs dans le document (DOI, URLs) ou les rechercher sur internet si absentes
- L'identification du thème principal pour chaque référence
- L'attribution d'une note d'importance entre 0 et 100
- L'extraction de l'année de publication
- L'obligation de ne répondre que par le tableau, sans texte supplémentaire
- La nécessité de lister TOUTES les références bibliographiques du document

Le prompt est optimisé pour garantir un format de sortie stable et cohérent, permettant un tri automatique par thème puis chronologique.

## Notes

- La syntaxe exacte du CLI Cursor peut varier selon la version
- Si une syntaxe ne fonctionne pas, le script essaiera d'autres variantes
- Le résultat est affiché dans le terminal ET sauvegardé automatiquement dans plusieurs formats :
  - **PDF** : Version imprimable avec liens cliquables
  - **HTML** : Version interactive avec tri et filtres
  - **RIS** : Format universel pour Zotero et autres gestionnaires de références
  - **BibTeX** : Format standard pour LaTeX et Zotero
- Le script utilise `--model auto` pour sélectionner automatiquement un modèle disponible
- Le tableau est extrait automatiquement de la réponse et formaté dans tous les formats
- Les exports Zotero incluent les métadonnées complètes (auteurs, titre, année, URL, thème et arguments étayés dans les notes)
- Si `reportlab` n'est pas installé, le script sauvegardera en Markdown à la place, mais le HTML et les exports Zotero seront toujours générés
