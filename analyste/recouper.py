"""Étape bonus : recoupe les chiffres lus avec les données officielles ESEF.
Depuis 2021, les sociétés cotées européennes déposent leurs comptes au format ESEF : chaque chiffre y est étiqueté
avec un concept IFRS (« Revenue », « Equity »…). filings.xbrl.org les republie en JSON. On compare, poste par poste,
ce qui a été lu dans le PDF avec ce que la société a elle-même déclaré. Aucune IA dans cette étape."""
import datetime, json, sys, urllib.parse, urllib.request
import yaml

API = "https://filings.xbrl.org"

# Postes qui ont un équivalent IFRS sans ambiguïté (signe ignoré : un décaissement est négatif dans le rapport)
CONCEPTS = {
    "ventes": "ifrs-full:Revenue",
    "marge_brute": "ifrs-full:GrossProfit",
    "resultat_operationnel": "ifrs-full:ProfitLossFromOperatingActivities",
    "resultat_net_part_du_groupe": "ifrs-full:ProfitLossAttributableToOwnersOfParent",
    "bpa_dilue": "ifrs-full:DilutedEarningsLossPerShare",
    "capitaux_propres": "ifrs-full:Equity",
    "interets_minoritaires": "ifrs-full:NoncontrollingInterests",
    "tresorerie": "ifrs-full:CashAndCashEquivalents",
    "dettes_locatives_long_terme": "ifrs-full:NoncurrentLeaseLiabilities",
    "dettes_locatives_court_terme": "ifrs-full:CurrentLeaseLiabilities",
    "flux_exploitation": "ifrs-full:CashFlowsFromUsedInOperatingActivities",
    "remboursements_dettes_locatives": "ifrs-full:PaymentsOfLeaseLiabilitiesClassifiedAsFinancingActivities",
}


def lire_json(url):
    requete = urllib.request.Request(url, headers={"User-Agent": "analyste-ia (projet pedagogique)"})
    with urllib.request.urlopen(requete, timeout=60) as r:
        return json.load(r)


def depots(lei, n=2):
    filtre = json.dumps([{"name": "entity.identifier", "op": "eq", "val": lei}])
    url = f"{API}/api/filings?filter={urllib.parse.quote(filtre)}&sort=-period_end&page%5Bsize%5D={n}"
    return [f["attributes"] for f in lire_json(url)["data"] if f["attributes"].get("json_url")]


def annee(periode):
    """'2024-01-01/2025-01-01' (exercice) ou '2025-01-01' (date de clôture, au matin du lendemain) -> '2024'."""
    fin = periode.split("/")[-1][:10]
    return str((datetime.date.fromisoformat(fin) - datetime.timedelta(days=1)).year)


def faits_officiels(lei):
    """{(concept, année): valeur} sans dimension (chiffres consolidés du groupe), le dépôt le plus récent d'abord."""
    faits, sources = {}, []
    for depot in depots(lei):
        sources.append(API + depot["json_url"])
        for f in lire_json(API + depot["json_url"])["facts"].values():
            d = f["dimensions"]
            if d.get("concept") in CONCEPTS.values() and not set(d) - {"concept", "entity", "period", "unit", "language"}:
                cle = (d["concept"], annee(d["period"]))
                if cle not in faits:
                    faits[cle] = float(f["value"])
    return faits, sources


def recouper(chiffres, faits):
    lignes = []
    for poste, concept in CONCEPTS.items():
        for an, item in sorted(chiffres["postes"].get(poste, {}).items()):
            if (concept, an) not in faits:
                continue
            officiel = faits[(concept, an)] / (1 if poste == "bpa_dilue" else 1e6)   # le rapport est en millions
            ok = abs(abs(item["valeur"]) - abs(officiel)) <= 0.51
            lignes.append({"poste": poste, "annee": an, "lu_dans_le_rapport": item["valeur"], "page": item["page"],
                           "depot_officiel": round(officiel, 2), "concorde": ok})
    return lignes


if __name__ == "__main__":
    dossier, fichier_hyp = sys.argv[1], sys.argv[2]
    h = yaml.safe_load(open(fichier_hyp))
    if not h.get("lei"):
        sys.exit("Pas de LEI dans les hypothèses : recoupement ESEF ignoré.")
    chiffres = json.load(open(f"{dossier}/chiffres.json"))
    faits, sources = faits_officiels(h["lei"])
    lignes = recouper(chiffres, faits)
    ecarts = [l for l in lignes if not l["concorde"]]
    json.dump({"lei": h["lei"], "sources": sources, "comparaisons": lignes,
               "nb_compares": len(lignes), "nb_concordants": len(lignes) - len(ecarts)},
              open(f"{dossier}/recoupement.json", "w"), ensure_ascii=False, indent=1)
    print(f"{len(lignes)} chiffres comparés au dépôt officiel ESEF, {len(lignes) - len(ecarts)} concordent")
    for l in ecarts:
        print(f"  écart : {l['poste']} {l['annee']} lu {l['lu_dans_le_rapport']} (p. {l['page']}), officiel {l['depot_officiel']}")
