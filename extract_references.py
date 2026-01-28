#!/usr/bin/env python3
"""
Script pour extraire les références bibliographiques d'un PDF scientifique
en utilisant Cursor CLI Agent.
"""

import sys
import subprocess
import os
import re
import glob
import shutil
import platform
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def get_agent_base_cmd():
    """
    Retourne la commande de base pour lancer Cursor CLI (agent)
    en fonction du système (Windows vs Linux/Mac).
    """
    system = platform.system()

    if system == "Windows":
        # Sur ta machine, agent est un script PowerShell (agent.ps1)
        # visible ici : C:\Users\hugor\AppData\Local\cursor-agent\agent.ps1
        # On essaie d'abord de le trouver via le PATH
        agent_script = shutil.which("agent.ps1")
        if not agent_script:
            agent_script = r"C:\Users\hugor\AppData\Local\cursor-agent\agent.ps1"

        return [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            agent_script,
        ]

    # Linux / Mac : utiliser le binaire 'agent' classique
    agent_bin = shutil.which("agent") or "agent"
    return [agent_bin]


def extract_table_from_response(response_text):
    """
    Extrait le tableau markdown de la réponse de l'agent.
    Gère les problèmes d'encodage.
    """
    # Essayer différents encodages si nécessaire
    if isinstance(response_text, bytes):
        try:
            response_text = response_text.decode('utf-8')
        except UnicodeDecodeError:
            try:
                response_text = response_text.decode('latin-1')
            except UnicodeDecodeError:
                response_text = response_text.decode('utf-8', errors='replace')
    
    # Chercher un tableau markdown
    # Pattern pour détecter un tableau markdown
    table_pattern = r'\|[^\n]+\|\s*\n\|[-\s:|]+\|\s*\n(?:\|[^\n]+\|\s*\n)+'
    
    matches = re.findall(table_pattern, response_text, re.MULTILINE)
    if matches:
        # Prendre le plus grand tableau trouvé
        table = max(matches, key=len)
        
        # Corriger les problèmes d'encodage courants
        table = table.replace('RÃ©fÃ©rence', 'Référence')
        table = table.replace('Arguments Ã©tayÃ©s', 'Arguments étayés')
        table = table.replace('Note d\'importance', "Note d'importance")
        table = table.replace('Lien web', 'Lien web')
        table = table.replace('ThÃ¨me', 'Thème')
        table = table.replace('AnnÃ©e', 'Année')
        
        return table.strip()
    
    # Si pas de tableau trouvé, chercher des lignes qui commencent par |
    lines = response_text.split('\n')
    table_lines = []
    in_table = False
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and '---' not in stripped:
            table_lines.append(line)
            in_table = True
        elif in_table and not stripped.startswith('|'):
            break
    
    if len(table_lines) >= 2:  # Au moins header + séparateur
        table = '\n'.join(table_lines)
        # Corriger l'encodage
        table = table.replace('RÃ©fÃ©rence', 'Référence')
        table = table.replace('Arguments Ã©tayÃ©s', 'Arguments étayés')
        return table.strip()
    
    return None


def parse_markdown_table(table_content):
    """
    Parse un tableau markdown et retourne (headers, data_rows).
    Gère les problèmes d'encodage.
    """
    if not table_content:
        return [], []
    
    # Corriger l'encodage si nécessaire
    if isinstance(table_content, bytes):
        try:
            table_content = table_content.decode('utf-8')
        except UnicodeDecodeError:
            table_content = table_content.decode('latin-1')
    
    lines = [line.strip() for line in table_content.split('\n') if line.strip()]
    
    if len(lines) < 2:
        return [], []
    
    # Ignorer la ligne de séparation (---)
    data_lines = [line for line in lines if not re.match(r'^[\|\s\-:]+$', line)]
    
    if not data_lines:
        return [], []
    
    # Parser les headers
    header_line = data_lines[0]
    headers = [cell.strip() for cell in header_line.split('|')[1:-1]]
    
    # Corriger l'encodage des headers
    headers = [h.replace('RÃ©fÃ©rence', 'Référence')
               .replace('Arguments Ã©tayÃ©s', 'Arguments étayés')
               .replace('Note d\'importance', "Note d'importance")
               .replace('ThÃ¨me', 'Thème')
               .replace('AnnÃ©e', 'Année') for h in headers]
    
    # Parser les lignes de données
    data_rows = []
    for line in data_lines[1:]:
        cells = [cell.strip() for cell in line.split('|')[1:-1]]
        if len(cells) == len(headers):
            # Corriger l'encodage
            cells = [c.replace('RÃ©fÃ©rence', 'Référence')
                    .replace('Arguments Ã©tayÃ©s', 'Arguments étayés')
                    .replace('ThÃ¨me', 'Thème')
                    .replace('AnnÃ©e', 'Année') for c in cells]
            data_rows.append(cells)
    
    return headers, data_rows


def get_theme_colors():
    """Retourne une palette de couleurs pastel pour les thèmes."""
    colors_list = [
        '#E8F4F8',  # Bleu clair
        '#FFF4E6',  # Orange clair
        '#F0F8E8',  # Vert clair
        '#F8E8F0',  # Rose clair
        '#E8F0F8',  # Bleu ciel
        '#FFF8E8',  # Jaune clair
        '#F0E8F8',  # Violet clair
        '#E8F8F0',  # Vert menthe
    ]
    
    if REPORTLAB_AVAILABLE:
        return [colors.HexColor(c) for c in colors_list]
    return colors_list


def assign_theme_colors(headers, data_rows):
    """Assigne une couleur à chaque thème unique."""
    theme_idx = None
    try:
        theme_idx = headers.index('Thème')
    except ValueError:
        return {}
    
    # Collecter tous les thèmes uniques
    themes = set()
    for row in data_rows:
        if theme_idx < len(row):
            themes.add(row[theme_idx].strip())
    
    # Assigner une couleur à chaque thème
    theme_colors = get_theme_colors()
    theme_color_map = {}
    for i, theme in enumerate(sorted(themes)):
        theme_color_map[theme] = theme_colors[i % len(theme_colors)]
    
    return theme_color_map


def consolidate_themes(headers, data_rows, max_themes=6):
    """Consolide les thèmes pour ne pas dépasser max_themes en regroupant les thèmes similaires."""
    theme_idx = None
    try:
        theme_idx = headers.index('Thème')
    except ValueError:
        return headers, data_rows
    
    # Compter les occurrences de chaque thème
    theme_counts = {}
    for row in data_rows:
        if theme_idx < len(row):
            theme = row[theme_idx].strip()
            theme_counts[theme] = theme_counts.get(theme, 0) + 1
    
    # Si on a déjà <= max_themes, pas besoin de consolidation
    if len(theme_counts) <= max_themes:
        return headers, data_rows
    
    # Trier les thèmes par fréquence
    sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)
    
    # Garder les max_themes thèmes les plus fréquents
    main_themes = [theme for theme, count in sorted_themes[:max_themes]]
    other_themes = [theme for theme, count in sorted_themes[max_themes:]]
    
    # Créer un thème "Autre" pour regrouper les thèmes moins fréquents
    if other_themes:
        # Mapper les thèmes "Autre" vers le thème principal le plus proche ou créer "Autre"
        theme_mapping = {theme: theme for theme in main_themes}
        theme_mapping['Autre'] = 'Autre'
        
        # Mapper tous les thèmes "Autre" vers "Autre"
        for theme in other_themes:
            theme_mapping[theme] = 'Autre'
        
        # Appliquer le mapping
        for row in data_rows:
            if theme_idx < len(row):
                original_theme = row[theme_idx].strip()
                if original_theme in theme_mapping:
                    row[theme_idx] = theme_mapping[original_theme]
    
    return headers, data_rows


def extract_year(row, year_idx):
    """Extrait l'année d'une ligne du tableau."""
    if year_idx is None or year_idx >= len(row):
        return None
    
    year_str = row[year_idx].strip()
    if not year_str:
        return None
    
    # Essayer d'extraire un nombre de 4 chiffres
    year_match = re.search(r'\b(19|20)\d{2}\b', year_str)
    if year_match:
        return int(year_match.group())
    
    try:
        year = int(year_str)
        if 1900 <= year <= 2100:
            return year
    except ValueError:
        pass
    
    return None


def sort_references_by_theme_and_year(headers, data_rows):
    """Trie les références par thème puis par année."""
    theme_idx = None
    year_idx = None
    
    try:
        theme_idx = headers.index('Thème')
    except ValueError:
        pass
    
    try:
        year_idx = headers.index('Année')
    except ValueError:
        pass
    
    def get_theme(row):
        if theme_idx is not None and theme_idx < len(row):
            return row[theme_idx].strip()
        return ""
    
    def get_year(row):
        year = extract_year(row, year_idx)
        return year if year else 0
    
    sorted_rows = sorted(data_rows, key=lambda row: (get_theme(row), get_year(row)))
    
    return headers, sorted_rows


def save_table_to_pdf(table_content, output_path):
    """Sauvegarde le tableau dans un fichier PDF."""
    if not REPORTLAB_AVAILABLE:
        # Fallback: sauvegarder en markdown si reportlab n'est pas disponible
        md_path = output_path.with_suffix('.md')
        md_path.write_text(table_content, encoding='utf-8')
        print(f"\n⚠️  reportlab n'est pas installé. Tableau sauvegardé en Markdown: {md_path}")
        print("   Installez reportlab avec: pip install reportlab")
        return
    
    headers, data_rows = parse_markdown_table(table_content)
    
    if not headers or not data_rows:
        print("\n⚠️  Impossible de parser le tableau. Sauvegarde en Markdown...")
        md_path = output_path.with_suffix('.md')
        md_path.write_text(table_content, encoding='utf-8')
        print(f"✓ Tableau sauvegardé dans: {md_path}")
        return
    
    # Trier par thème puis par année
    headers, data_rows = sort_references_by_theme_and_year(headers, data_rows)
    # Consolider les thèmes si nécessaire (max 6 thèmes)
    headers, data_rows = consolidate_themes(headers, data_rows, max_themes=6)
    # Assigner des couleurs aux thèmes
    theme_color_map = assign_theme_colors(headers, data_rows)
    
    # Créer le document PDF
    doc = SimpleDocTemplate(str(output_path), pagesize=A4)
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#2C3E50'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=9,
        leading=11
    )
    
    # Titre
    title = Paragraph("Références Bibliographiques", title_style)
    story.append(title)
    story.append(Spacer(1, 0.2*inch))
    
    # Préparer les données du tableau
    table_data = []
    
    # En-têtes avec couleurs
    header_row = []
    for header in headers:
        header_para = Paragraph(f"<b>{header}</b>", normal_style)
        header_row.append(header_para)
    table_data.append(header_row)
    
    # Lignes de données avec couleurs par thème
    theme_idx = None
    try:
        theme_idx = headers.index('Thème')
    except ValueError:
        pass
    
    url_idx = None
    try:
        url_idx = headers.index('Lien web')
    except ValueError:
        pass
    
    for row in data_rows:
        data_row = []
        row_theme = None
        
        if theme_idx is not None and theme_idx < len(row):
            row_theme = row[theme_idx].strip()
        
        for i, cell in enumerate(row):
            # Créer un paragraphe pour chaque cellule
            cell_text = str(cell) if cell else ""
            
            # Si c'est une URL, la rendre cliquable dans le PDF
            if url_idx is not None and i == url_idx and cell_text.startswith('http'):
                cell_text = f'<link href="{cell_text}" color="blue"><u>{cell_text}</u></link>'
            
            # Limiter la longueur pour éviter les débordements
            if len(cell_text) > 200:
                cell_text = cell_text[:197] + "..."
            
            para = Paragraph(cell_text, normal_style)
            data_row.append(para)
        
        table_data.append(data_row)
    
    # Créer le tableau
    num_cols = len(headers)
    col_widths = [doc.width / num_cols] * num_cols
    
    # Ajuster les largeurs selon le contenu
    if num_cols >= 6:
        # Référence: 25%, Thème: 15%, Arguments: 30%, Note: 8%, Année: 7%, Lien: 15%
        col_widths = [
            doc.width * 0.25,
            doc.width * 0.15,
            doc.width * 0.30,
            doc.width * 0.08,
            doc.width * 0.07,
            doc.width * 0.15
        ]
    elif num_cols == 5:
        col_widths = [
            doc.width * 0.25,
            doc.width * 0.15,
            doc.width * 0.35,
            doc.width * 0.10,
            doc.width * 0.15
        ]
    
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    # Style du tableau
    table_style = TableStyle([
        # En-tête
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495E')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        # Données
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
    ])
    
    # Appliquer les couleurs par thème
    if theme_idx is not None:
        current_theme = None
        theme_start_row = 1
        
        for row_idx, row in enumerate(data_rows, start=1):
            if theme_idx < len(row):
                row_theme = row[theme_idx].strip()
                
                if row_theme != current_theme:
                    # Appliquer la couleur au groupe précédent
                    if current_theme and current_theme in theme_color_map:
                        color = theme_color_map[current_theme]
                        if isinstance(color, str):
                            color = colors.HexColor(color)
                        table_style.add('BACKGROUND', (0, theme_start_row), (-1, row_idx - 1), color)
                    
                    current_theme = row_theme
                    theme_start_row = row_idx
        
        # Appliquer la couleur au dernier groupe
        if current_theme and current_theme in theme_color_map:
            color = theme_color_map[current_theme]
            if isinstance(color, str):
                color = colors.HexColor(color)
            table_style.add('BACKGROUND', (0, theme_start_row), (-1, len(data_rows)), color)
    
    table.setStyle(table_style)
    story.append(table)
    
    # Légende des couleurs
    if theme_color_map:
        story.append(Spacer(1, 0.3*inch))
        legend_title = Paragraph("<b>Légende des thèmes</b>", normal_style)
        story.append(legend_title)
        story.append(Spacer(1, 0.1*inch))
        
        legend_data = []
        for theme, color in sorted(theme_color_map.items()):
            if isinstance(color, str):
                color = colors.HexColor(color)
            legend_data.append([
                Paragraph(f'<para backColor="{color.hexval()}" textColor="black">  </para>', normal_style),
                Paragraph(theme, normal_style)
            ])
        
        legend_table = Table(legend_data, colWidths=[0.5*inch, 4*inch])
        legend_style = TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ])
        legend_table.setStyle(legend_style)
        story.append(legend_table)
    
    # Générer le PDF
    doc.build(story)
    print(f"✓ Tableau sauvegardé dans: {output_path}")


def save_table_to_html(headers, data_rows, theme_color_map, output_path):
    """Génère un fichier HTML interactif avec tri et filtrage."""
    # Trier par thème puis par année
    headers, data_rows = sort_references_by_theme_and_year(headers, data_rows)
    # Consolider les thèmes si nécessaire (max 6 thèmes)
    headers, data_rows = consolidate_themes(headers, data_rows, max_themes=6)
    
    # Trouver les indices des colonnes
    theme_idx = None
    importance_idx = None
    year_idx = None
    url_idx = None
    
    try:
        theme_idx = headers.index('Thème')
    except ValueError:
        pass
    
    try:
        importance_idx = headers.index('Note d\'importance')
    except ValueError:
        try:
            importance_idx = headers.index("Note d'importance")
        except ValueError:
            pass
    
    try:
        year_idx = headers.index('Année')
    except ValueError:
        pass
    
    try:
        url_idx = headers.index('Lien web')
    except ValueError:
        pass
    
    # Générer les couleurs CSS pour les thèmes
    theme_css = ""
    for theme, color in theme_color_map.items():
        # Récupérer une chaîne hexadécimale depuis reportlab ou une chaîne brute
        if isinstance(color, str):
            hex_color = color
        else:
            hex_color = color.hexval()  # souvent du type "0xe8f4f8"
        
        hex_str = str(hex_color)
        # Enlever le préfixe 0x si présent (reportlab)
        if hex_str.lower().startswith("0x"):
            hex_str = hex_str[2:]
        # Ajouter le # si absent
        if not hex_str.startswith("#"):
            hex_str = f"#{hex_str}"
        
        # Nettoyer le nom du thème pour CSS
        theme_class = re.sub(r'[^a-zA-Z0-9]', '_', theme)
        theme_css += f"    .theme-{theme_class} {{ background-color: {hex_str}; }}\n"
    
    # Générer les lignes du tableau
    table_rows = ""
    for i, row in enumerate(data_rows):
        theme_class = ""
        if theme_idx is not None and theme_idx < len(row):
            theme = row[theme_idx].strip()
            theme_class = re.sub(r'[^a-zA-Z0-9]', '_', theme)
        
        row_html = "        <tr"
        if theme_class:
            row_html += f' class="theme-{theme_class}"'
        row_html += ">\n"
        
        for j, cell in enumerate(row):
            cell_text = str(cell) if cell else ""
            # Échapper les caractères HTML
            cell_text = cell_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
            
            # Préparer les attributs data pour les couleurs
            data_attrs = ""
            
            # Si c'est la colonne Note d'importance, extraire la valeur numérique
            if importance_idx is not None and j == importance_idx:
                try:
                    importance_value = int(re.search(r'\d+', cell_text).group())
                    data_attrs = f' data-importance="{importance_value}"'
                except:
                    pass
            
            # Si c'est la colonne Année, extraire la valeur numérique
            if year_idx is not None and j == year_idx:
                try:
                    year_value = int(re.search(r'\b(19|20)\d{2}\b', cell_text).group())
                    data_attrs = f' data-year="{year_value}"'
                except:
                    pass
            
            # Si c'est une URL, la rendre cliquable
            if url_idx is not None and j == url_idx and cell_text.startswith('http'):
                cell_text = f'<a href="{cell_text}" target="_blank">{cell_text}</a>'
            
            row_html += f"            <td{data_attrs}>{cell_text}</td>\n"
        
        row_html += "        </tr>\n"
        table_rows += row_html
    
    # Préparer les infos pour les couleurs côté JS
    theme_col_index_js = theme_idx if theme_idx is not None else -1
    theme_js_entries = []
    for theme, color in theme_color_map.items():
        if isinstance(color, str):
            hex_color = color
        else:
            hex_color = color.hexval()
        hex_str = str(hex_color)
        if hex_str.lower().startswith("0x"):
            hex_str = hex_str[2:]
        if not hex_str.startswith("#"):
            hex_str = f"#{hex_str}"
        safe_theme = theme.replace('\\', '\\\\').replace('"', '\\"')
        theme_js_entries.append(f'"{safe_theme}": "{hex_str}"')
    theme_js_map = "{ " + ", ".join(theme_js_entries) + " }" if theme_js_entries else "{}"
    
    # Générer le HTML complet
    html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Références Bibliographiques</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        .header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        
        .controls {{
            padding: 20px;
            background: #f8f9fa;
            border-bottom: 2px solid #e9ecef;
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            align-items: center;
        }}
        
        .control-group {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .control-group label {{
            font-size: 14px;
            font-weight: 600;
            color: #495057;
        }}
        
        .control-group input,
        .control-group select {{
            padding: 8px 12px;
            border: 2px solid #dee2e6;
            border-radius: 5px;
            font-size: 14px;
            transition: border-color 0.3s;
        }}
        
        .control-group input:focus,
        .control-group select:focus {{
            outline: none;
            border-color: #667eea;
        }}
        
        .stats {{
            margin-left: auto;
            font-size: 14px;
            color: #6c757d;
            font-weight: 600;
        }}
        
        .table-container {{
            max-height: 70vh;
            overflow-y: auto;
            overflow-x: auto;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        
        thead {{
            position: sticky;
            top: 0;
            z-index: 10;
        }}
        
        th {{
            background: #34495e;
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
            cursor: pointer;
            user-select: none;
            transition: background-color 0.3s;
        }}
        
        th:hover {{
            background: #2c3e50;
        }}
        
        th.sortable::after {{
            content: ' ↕';
            opacity: 0.5;
            font-size: 0.8em;
        }}
        
        th.sort-asc::after {{
            content: ' ↑';
            opacity: 1;
        }}
        
        th.sort-desc::after {{
            content: ' ↓';
            opacity: 1;
        }}
        
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #e9ecef;
            vertical-align: top;
        }}
        
        tr:hover {{
            background-color: #f8f9fa;
        }}
        
        tr.hidden {{
            display: none;
        }}
        
        a {{
            color: #667eea;
            text-decoration: none;
            word-break: break-all;
        }}
        
        a:hover {{
            text-decoration: underline;
        }}
        
        .legend {{
            padding: 20px;
            background: #f8f9fa;
            border-top: 2px solid #e9ecef;
        }}
        
        .legend h3 {{
            font-size: 2em;
            margin-bottom: 15px;
            color: #495057;
        }}
        
        .legend-items {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.9em;
        }}
        
        .legend-color {{
            width: 30px;
            height: 20px;
            border-radius: 4px;
            border: 1px solid #dee2e6;
        }}
        
        {theme_css}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Références Bibliographiques</h1>
            <p>Tableau interactif avec tri et filtrage</p>
        </div>
        
        <div class="controls">
            <div class="control-group">
                <label for="themeFilter">Filtrer par thème:</label>
                <select id="themeFilter">
                    <option value="">Tous les thèmes</option>
"""
    
    # Ajouter les options de thème
    themes = sorted(set([row[theme_idx].strip() for row in data_rows if theme_idx is not None and theme_idx < len(row)]))
    for theme in themes:
        html_content += f'                    <option value="{theme}">{theme}</option>\n'
    
    html_content += """                </select>
            </div>
            
            <div class="control-group">
                <label for="importanceFilter">Note min:</label>
                <input type="number" id="importanceFilter" min="0" max="100" value="0">
            </div>
            
            <div class="control-group">
                <label for="searchBox">Rechercher:</label>
                <input type="text" id="searchBox" placeholder="Texte à rechercher...">
            </div>
            
            <div class="stats">
                <span id="statsText">0 référence(s) affichée(s)</span>
            </div>
        </div>
        
        <div class="table-container">
            <table id="referencesTable">
                <thead>
                    <tr>
"""
    
    # Générer les en-têtes
    for header in headers:
        header_clean = header.replace("'", "\\'")
        html_content += f'                        <th class="sortable" onclick="sortTable({headers.index(header)})">{header}</th>\n'
    
    html_content += """                    </tr>
                </thead>
                <tbody>
"""
    
    html_content += table_rows
    
    html_content += """                </tbody>
            </table>
        </div>
        
        <div class="legend">
            <h3>Légende des thèmes</h3>
            <div class="legend-items">
"""
    
    # Générer la légende
    for theme, color in sorted(theme_color_map.items()):
        if isinstance(color, str):
            hex_color = color
        else:
            hex_color = color.hexval()
        theme_class = re.sub(r'[^a-zA-Z0-9]', '_', theme)
        html_content += f'                <div class="legend-item">\n'
        html_content += f'                    <div class="legend-color theme-{theme_class}"></div>\n'
        html_content += f'                    <span>{theme}</span>\n'
        html_content += f'                </div>\n'
    
    html_content += """            </div>
        </div>
    </div>
    
"""
    # Script JS avec injection des valeurs Python (indice de colonne thème + couleurs)
    html_content += f"""    <script>
        const THEME_COL_INDEX = {theme_col_index_js};
        const themeColors = {theme_js_map};
"""
    html_content += """
        let currentSort = { column: -1, direction: 'asc' };
        let allRows = Array.from(document.querySelectorAll('#referencesTable tbody tr'));
        
        function updateStats() {
            const visibleRows = allRows.filter(row => !row.classList.contains('hidden'));
            document.getElementById('statsText').textContent = `${visibleRows.length} référence(s) affichée(s)`;
        }
        
        function sortTable(columnIndex) {
            const tbody = document.querySelector('#referencesTable tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            
            // Déterminer la direction de tri
            if (currentSort.column === columnIndex) {
                currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
            } else {
                currentSort.column = columnIndex;
                currentSort.direction = 'asc';
            }
            
            // Mettre à jour les indicateurs visuels
            document.querySelectorAll('th').forEach((th, idx) => {
                th.classList.remove('sort-asc', 'sort-desc');
                if (idx === columnIndex) {
                    th.classList.add(`sort-${currentSort.direction}`);
                }
            });
            
            // Trier les lignes
            rows.sort((a, b) => {
                const aCell = a.cells[columnIndex]?.textContent.trim() || '';
                const bCell = b.cells[columnIndex]?.textContent.trim() || '';
                
                // Essayer de parser comme nombre (pour Note d'importance, Année)
                const aNum = parseFloat(aCell);
                const bNum = parseFloat(bCell);
                
                if (!isNaN(aNum) && !isNaN(bNum)) {
                    return currentSort.direction === 'asc' ? aNum - bNum : bNum - aNum;
                }
                
                // Sinon, tri alphabétique
                return currentSort.direction === 'asc' 
                    ? aCell.localeCompare(bCell, 'fr', { numeric: true })
                    : bCell.localeCompare(aCell, 'fr', { numeric: true });
            });
            
            // Réorganiser les lignes dans le DOM
            rows.forEach(row => tbody.appendChild(row));
            updateStats();
            applyCellColors(); // Réappliquer les couleurs après le tri
        }
        
        function filterTable() {
            const themeFilter = document.getElementById('themeFilter').value;
            const importanceFilter = parseInt(document.getElementById('importanceFilter').value) || 0;
            const searchText = document.getElementById('searchBox').value.toLowerCase();
            
            // Trouver les indices des colonnes
            const headers = Array.from(document.querySelectorAll('#referencesTable thead th'));
            const themeHeaderIndex = headers.findIndex(th => th.textContent.includes('Thème'));
            const importanceHeaderIndex = headers.findIndex(th => th.textContent.includes('Note') || th.textContent.includes('importance'));
            
            allRows.forEach(row => {
                let show = true;
                
                // Filtre par thème
                if (themeFilter && themeHeaderIndex >= 0) {
                    const themeCell = row.cells[themeHeaderIndex]?.textContent.trim() || '';
                    if (themeCell !== themeFilter) {
                        show = false;
                    }
                }
                
                // Filtre par note d'importance
                if (show && importanceHeaderIndex >= 0) {
                    const importanceCell = row.cells[importanceHeaderIndex]?.textContent.trim() || '';
                    const importance = parseInt(importanceCell) || 0;
                    if (importance < importanceFilter) {
                        show = false;
                    }
                }
                
                // Filtre par recherche textuelle
                if (show && searchText) {
                    const rowText = Array.from(row.cells).map(cell => cell.textContent).join(' ').toLowerCase();
                    if (!rowText.includes(searchText)) {
                        show = false;
                    }
                }
                
                if (show) {
                    row.classList.remove('hidden');
                } else {
                    row.classList.add('hidden');
                }
            });
            
            updateStats();
            applyCellColors(); // Réappliquer les couleurs après le filtrage
        }
        
        // Fonction pour calculer la couleur d'une note (rouge -> vert)
        function getImportanceColor(value) {
            // Normaliser entre 0 et 100
            const normalized = Math.max(0, Math.min(100, value)) / 100;
            // Rouge (faible) -> Vert (élevé)
            const red = Math.round(255 * (1 - normalized));
            const green = Math.round(255 * normalized);
            const blue = 0;
            return `rgb(${red}, ${green}, ${blue})`;
        }
        
        // Fonction pour calculer la couleur d'une année (violet -> jaune)
        function getYearColor(year) {
            // Trouver les années min et max dans le tableau
            const yearCells = Array.from(document.querySelectorAll('td[data-year]'));
            const years = yearCells.map(cell => parseInt(cell.getAttribute('data-year'))).filter(y => !isNaN(y));
            if (years.length === 0) return 'rgb(128, 0, 128)'; // Violet par défaut
            
            const minYear = Math.min(...years);
            const maxYear = Math.max(...years);
            
            if (minYear === maxYear) return 'rgb(255, 255, 0)'; // Jaune si une seule année
            
            // Normaliser entre 0 et 1
            const normalized = (year - minYear) / (maxYear - minYear);
            
            // Violet (ancien) -> Jaune (récent)
            // Violet: rgb(128, 0, 128), Jaune: rgb(255, 255, 0)
            const red = Math.round(128 + (255 - 128) * normalized);
            const green = Math.round(0 + 255 * normalized);
            const blue = Math.round(128 * (1 - normalized));
            return `rgb(${red}, ${green}, ${blue})`;
        }
        
        // Appliquer les couleurs aux cellules
        function applyCellColors() {
            // Pré-calcul des indices de colonnes Référence / Thème / Arguments
            const headerCells = Array.from(document.querySelectorAll('#referencesTable thead th'));
            const refColIndex = headerCells.findIndex(th => th.textContent.includes('Référence'));
            const themeColIndex = headerCells.findIndex(th => th.textContent.includes('Thème'));
            const argsColIndex = headerCells.findIndex(th => th.textContent.includes('Arguments étayés'));
            
            // Couleurs pour les notes d'importance
            document.querySelectorAll('td[data-importance]').forEach(cell => {
                const importance = parseInt(cell.getAttribute('data-importance'));
                if (!isNaN(importance)) {
                    const color = getImportanceColor(importance);
                    cell.style.backgroundColor = color;
                    cell.style.color = importance < 50 ? 'white' : 'black'; // Texte blanc si fond sombre
                    cell.style.fontWeight = 'bold';
                }
            });
            
            // Couleurs pour les années
            document.querySelectorAll('td[data-year]').forEach(cell => {
                const year = parseInt(cell.getAttribute('data-year'));
                if (!isNaN(year)) {
                    const color = getYearColor(year);
                    cell.style.backgroundColor = color;
                    cell.style.color = 'black';
                    cell.style.fontWeight = 'bold';
                }
            });
            
            // Couleurs pour les thèmes (Référence + Thème + Arguments étayés)
            if (typeof THEME_COL_INDEX !== 'undefined' && THEME_COL_INDEX >= 0) {
                document.querySelectorAll('#referencesTable tbody tr').forEach(row => {
                    const themeCell = row.cells[THEME_COL_INDEX];
                    if (!themeCell) return;
                    const theme = themeCell.textContent.trim();
                    if (theme && themeColors[theme]) {
                        const colsToColor = [refColIndex, themeColIndex, argsColIndex].filter(idx => idx >= 0);
                        colsToColor.forEach(idx => {
                            const c = row.cells[idx];
                            if (!c) return;
                            c.style.backgroundColor = themeColors[theme];
                            c.style.fontWeight = 'bold';
                        });
                    }
                });
            }
        }
        
        // Événements
        document.getElementById('themeFilter').addEventListener('change', filterTable);
        document.getElementById('importanceFilter').addEventListener('input', filterTable);
        document.getElementById('searchBox').addEventListener('input', filterTable);
        
        // Initialiser les statistiques et appliquer les couleurs
        updateStats();
        applyCellColors();
    </script>
</body>
</html>"""
    
    output_path.write_text(html_content, encoding='utf-8')
    print(f"✓ Tableau HTML interactif sauvegardé dans: {output_path}")


def save_table_to_file(table_content, output_path):
    """Sauvegarde le tableau dans un fichier PDF, HTML et Markdown."""
    # Sauvegarder le PDF
    save_table_to_pdf(table_content, output_path)
    
    # Sauvegarder aussi le Markdown (nécessaire pour la fusion)
    md_path = output_path.with_suffix('.md')
    md_path.write_text(table_content, encoding='utf-8')
    print(f"✓ Tableau Markdown sauvegardé dans: {md_path.name}")
    
    # Sauvegarder aussi le HTML
    headers, data_rows = parse_markdown_table(table_content)
    if headers and data_rows:
        # Trier par thème puis par année
        headers, data_rows = sort_references_by_theme_and_year(headers, data_rows)
        # Consolider les thèmes si nécessaire (max 6 thèmes)
        headers, data_rows = consolidate_themes(headers, data_rows, max_themes=6)
        # Assigner des couleurs aux thèmes
        theme_color_map = assign_theme_colors(headers, data_rows)
        # Générer le HTML
        html_path = output_path.with_suffix('.html')
        save_table_to_html(headers, data_rows, theme_color_map, html_path)


def get_prompt():
    """Retourne le prompt pour l'agent Cursor."""
    return """tu es un agent IA qui est spécialisé dans l'extraction de référence bibliographique. Ton role est, à la récéption d'un pdf d'un article scientifique, de créer un tableau listant les références bibliographiques et résumant quels arguments DE L'ARTICLE ANALYSÉ (pas de l'article référencé) chaque référence sert à étayer.

FORMAT DE SORTIE OBLIGATOIRE - Réponds UNIQUEMENT avec un tableau markdown au format suivant (sans texte avant ou après, sans formules de politesse) :

| Référence | Thème | Arguments étayés | Note d'importance | Année | Lien web |
|-----------|-------|------------------|-------------------|-------|----------|
| Auteur1 et al. (2020) - Titre | Thème principal | Utilisée pour justifier la méthode X dans l'article analysé, appuie l'hypothèse Y | 85 | 2020 | https://example.com/article1 |
| Auteur2 et al. (2018) - Titre | Autre thème | Fournit le cadre théorique pour l'approche Z, permet de comparer les résultats | 70 | 2018 | https://example.com/article2 |

Règles strictes :
- Commence directement par le tableau (pas de texte d'introduction)
- Utilise exactement le format markdown ci-dessus avec les colonnes : "Référence", "Thème", "Arguments étayés", "Note d'importance", "Année", "Lien web"
- Chaque référence doit être sur une seule ligne
- Thème : Identifie le thème principal de l'argument étayé. CONTRAINTE STRICTE ET OBLIGATOIRE : Tu dois utiliser EXACTEMENT entre 4 et 6 thèmes différents pour TOUT le document. Pas plus de 6 thèmes, pas moins de 4 thèmes. C'est une règle absolue. Regroupe les références similaires sous les mêmes thèmes généraux et larges. Évite absolument les thèmes trop spécifiques qui ne concernent qu'une seule ou deux références. Exemples de thèmes larges possibles : "Méthodes GNSS-Acoustic", "Géodésie des fonds marins", "Optimisation et traitement de données", "Modélisation et simulation", "Instruments et techniques de mesure", "Applications et études de cas". PROCESSUS OBLIGATOIRE : 1) Analyse d'abord TOUTES les références du document, 2) Identifie les 4 à 6 thèmes principaux et larges qui couvrent toutes les références, 3) Assigne ensuite chaque référence à l'un de ces thèmes. Ne crée jamais plus de 6 thèmes différents.
- Note d'importance : Un nombre entre 0 et 100 indiquant l'importance de la référence pour l'article (100 = très importante, 0 = peu importante)
- Année : L'année de publication de la référence (extraite du format Auteur (Année))
- Lien web : URL complète vers la page de l'article. Cherche d'abord dans le document PDF (DOI, URL dans les références), sinon recherche sur internet (Google Scholar, DOI.org, etc.). Si aucun lien n'est trouvé, laisse vide.
- Arguments étayés : Décris PRÉCISÉMENT quels arguments, hypothèses, méthodes ou conclusions DE L'ARTICLE ANALYSÉ (celui que tu lis actuellement) cette référence sert à étayer ou à appuyer. IMPORTANT : Ne décris PAS le contenu général de l'article référencé, mais explique comment et pourquoi cette référence est utilisée dans l'article analysé. Identifie le contexte d'utilisation dans l'article analysé : est-ce pour justifier une méthode utilisée dans l'article ? Appuyer une hypothèse formulée dans l'article ? Comparer des résultats obtenus dans l'article ? Fournir un cadre théorique pour l'approche de l'article ? Donner un exemple ou un précédent ? Les arguments doivent être concis mais précis, et doivent clairement montrer le rôle de la référence dans l'argumentation et la démonstration de l'article analysé. Focus sur "comment cette référence sert l'article analysé" et non "ce que dit l'article référencé".
- Ne termine pas par du texte supplémentaire ou des formules de politesse
- Le tableau doit être complet et listant TOUTES les références bibliographiques du document"""


def process_pdf(pdf_path):
    """Traite un seul PDF et génère les fichiers de sortie."""
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        return f"❌ Erreur: Le fichier '{pdf_path}' n'existe pas."
    
    if not pdf_path.suffix.lower() == '.pdf':
        return f"❌ Erreur: Le fichier '{pdf_path}' n'est pas un PDF."
    
    prompt = get_prompt()
    pdf_abs_path = pdf_path.resolve()
    output_path = pdf_path.parent / f"{pdf_path.stem}_references.pdf"
    
    try:
        print(f"[{pdf_path.name}] Traitement en cours...")
        full_prompt = f'{prompt}\n\nFichier PDF à analyser: {pdf_abs_path}'

        # Construire la commande de base pour lancer Cursor CLI
        base_cmd = get_agent_base_cmd()
        cmd = base_cmd + ['--model', 'auto', 'chat', full_prompt]
        
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
                return f"✓ [{pdf_path.name}] Traitement terminé: {output_path.name}"
            else:
                md_path = output_path.with_suffix('.md')
                md_path.write_text(result.stdout, encoding='utf-8')
                return f"⚠️  [{pdf_path.name}] Aucun tableau détecté. Réponse sauvegardée: {md_path.name}"
        else:
            return f"❌ [{pdf_path.name}] Erreur lors du traitement (code {result.returncode})"
            
    except Exception as e:
        return f"❌ [{pdf_path.name}] Erreur: {e}"


def expand_glob_patterns(args):
    """
    Développe les patterns glob en listes de fichiers.
    Retourne une liste de chemins Path.
    """
    expanded_files = []
    for arg in args:
        # Vérifier si l'argument contient des caractères de pattern glob
        if '*' in arg or '?' in arg or '[' in arg:
            # C'est un pattern glob, le développer
            matches = glob.glob(arg, recursive=True)
            if matches:
                expanded_files.extend([Path(match) for match in matches])
            else:
                print(f"⚠️  Aucun fichier trouvé pour le pattern: {arg}")
        else:
            # C'est un chemin normal
            expanded_files.append(Path(arg))
    
    return expanded_files


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_references.py <chemin_vers_pdf> [<pdf2> ... <pdfN>]")
        print("       python extract_references.py <pattern_glob> [<pattern2> ...]")
        print("Exemple: python extract_references.py article.pdf")
        print("Exemple: python extract_references.py article1.pdf article2.pdf article3.pdf")
        print("Exemple: python extract_references.py articles/*.pdf")
        print("Exemple: python extract_references.py articles/**/*.pdf")
        sys.exit(1)
    
    # Développer les patterns glob en listes de fichiers
    pdf_files = expand_glob_patterns(sys.argv[1:])
    
    # Vérifier que tous les fichiers existent et sont des PDF
    valid_pdfs = []
    for pdf_path in pdf_files:
        if not pdf_path.exists():
            print(f"⚠️  Ignoré: Le fichier '{pdf_path}' n'existe pas.")
            continue
        if not pdf_path.suffix.lower() == '.pdf':
            print(f"⚠️  Ignoré: Le fichier '{pdf_path}' n'est pas un PDF.")
            continue
        valid_pdfs.append(pdf_path)
    
    if not valid_pdfs:
        print("❌ Aucun fichier PDF valide à traiter.")
        sys.exit(1)
    
    print(f"📚 Traitement de {len(valid_pdfs)} fichier(s) PDF en parallèle...\n")
    
    # Traiter les PDF en parallèle
    max_workers = min(len(valid_pdfs), 4)  # Maximum 4 traitements en parallèle
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Lancer tous les traitements
        future_to_pdf = {executor.submit(process_pdf, pdf): pdf for pdf in valid_pdfs}
        
        # Afficher les résultats au fur et à mesure
        for future in as_completed(future_to_pdf):
            pdf = future_to_pdf[future]
            try:
                result = future.result()
                print(result)
            except Exception as e:
                print(f"❌ [{pdf.name}] Exception: {e}")
    
    print(f"\n✅ Traitement terminé pour {len(valid_pdfs)} fichier(s).")


if __name__ == "__main__":
    main()
