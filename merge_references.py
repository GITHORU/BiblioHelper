#!/usr/bin/env python3
"""
Script pour fusionner les tableaux markdown de plusieurs blocs en un tableau unique consolidé.
"""

import sys
import subprocess
import os
import re
import glob
from pathlib import Path

# Importer les fonctions nécessaires depuis extract_references.py
try:
    from extract_references import (
        extract_table_from_response,
        parse_markdown_table,
        save_table_to_file,
        get_agent_base_cmd,
    )
except ImportError:
    print("Erreur: Impossible d'importer extract_references.py", file=sys.stderr)
    sys.exit(1)


def get_merge_prompt():
    """Retourne le prompt pour la fusion des références."""
    return """tu es un agent IA spécialisé dans la fusion et consolidation de références bibliographiques. Ton rôle est de fusionner plusieurs tableaux markdown contenant des références bibliographiques extraites de différents blocs d'un même document en un SEUL tableau consolidé.

INSTRUCTIONS CRITIQUES - LIS ATTENTIVEMENT :
- Tu dois RÉPONDRE DIRECTEMENT avec le tableau markdown dans ta réponse
- NE PAS créer de fichiers, NE PAS écrire de fichiers sur le disque
- NE PAS ajouter de texte avant ou après le tableau
- NE PAS poser de questions, NE PAS faire de commentaires
- Commence ta réponse DIRECTEMENT par le tableau markdown
- Termine ta réponse DIRECTEMENT après le tableau markdown

FORMAT DE SORTIE OBLIGATOIRE - Réponds UNIQUEMENT avec un tableau markdown au format suivant :

| Référence | Thème | Arguments étayés | Note d'importance | Année | Lien web |
|-----------|-------|------------------|-------------------|-------|----------|
| Auteur1 et al. (2020) - Titre | Thème principal | Utilisée pour justifier la méthode X, appuyer l'hypothèse Y et fournir le cadre théorique pour l'approche Z | 85 | 2020 | https://example.com/article1 |

RÈGLES DE FUSION STRICTES :
0. CONSERVATION OBLIGATOIRE : AUCUNE référence présente dans les tableaux d'entrée ne doit être supprimée. Même si une référence n'apparaît qu'une seule fois ou semble secondaire, conserve-la comme une ligne dans le tableau final. Tu ne dois fusionner que deux lignes qui représentent manifestement la même référence (même auteur(s) et même année). En cas de doute, garde deux lignes distinctes plutôt que de fusionner.
1. DÉDUPLICATION : Si une même référence apparaît dans plusieurs blocs, fusionne-la en une seule entrée.
   IMPORTANT : Pour déterminer si deux lignes concernent la même référence, ne te fies PAS uniquement à l’égalité exacte du texte de la colonne "Référence".
   Tu dois utiliser ton discernement et considérer qu'il s’agit de la même référence lorsque :
   - les auteurs (noms de famille principaux) et l’année de publication sont les mêmes,
   - même si le titre est formulé légèrement différemment, tronqué, ou qu’il existe des variantes mineures (ponctuation, accents, majuscules/minuscules, ordre des prénoms/initiales),
   - ou que la forme de la citation varie (ex : "Spiess (1985)" vs "Spiess, F. N. (1985)" vs "Spiess 1985").
   En cas de doute raisonnable, regroupe ces lignes en une seule référence fusionnée plutôt que de les dupliquer.
2. ARGUMENTS ÉTAYÉS : Combine tous les usages de la référence trouvés dans les différents blocs en un SEUL argument unifié et cohérent. Ne pas utiliser de format "Usage 1, Usage 2, etc." mais plutôt créer un texte fluide qui explique de manière synthétique tous les points que cette référence sert à justifier dans le document. L'argument doit être unifié et naturel, pas une simple liste séparée.
3. NOTE D'IMPORTANCE : Prend la note la plus élevée si la référence apparaît plusieurs fois
4. THÈMES : Consolide les thèmes pour avoir EXACTEMENT entre 4 et 6 thèmes différents au total. C'est une règle absolue. Regroupe les thèmes similaires sous des thèmes généraux et larges. Si une référence apparaît avec des thèmes différents dans plusieurs blocs, choisis le thème le plus fréquent ou le plus approprié.
5. ANNÉE : Utilise l'année la plus fréquente ou la première trouvée
6. LIEN WEB : Utilise le premier lien web valide trouvé

RÈGLES DE FORMAT ABSOLUES :
- Commence DIRECTEMENT par le tableau (pas de texte d'introduction, pas de "Voici le tableau", rien)
- Utilise exactement le format markdown ci-dessus avec les colonnes : "Référence", "Thème", "Arguments étayés", "Note d'importance", "Année", "Lien web"
- Chaque référence doit être sur une seule ligne
- Ne termine PAS par du texte supplémentaire ou des formules de politesse
- Le tableau doit être complet et listant TOUTES les références (dédupliquées)
- RÉPONDS UNIQUEMENT DANS TA RÉPONSE, NE CRÉE PAS DE FICHIERS"""


def expand_glob_patterns(pattern):
    """Développe un pattern glob en liste de fichiers."""
    files = []
    for path in glob.glob(pattern, recursive=False):
        p = Path(path)
        if p.is_file() and p.suffix.lower() == '.md':
            files.append(p)
    return sorted(files)


def read_markdown_files(input_paths):
    """Lit tous les fichiers markdown depuis un dossier, un pattern glob, ou une liste de fichiers."""
    # Si input_paths est une liste, traiter comme des fichiers individuels
    if isinstance(input_paths, list):
        md_files = []
        for path_str in input_paths:
            p = Path(path_str)
            if not p.exists():
                print(f"⚠️  Fichier non trouvé: {p}", file=sys.stderr)
                continue
            if not p.is_file():
                print(f"⚠️  '{p}' n'est pas un fichier.", file=sys.stderr)
                continue
            if p.suffix.lower() != '.md':
                print(f"⚠️  '{p}' n'est pas un fichier .md.", file=sys.stderr)
                continue
            md_files.append(p)
        
        if not md_files:
            return [], None
        
        # Déterminer le répertoire de sortie (parent du premier fichier)
        output_dir = md_files[0].parent
    else:
        # Traiter comme un seul chemin (dossier, pattern glob, ou fichier)
        input_path_str = str(input_paths)
        
        # Si c'est un pattern glob (contient * ou ?)
        if '*' in input_path_str or '?' in input_path_str:
            md_files = expand_glob_patterns(input_path_str)
            if not md_files:
                print(f"⚠️  Aucun fichier .md trouvé avec le pattern '{input_path_str}'", file=sys.stderr)
                return [], None
            
            # Déterminer le répertoire de sortie (parent du premier fichier)
            output_dir = md_files[0].parent
        else:
            # C'est un dossier ou un fichier
            chunks_dir = Path(input_paths)
            
            if not chunks_dir.exists():
                print(f"❌ Erreur: '{chunks_dir}' n'existe pas.", file=sys.stderr)
                return [], None
            
            if chunks_dir.is_file():
                # C'est un fichier individuel
                if chunks_dir.suffix.lower() != '.md':
                    print(f"❌ Erreur: '{chunks_dir}' n'est pas un fichier .md.", file=sys.stderr)
                    return [], None
                md_files = [chunks_dir]
                output_dir = chunks_dir.parent
            else:
                # C'est un dossier
                # Trouver tous les fichiers *_references.md ou *.md
                md_files = sorted(list(chunks_dir.glob("*_references.md")) + list(chunks_dir.glob("*.md")))
                # Éliminer les doublons (si un fichier correspond aux deux patterns)
                md_files = list(dict.fromkeys(md_files))
                
                if not md_files:
                    print(f"⚠️  Aucun fichier .md trouvé dans '{chunks_dir}'", file=sys.stderr)
                    return [], None
                
                output_dir = chunks_dir
    
    print(f"✓ {len(md_files)} fichier(s) markdown trouvé(s)", file=sys.stderr)
    
    # Lire le contenu de tous les fichiers
    markdown_contents = []
    for md_file in md_files:
        try:
            content = md_file.read_text(encoding='utf-8')
            markdown_contents.append(content)
            print(f"  - {md_file.name}", file=sys.stderr)
        except Exception as e:
            print(f"⚠️  Erreur lors de la lecture de {md_file.name}: {e}", file=sys.stderr)
    
    return markdown_contents, output_dir, md_files


def merge_references(input_paths, output_name=None):
    """Fusionne les références de plusieurs fichiers markdown."""
    # Lire tous les fichiers markdown
    result = read_markdown_files(input_paths)
    
    if not result or result[0] is None:
        return None
    
    markdown_contents, output_dir, md_files = result
    
    if output_dir is None:
        return None
    
    if not markdown_contents:
        return None
    
    # Si un seul fichier, pas besoin de fusion
    if len(markdown_contents) == 1:
        print("⚠️  Un seul fichier trouvé, pas de fusion nécessaire.", file=sys.stderr)
        return None
    
    # Construire le prompt (sans les tableaux, ils seront passés comme fichiers)
    prompt = get_merge_prompt()
    prompt += f"\n\nTu reçois {len(md_files)} fichiers markdown contenant des tableaux à fusionner. "
    prompt += "Lis TOUS ces fichiers et fusionne-les en un SEUL tableau consolidé selon les règles strictes définies ci-dessus. "
    prompt += "\n\nRAPPEL CRITIQUE : Réponds UNIQUEMENT avec le tableau markdown dans ta réponse. "
    prompt += "NE CRÉE PAS DE FICHIERS, NE FAIS PAS DE COMMENTAIRES, NE POSE PAS DE QUESTIONS. "
    prompt += "Commence DIRECTEMENT par le tableau markdown (ligne | Référence | Thème | ...) et termine DIRECTEMENT après le dernier | du tableau."
    
    # Déterminer le nom du fichier de sortie
    if output_name is None:
        # Si input_paths est une liste, utiliser le premier fichier
        if isinstance(input_paths, list) and input_paths:
            first_file = Path(input_paths[0])
            base_name = first_file.stem.replace("_references", "").replace("_chunk_", "_")
            output_name = f"{base_name}_references_merged"
        else:
            input_path_str = str(input_paths)
            # Si c'est un pattern glob, utiliser le nom du premier fichier trouvé
            if '*' in input_path_str or '?' in input_path_str:
                # Récupérer le premier fichier depuis le pattern
                first_files = expand_glob_patterns(input_path_str)
                if first_files:
                    first_file = first_files[0]
                    base_name = first_file.stem.replace("_references", "").replace("_chunk_", "_")
                    output_name = f"{base_name}_references_merged"
                else:
                    output_name = "references_merged"
            else:
                # Extraire le nom de base du dossier ou fichier
                path_obj = Path(input_paths)
                if path_obj.is_file():
                    base_name = path_obj.stem.replace("_references", "").replace("_chunk_", "_")
                    output_name = f"{base_name}_references_merged"
                else:
                    base_name = path_obj.stem.replace("_chunks", "")
                    output_name = f"{base_name}_references_merged"
    else:
        output_name = Path(output_name).stem
    
    # Déterminer le répertoire de sortie
    output_path = output_dir / f"{output_name}.pdf"
    
    try:
        print(f"Traitement en cours...", file=sys.stderr)
        # Appel natif à l'agent (Windows, Linux, Mac) via get_agent_base_cmd
        md_paths = [str(md_file.resolve()) for md_file in md_files]
        base_cmd = get_agent_base_cmd()
        cmd = base_cmd + ['--model', 'auto', 'chat', prompt] + md_paths
        
        env = os.environ.copy()
        env['LC_ALL'] = 'C.UTF-8'
        env['LANG'] = 'C.UTF-8'
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env,
            check=False
        )
        
        if result.returncode == 0:
            table_content = extract_table_from_response(result.stdout)
            if table_content:
                save_table_to_file(table_content, output_path)
                print(f"\n✓ Fusion terminée: {output_path.name}", file=sys.stderr)
                print(f"  - PDF: {output_path.name}", file=sys.stderr)
                print(f"  - HTML: {output_path.with_suffix('.html').name}", file=sys.stderr)
                print(f"  - Markdown: {output_path.with_suffix('.md').name}", file=sys.stderr)
                return output_path
            else:
                md_path = output_path.with_suffix('.md')
                md_path.write_text(result.stdout, encoding='utf-8')
                print(f"⚠️  Aucun tableau détecté. Réponse sauvegardée: {md_path.name}", file=sys.stderr)
                return None
        else:
            print(f"❌ Erreur lors du traitement (code {result.returncode})", file=sys.stderr)
            if result.stderr:
                print(f"Erreur: {result.stderr}", file=sys.stderr)
            return None
            
    except Exception as e:
        print(f"❌ Erreur: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python merge_references.py <dossier_ou_pattern_ou_fichiers...> [nom_sortie]", file=sys.stderr)
        print("", file=sys.stderr)
        print("Exemples:", file=sys.stderr)
        print("  python merge_references.py articles/these_chunks", file=sys.stderr)
        print("  python merge_references.py articles/*.md", file=sys.stderr)
        print("  python merge_references.py articles/*_references.md", file=sys.stderr)
        print("  python merge_references.py file1.md file2.md file3.md", file=sys.stderr)
        print("  python merge_references.py articles/these_chunks these_finale", file=sys.stderr)
        sys.exit(1)
    
    # Si plusieurs arguments et que le dernier n'est pas un fichier existant, c'est probablement le nom de sortie
    if len(sys.argv) >= 3:
        last_arg = Path(sys.argv[-1])
        # Si le dernier argument n'existe pas comme fichier/dossier et ne contient pas de wildcards, c'est le nom de sortie
        if not last_arg.exists() and '*' not in str(last_arg) and '?' not in str(last_arg) and not last_arg.suffix == '.md':
            input_paths = sys.argv[1:-1]
            output_name = sys.argv[-1]
        else:
            input_paths = sys.argv[1:]
            output_name = None
    else:
        input_paths = [sys.argv[1]]
        output_name = None
    
    # Si un seul chemin, le passer tel quel (peut être un dossier ou un pattern)
    # Si plusieurs chemins, les passer comme liste
    if len(input_paths) == 1:
        input_paths = input_paths[0]
    
    result = merge_references(input_paths, output_name)
    
    if result is None:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
