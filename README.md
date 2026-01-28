# BiblioHelper – Extraction et fusion de références bibliographiques

Petit outil pour extraire et consolider les références bibliographiques d’un manuscrit (ou d’articles) PDF en utilisant l’Agent Cursor, puis générer un tableau final en Markdown et HTML interactif.

### Vue d’ensemble du pipeline

1. **Découper le PDF long en chunks** (`split_pdf.py`)
2. **Extraire les références de chaque chunk** (`extract_references.py`)
3. **Fusionner et dédupliquer les références** (`merge_references.py`)

---

## Prérequis

- **Python 3.9+**
- **Dépendances Python** installées avec :

```bash
pip install -r requirements.txt
```

- **Agent Cursor** disponible en ligne de commande (CLI ou intégration Cursor) – les scripts appellent l’agent via la commande retournée par `get_agent_base_cmd()` dans `extract_references.py`.

---

## 1. Découper un gros PDF en chunks – `split_pdf.py`

But : créer des sous-PDF de taille raisonnable (ex. 20 pages) pour faciliter l’extraction.

```bash
python split_pdf.py \
  --input "articles/exception/20250114_manuscrit_thèse_LENHOF.pdf" \
  --output-dir "articles/20250114_manuscrit_thèse_LENHOF_chunks" \
  --chunk-size 20
```

Sortie : des fichiers du type  
`20250114_manuscrit_thèse_LENHOF_chunk_002_pages_21-40.pdf` dans le dossier `articles/..._chunks/`.

---

## 2. Extraire les références d’un PDF ou d’un chunk – `extract_references.py`

But : pour chaque PDF (article isolé ou chunk de thèse), produire un **tableau Markdown** + éventuellement **HTML/PDF** avec les colonnes :

- `Référence`
- `Thème` (4–6 thèmes globaux pour tout le document)
- `Arguments étayés`
- `Note d'importance` (0–100)
- `Année`
- `Lien web`

Usage typique sur un chunk :

```bash
python extract_references.py \
  --pdf "articles/20250114_manuscrit_thèse_LENHOF_chunks/20250114_manuscrit_thèse_LENHOF_chunk_002_pages_21-40.pdf"
```

Sorties (dans le même dossier que le PDF) :

- `..._references.md` – tableau Markdown
- `..._references.html` – tableau HTML interactif (si activé dans les options)
- (éventuellement) `..._references.pdf` selon la configuration

Tu peux boucler sur tous les chunks avec un petit script shell / PowerShell ou en les appelant un par un.

---

## 3. Fusionner toutes les références en un seul tableau – `merge_references.py`

But : prendre **tous les fichiers `*_references.md` de chunks** et produire un **seul tableau consolidé** (Markdown + HTML) avec :

- **Déduplication intelligente** : fusion des doublons basés sur auteurs + année (tolérant aux variantes de titre/format),
- **Conservation stricte** : **aucune référence présente dans les tableaux d’entrée ne doit être supprimée** ; en cas de doute, les références restent séparées,
- **Thèmes normalisés** : exactement **4 à 6 thèmes** globaux pour tout le tableau final,
- Combinaison des « arguments étayés » et de la **note d’importance max** pour chaque référence fusionnée.

Exemple d’appel (fusion de tous les `*_references.md` d’un dossier de chunks) :

```bash
python merge_references.py \
  --input "articles/20250114_manuscrit_thèse_LENHOF_chunks/*.md"
```

Sorties typiques dans le même dossier :

- `20250114_manuscrit_thèse_LENHOF_001_pages_1-20_references_merged.md`
- `20250114_manuscrit_thèse_LENHOF_001_pages_1-20_references_merged.html`

Le HTML contient un tableau interactif (tri, filtres par thème, seuil de note, recherche texte, couleurs par thème, stats rapides, etc.).

---

## Exemple de sortie HTML

Un exemple concret de fichier HTML généré par `extract_references.py` (pour un article isolé) est fourni dans le dépôt local :

- `Xie et al. - 2023 - Shallow Water Seafloor Geodesy With Wave Glider-Ba_references.html`

Ouvre-le dans ton navigateur pour voir à quoi ressemble le tableau interactif (tri par colonnes, filtres, couleurs par thème, etc.).

## Remarques

- Les dossiers volumineux (`articles/`, `My Library/`) et l’environnement virtuel (`venv/`) sont **exclus du dépôt Git** via `.gitignore`.
- Le projet est pensé pour être utilisé localement sur ta machine (avec tes propres PDFs) et pousser uniquement les **scripts** et la structure de pipeline sur GitHub (`GITHORU/BiblioHelper`).

