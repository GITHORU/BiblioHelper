#!/usr/bin/env python3
"""
Script pour analyser les références bibliographiques d'un PDF de thèse
et générer un tableau markdown avec leur utilisation dans l'article.
"""

import re
import sys
from pathlib import Path

def extract_references_from_text(text):
    """Extrait toutes les références bibliographiques du texte."""
    # La section bibliographie commence après "BIBLIOGRAPHIE"
    bib_start = text.find("BIBLIOGRAPHIE")
    if bib_start == -1:
        return []
    
    bib_section = text[bib_start:]
    # S'arrêter avant les sections suivantes (comme "Titre :", etc.)
    bib_end = bib_section.find("Titre :")
    if bib_end != -1:
        bib_section = bib_section[:bib_end]
    
    references = []
    # Pattern pour détecter une référence : nom d'auteur suivi d'une année
    # Format typique : "Auteur, (Année), Titre, Journal, ..."
    lines = bib_section.split('\n')
    current_ref = []
    
    for line in lines:
        line = line.strip()
        if not line:
            if current_ref:
                ref_text = ' '.join(current_ref)
                if ref_text and len(ref_text) > 20:  # Filtrer les lignes trop courtes
                    references.append(ref_text)
                current_ref = []
            continue
        
        # Détecter le début d'une nouvelle référence (commence généralement par un nom d'auteur)
        # Pattern : nom en majuscules ou nom avec virgule suivi d'une année entre parenthèses
        if re.match(r'^[A-Z][a-zA-Z\s,\.&]+,\s*\([0-9]{4}', line) or \
           re.match(r'^[A-Z][a-zA-Z\s,\.&]+\s+\([0-9]{4}', line):
            if current_ref:
                ref_text = ' '.join(current_ref)
                if ref_text and len(ref_text) > 20:
                    references.append(ref_text)
            current_ref = [line]
        elif current_ref:
            current_ref.append(line)
    
    # Ajouter la dernière référence
    if current_ref:
        ref_text = ' '.join(current_ref)
        if ref_text and len(ref_text) > 20:
            references.append(ref_text)
    
    return references

def parse_reference(ref_text):
    """Parse une référence pour extraire auteur, année, titre, DOI, etc."""
    # Extraire l'année
    year_match = re.search(r'\(([0-9]{4}[a-z]?)\)', ref_text)
    year = year_match.group(1) if year_match else ""
    
    # Extraire le DOI
    doi_match = re.search(r'https?://doi\.org/([^\s,]+)', ref_text)
    doi_url = doi_match.group(0) if doi_match else ""
    
    # Extraire les auteurs (avant l'année)
    if year_match:
        authors_part = ref_text[:year_match.start()].strip()
        # Nettoyer
        authors_part = re.sub(r'\s+', ' ', authors_part)
        # Prendre le premier auteur et "et al." si présent
        if ', ' in authors_part:
            first_author = authors_part.split(',')[0].strip()
            if 'et al' in authors_part.lower():
                authors = f"{first_author} et al."
            else:
                # Prendre les premiers auteurs
                authors_list = [a.strip() for a in authors_part.split(',')[:3]]
                authors = ', '.join(authors_list)
                if len(authors_part.split(',')) > 3:
                    authors += " et al."
        else:
            authors = authors_part
    else:
        authors = ref_text.split(',')[0] if ',' in ref_text else ref_text[:50]
    
    # Extraire le titre (généralement après l'année, avant le journal)
    title = ""
    if year_match:
        after_year = ref_text[year_match.end():].strip()
        # Le titre est généralement entre l'année et une virgule suivie d'un nom de journal
        # Chercher jusqu'à un pattern de journal (mots en majuscules ou patterns comme "J. Geophys.")
        title_match = re.match(r'^[^,]+', after_year)
        if title_match:
            title = title_match.group(0).strip()
            # Nettoyer
            title = re.sub(r'\s+', ' ', title)
            if len(title) > 100:
                title = title[:100] + "..."
    
    # Format de référence complet
    ref_display = f"{authors} ({year})"
    if title:
        ref_display += f" - {title}"
    
    return {
        'authors': authors,
        'year': year,
        'title': title,
        'doi': doi_url,
        'full_ref': ref_text,
        'display': ref_display
    }

def find_reference_citations(text, ref_parsed):
    """Trouve où et comment une référence est citée dans le texte."""
    # Chercher les citations de cette référence dans le texte
    # Patterns possibles : "Auteur (Année)", "Auteur et al. (Année)", etc.
    authors = ref_parsed['authors']
    year = ref_parsed['year']
    
    if not year:
        return []
    
    # Extraire le premier auteur
    first_author = authors.split(',')[0].strip()
    if ' et al' in authors.lower():
        pattern1 = rf"{re.escape(first_author)}\s+et\s+al\.?\s*\({re.escape(year)}\)"
    else:
        pattern1 = rf"{re.escape(first_author)}[^,]*\({re.escape(year)}\)"
    
    # Pattern alternatif : juste l'année si l'auteur est mentionné avant
    pattern2 = rf"\({re.escape(year)}\)"
    
    citations = []
    for pattern in [pattern1, pattern2]:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        for match in matches:
            # Extraire le contexte autour de la citation
            start = max(0, match.start() - 200)
            end = min(len(text), match.end() + 200)
            context = text[start:end]
            citations.append({
                'position': match.start(),
                'context': context
            })
    
    return citations

def analyze_reference_usage(text, ref_parsed):
    """Analyse comment une référence est utilisée dans l'article."""
    citations = find_reference_citations(text, ref_parsed)
    
    if not citations:
        return "Référence citée dans la bibliographie mais usage non détecté dans le texte", 30
    
    # Analyser le contexte de chaque citation
    usage_contexts = []
    for citation in citations[:3]:  # Limiter à 3 contextes
        context = citation['context'].lower()
        
        # Détecter le type d'utilisation
        if any(word in context for word in ['méthode', 'method', 'technique', 'approche', 'algorithme']):
            usage_contexts.append("justification de méthode")
        elif any(word in context for word in ['cadre', 'framework', 'théorie', 'theory', 'modèle', 'model']):
            usage_contexts.append("cadre théorique")
        elif any(word in context for word in ['résultat', 'result', 'comparaison', 'comparison', 'donnée', 'data']):
            usage_contexts.append("comparaison de résultats")
        elif any(word in context for word in ['hypothèse', 'hypothesis', 'appuie', 'support']):
            usage_contexts.append("appui d'hypothèse")
        elif any(word in context for word in ['exemple', 'example', 'cas', 'case', 'application']):
            usage_contexts.append("exemple ou application")
        else:
            usage_contexts.append("référence générale")
    
    # Déterminer l'importance (0-100)
    importance = 50  # Base
    if len(citations) > 5:
        importance = 85
    elif len(citations) > 2:
        importance = 70
    elif len(citations) > 0:
        importance = 50
    
    # Ajuster selon le type d'utilisation
    if "justification de méthode" in usage_contexts or "cadre théorique" in usage_contexts:
        importance = min(100, importance + 15)
    
    usage_description = ", ".join(set(usage_contexts)) if usage_contexts else "référence générale"
    
    return usage_description, importance

def categorize_theme(ref_parsed, usage_desc):
    """Catégorise une référence dans un thème (4-6 thèmes max)."""
    title_lower = ref_parsed['title'].lower()
    usage_lower = usage_desc.lower()
    full_text = (ref_parsed['full_ref'] + " " + usage_desc).lower()
    
    # Thèmes possibles (4-6 thèmes larges)
    if any(word in full_text for word in ['gnss', 'gps', 'acoustic', 'acoustique', 'positioning', 'positionnement', 'seafloor', 'fond de mer']):
        return "Méthodes GNSS-Acoustique"
    elif any(word in full_text for word in ['geodesy', 'géodésie', 'deformation', 'déformation', 'strain', 'fault', 'faille']):
        return "Géodésie des fonds marins"
    elif any(word in full_text for word in ['optimization', 'optimisation', 'processing', 'traitement', 'algorithm', 'algorithme', 'filter', 'filtre']):
        return "Optimisation et traitement de données"
    elif any(word in full_text for word in ['model', 'modèle', 'simulation', 'numerical', 'numérique', 'theoretical', 'théorique']):
        return "Modélisation et simulation"
    elif any(word in full_text for word in ['instrument', 'sensor', 'capteur', 'measurement', 'mesure', 'pressure', 'pression', 'tiltmeter']):
        return "Instruments et techniques de mesure"
    else:
        return "Applications et études de cas"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_references.py <pdf_text_file>")
        sys.exit(1)
    
    pdf_text_file = Path(sys.argv[1])
    if not pdf_text_file.exists():
        print(f"Erreur: Le fichier {pdf_text_file} n'existe pas")
        sys.exit(1)
    
    # Lire le texte du PDF (supposé déjà extrait)
    text = pdf_text_file.read_text(encoding='utf-8', errors='ignore')
    
    # Extraire les références
    print("Extraction des références...", file=sys.stderr)
    references = extract_references_from_text(text)
    print(f"{len(references)} références trouvées", file=sys.stderr)
    
    # Analyser chaque référence
    results = []
    for ref_text in references:
        ref_parsed = parse_reference(ref_text)
        usage_desc, importance = analyze_reference_usage(text, ref_parsed)
        theme = categorize_theme(ref_parsed, usage_desc)
        
        results.append({
            'reference': ref_parsed['display'],
            'theme': theme,
            'usage': usage_desc,
            'importance': importance,
            'year': ref_parsed['year'],
            'link': ref_parsed['doi']
        })
    
    # Générer le tableau markdown
    print("| Référence | Thème | Arguments étayés | Note d'importance | Année | Lien web |")
    print("|-----------|-------|------------------|-------------------|-------|----------|")
    
    for result in results:
        ref = result['reference'].replace('|', '\\|')
        theme = result['theme']
        usage = result['usage']
        importance = result['importance']
        year = result['year']
        link = result['link']
        
        print(f"| {ref} | {theme} | {usage} | {importance} | {year} | {link} |")
