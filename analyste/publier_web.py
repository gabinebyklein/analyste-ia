"""Prépare les données de la page web (index.html) à partir des dossiers rapports/*.
Aucun calcul ici : on regroupe ce que les étapes précédentes ont produit."""
import json, pathlib

RACINE = pathlib.Path(__file__).resolve().parent.parent
SORTIE = RACINE / "web" / "donnees"


def paquet(dossier):
    c = json.load(open(dossier / "chiffres.json"))
    v = json.load(open(dossier / "valorisation.json"))
    a = json.load(open(dossier / "analyse.json"))
    r = json.load(open(dossier / "recoupement.json")) if (dossier / "recoupement.json").exists() else None
    m = v["marche"][v["ticker"]]
    base = v["annee_de_base"]
    pages = {poste: annees[base]["page"] for poste, annees in c["postes"].items() if base in annees}
    return {
        "id": dossier.name, "societe": v["societe"], "ticker": v["ticker"], "annee_de_base": base,
        "cours": v["cours"], "capitalisation": v["capitalisation"], "nb_actions_m": v["nb_actions_m"],
        "dividende_pct": m["dividendYield"], "plus_bas_52s": m["fiftyTwoWeekLow"], "plus_haut_52s": m["fiftyTwoWeekHigh"],
        "hypotheses": v["hypotheses"], "interets_minoritaires": v["interets_minoritaires"], "poids_dette": v["poids_dette"],
        "historique": v["historique"], "base": v["historique"][base], "pages": pages,
        "pages_etats": c["pages_etats"], "nb_verifies": sum(len(x) for x in c["postes"].values()), "nb_rejetes": len(c["rejetes"]),
        "dcf": v["dcf"], "wacc": v["wacc"], "comparables": v["comparables"], "fourchettes": v["fourchettes"],
        "analyse": {k: a[k] for k in ("en_une_phrase", "points_forts", "points_de_vigilance",
                                      "lecture_de_la_valorisation", "pour_un_gestionnaire_de_patrimoine")},
        "recoupement": r and {"nb_compares": r["nb_compares"], "nb_concordants": r["nb_concordants"],
                              "comparaisons": r["comparaisons"], "sources": r["sources"]},
        "fiche_pdf": next((str(p.relative_to(RACINE)) for p in dossier.glob("fiche-*.pdf")), None),
    }


if __name__ == "__main__":
    SORTIE.mkdir(parents=True, exist_ok=True)
    liste = []
    for dossier in sorted((RACINE / "rapports").iterdir()):
        if (dossier / "analyse.json").exists():
            p = paquet(dossier)
            json.dump(p, open(SORTIE / f"{p['id']}.json", "w"), ensure_ascii=False)
            liste.append({"id": p["id"], "societe": p["societe"], "capitalisation": p["capitalisation"]})
    liste.sort(key=lambda x: -x["capitalisation"])          # la plus grosse capitalisation d'abord
    json.dump(liste, open(SORTIE / "index.json", "w"), ensure_ascii=False)
    print(", ".join(x["societe"] for x in liste))
