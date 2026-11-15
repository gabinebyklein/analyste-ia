"""Lance toute la chaîne sur un rapport : python -m analyste <dossier> <hypotheses.yaml>
Le dossier doit contenir deu.pdf (le rapport annuel)."""
import pathlib, subprocess, sys

dossier, hypotheses = pathlib.Path(sys.argv[1]), sys.argv[2]
py = [sys.executable]   # pas de -I : les étapes importent le module ia.py voisin
etapes = [
    ("Extraction du texte", py + ["analyste/extraire.py", str(next(p for p in dossier.glob("*.pdf") if not p.name.startswith("fiche"))), str(dossier / "pages.jsonl")]),
    ("Lecture par Claude + vérification", py + ["analyste/lire.py", str(dossier / "pages.jsonl"), str(dossier / "chiffres.json")]),
    ("Calculs et valorisation", py + ["analyste/calculer.py", str(dossier), hypotheses]),
    ("Rédaction + contrôle des chiffres", py + ["analyste/rediger.py", str(dossier)]),
    ("Fiche PDF", py + ["analyste/fiche.py", str(dossier)]),
]
for nom, cmd in etapes:
    print(f"→ {nom}")
    subprocess.run(cmd, check=True)
