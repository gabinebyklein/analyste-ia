"""Étape 1 : transforme le PDF en texte, page par page (numéro de page du PDF conservé pour citer)."""
import json, sys, pymupdf

def extraire(pdf, sortie):
    doc = pymupdf.open(pdf)
    with open(sortie, "w") as f:
        for i, page in enumerate(doc, start=1):
            f.write(json.dumps({"page": i, "texte": page.get_text()}, ensure_ascii=False) + "\n")
    return doc.page_count

if __name__ == "__main__":
    print(extraire(sys.argv[1], sys.argv[2]), "pages extraites")
