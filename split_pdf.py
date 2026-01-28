#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour decouper un PDF en blocs de pages.
Utile pour traiter des PDF tres volumineux par morceaux.
"""

import sys
from pathlib import Path

try:
    from pypdf import PdfReader, PdfWriter
    PYPDF_AVAILABLE = True
except ImportError:
    try:
        from PyPDF2 import PdfFileReader, PdfFileWriter
        PYPDF2_AVAILABLE = True
        PYPDF_AVAILABLE = False
    except ImportError:
        PYPDF2_AVAILABLE = False
        PYPDF_AVAILABLE = False


def split_pdf(input_path, pages_per_chunk=20, output_dir=None):
    """
    Decoupe un PDF en plusieurs fichiers de pages_per_chunk pages.
    
    Args:
        input_path: Chemin vers le PDF a decouper
        pages_per_chunk: Nombre de pages par bloc (defaut: 20)
        output_dir: Repertoire de sortie (defaut: meme repertoire que le PDF)
    
    Returns:
        Liste des chemins des fichiers crees
    """
    input_path = Path(input_path)
    
    if not input_path.exists():
        print(f"Erreur: Le fichier '{input_path}' n'existe pas.")
        return []
    
    if not input_path.suffix.lower() == '.pdf':
        print(f"Erreur: Le fichier doit etre un PDF (.pdf)")
        return []
    
    # Determiner le repertoire de sortie
    if output_dir is None:
        output_dir = input_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # Creer un sous-dossier pour les chunks
    chunks_dir = output_dir / f"{input_path.stem}_chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Ouverture du PDF: {input_path.name}")
    
    # Lire le PDF
    try:
        if PYPDF_AVAILABLE:
            reader = PdfReader(str(input_path))
            total_pages = len(reader.pages)
        elif PYPDF2_AVAILABLE:
            reader = PdfFileReader(str(input_path))
            total_pages = reader.getNumPages()
        else:
            print("Erreur: Aucune bibliotheque PDF disponible.")
            print("   Installez pypdf: pip install pypdf")
            return []
    except Exception as e:
        print(f"Erreur lors de la lecture du PDF: {e}")
        return []
    
    print(f"   Total de pages: {total_pages}")
    print(f"   Taille des blocs: {pages_per_chunk} pages")
    
    # Calculer le nombre de blocs
    num_chunks = (total_pages + pages_per_chunk - 1) // pages_per_chunk  # Arrondi superieur
    print(f"   Nombre de blocs a creer: {num_chunks}\n")
    
    created_files = []
    
    # Decouper le PDF
    for chunk_num in range(num_chunks):
        start_page = chunk_num * pages_per_chunk
        end_page = min(start_page + pages_per_chunk, total_pages)
        
        # Creer un nouveau PDF pour ce bloc
        if PYPDF_AVAILABLE:
            writer = PdfWriter()
            for page_num in range(start_page, end_page):
                writer.add_page(reader.pages[page_num])
        elif PYPDF2_AVAILABLE:
            writer = PdfFileWriter()
            for page_num in range(start_page, end_page):
                writer.addPage(reader.getPage(page_num))
        
        # Nom du fichier de sortie
        output_filename = f"{input_path.stem}_chunk_{chunk_num + 1:03d}_pages_{start_page + 1}-{end_page}.pdf"
        output_path = chunks_dir / output_filename
        
        # Sauvegarder le bloc
        try:
            with open(output_path, 'wb') as output_file:
                if PYPDF_AVAILABLE:
                    writer.write(output_file)
                elif PYPDF2_AVAILABLE:
                    writer.write(output_file)
            
            created_files.append(output_path)
            print(f"Bloc {chunk_num + 1}/{num_chunks}: pages {start_page + 1}-{end_page} -> {output_filename}")
        except Exception as e:
            print(f"Erreur lors de la creation du bloc {chunk_num + 1}: {e}")
    
    print(f"\nDecoupage termine: {len(created_files)} fichier(s) cree(s) dans {chunks_dir}")
    return created_files


def main():
    if len(sys.argv) < 2:
        print("Usage: python split_pdf.py <chemin_vers_pdf> [pages_par_bloc] [repertoire_sortie]")
        print("Exemple: python split_pdf.py article.pdf")
        print("Exemple: python split_pdf.py article.pdf 20")
        print("Exemple: python split_pdf.py article.pdf 20 ./output")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    
    # Nombre de pages par bloc (defaut: 20)
    pages_per_chunk = 20
    if len(sys.argv) >= 3:
        try:
            pages_per_chunk = int(sys.argv[2])
            if pages_per_chunk < 1:
                print("Le nombre de pages par bloc doit etre >= 1. Utilisation de 20 par defaut.")
                pages_per_chunk = 20
        except ValueError:
            print("Nombre de pages invalide. Utilisation de 20 par defaut.")
    
    # Repertoire de sortie (optionnel)
    output_dir = None
    if len(sys.argv) >= 4:
        output_dir = Path(sys.argv[4])
    
    split_pdf(input_path, pages_per_chunk, output_dir)


if __name__ == "__main__":
    main()
