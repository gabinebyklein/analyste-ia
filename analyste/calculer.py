"""Étape 3 : tous les calculs, en Python, à partir des chiffres vérifiés.
Ratios historiques, DCF, comparables boursiers, sensibilité, fourchettes de valeur."""
import json, statistics, sys

ANNEES = []   # années présentes dans le rapport, fixées par annees_disponibles()


def serie(chiffres, poste):
    s = {a: chiffres["postes"][poste][a]["valeur"] for a in chiffres["postes"].get(poste, {})}
    if poste in FACULTATIFS and not s:
        return {a: 0.0 for a in ANNEES}       # poste absent du rapport (inclus dans une autre ligne) : compté pour 0
    return s


def marche(tickers):
    import yfinance as yf                     # importé ici : le reste du fichier tourne aussi dans le navigateur
    champs = ["shortName", "currency", "currentPrice", "enterpriseToEbitda", "trailingPE",
              "beta", "sharesOutstanding", "dividendYield", "fiftyTwoWeekLow", "fiftyTwoWeekHigh"]
    return {t: {k: yf.Ticker(t).info.get(k) for k in champs} for t in tickers}


def ratios(c):
    v = serie(c, "ventes")
    roc, rn = serie(c, "resultat_operationnel_courant"), serie(c, "resultat_net_part_du_groupe")
    dot, rou = serie(c, "dotations_amortissements"), serie(c, "amortissement_droits_utilisation")
    capex, bfr = serie(c, "investissements_operationnels"), serie(c, "variation_bfr")
    loyers = {a: serie(c, "remboursements_dettes_locatives")[a] + serie(c, "interets_locatifs_payes")[a] for a in ANNEES}
    cp, mino = serie(c, "capitaux_propres"), serie(c, "interets_minoritaires")
    dette_fin = {a: serie(c, "dette_financiere_long_terme")[a] + serie(c, "dette_financiere_court_terme")[a]
                 - serie(c, "tresorerie")[a] for a in ANNEES}
    dettes_loc = {a: serie(c, "dettes_locatives_long_terme")[a] + serie(c, "dettes_locatives_court_terme")[a] for a in ANNEES}
    ebitda = {a: roc[a] + dot[a] + rou[a] for a in ANNEES}
    # cash-flow disponible d'exploitation, définition LVMH : flux d'exploitation - capex - remboursements locatifs
    fcf = {a: serie(c, "flux_exploitation")[a] + capex[a] + serie(c, "remboursements_dettes_locatives")[a] for a in ANNEES}
    r = {}
    for a in ANNEES:
        r[a] = {
            "ventes": v[a],
            "croissance_ventes_pct": (v[a] / v[str(int(a) - 1)] - 1) * 100 if str(int(a) - 1) in v else None,
            "marge_brute_pct": serie(c, "marge_brute")[a] / v[a] * 100 if a in c["postes"].get("marge_brute", {}) else None,
            "marge_roc_pct": roc[a] / v[a] * 100,
            "marge_nette_pct": rn[a] / v[a] * 100,
            "ebitda": ebitda[a],
            "amortissements_pct": (dot[a] + rou[a]) / v[a] * 100,
            "capex_pct": -capex[a] / v[a] * 100,
            "loyers_pct": -loyers[a] / v[a] * 100,
            "fcf_exploitation": fcf[a],
            "rentabilite_capitaux_propres_pct": rn[a] / (cp[a] - mino[a]) * 100,
            "dette_financiere_nette": dette_fin[a],
            "dettes_locatives": dettes_loc[a],
            "levier_dette_nette_sur_ebitda": (dette_fin[a] + dettes_loc[a]) / ebitda[a],
            "dividendes_verses": -serie(c, "dividendes_verses")[a],
        }
    return r


def wacc(h, poids_dette):
    w = h["wacc"]
    ke = w["taux_sans_risque_pct"] + w["beta"] * w["prime_risque_marche_pct"]
    kd = (w["taux_sans_risque_pct"] + w["spread_dette_pct"]) * (1 - h["projection"]["taux_impot_pct"] / 100)
    return (1 - poids_dette) * ke + poids_dette * kd, ke, kd


def projeter(h, base):
    p, t = h["projection"], h["projection"]["taux_impot_pct"] / 100
    ventes, lignes = base["ventes"], []
    for i, g in enumerate(p["croissance_ventes_pct"]):
        nouvelles = ventes * (1 + g / 100)
        roc = nouvelles * p["marge_roc_pct"][i] / 100
        fcf = (roc * (1 - t)
               + nouvelles * base["amortissements_pct"] / 100
               - nouvelles * p["capex_pct_ventes"] / 100
               - nouvelles * base["loyers_pct"] / 100
               - (nouvelles - ventes) * p["bfr_pct_ventes_supplementaires"] / 100)
        lignes.append({"annee": int(h["annee_de_base"]) + 1 + i, "ventes": nouvelles, "roc": roc, "fcf": fcf})
        ventes = nouvelles
    return lignes


def dcf(lignes, taux, g):
    """Valeur d'entreprise = flux actualisés + valeur terminale de Gordon actualisée."""
    taux, g = taux / 100, g / 100
    actualises = sum(l["fcf"] / (1 + taux) ** (i + 1) for i, l in enumerate(lignes))
    terminale = lignes[-1]["fcf"] * (1 + g) / (taux - g)
    return actualises + terminale / (1 + taux) ** len(lignes), terminale / (1 + taux) ** len(lignes)


def par_action(ve, base, nb_actions_m, mino):
    # les loyers sont déjà déduits des flux : on ne retire que la dette FINANCIÈRE nette
    return (ve - base["dette_financiere_nette"] - mino) / nb_actions_m


# Postes qui n'existent pas dans tous les rapports, comptés pour 0 s'ils manquent :
# - marge brute (pas de ligne chez Danone) ;
# - amortissement des droits d'utilisation, intérêts locatifs : parfois inclus dans les dotations ou les frais financiers ;
# - dettes locatives et leurs remboursements : quand le rapport les inclut dans la dette financière (Danone), les loyers
#   ne sont pas déduits des flux et la dette locative est retirée avec la dette financière. Le traitement reste cohérent ;
# - intérêts minoritaires, dividendes.
FACULTATIFS = ["marge_brute", "amortissement_droits_utilisation", "interets_locatifs_payes", "interets_minoritaires",
               "dettes_locatives_long_terme", "dettes_locatives_court_terme", "remboursements_dettes_locatives",
               "dividendes_verses"]

NECESSAIRES = ["ventes", "marge_brute", "resultat_operationnel_courant", "resultat_net_part_du_groupe", "bpa_dilue",
               "capitaux_propres", "interets_minoritaires", "dette_financiere_long_terme", "dette_financiere_court_terme",
               "tresorerie", "dettes_locatives_long_terme", "dettes_locatives_court_terme", "dotations_amortissements",
               "amortissement_droits_utilisation", "variation_bfr", "flux_exploitation", "investissements_operationnels",
               "remboursements_dettes_locatives", "interets_locatifs_payes", "dividendes_verses"]


def evaluer(h, base, nb_actions_m, mino, cours, poids_dette):
    """Le DCF complet à partir des hypothèses : WACC, projection, valeur par action, sensibilité, DCF inversé.
    C'est cette fonction que la page web appelle quand on bouge un curseur."""
    w, ke, kd = wacc(h, poids_dette)
    g = h["valeur_terminale"]["croissance_perpetuelle_pct"]
    lignes = projeter(h, base)
    ve, part_terminale = dcf(lignes, w, g)
    sensibilite = {f"{wi:.1f}": {f"{gi:.1f}": par_action(dcf(lignes, wi, gi)[0], base, nb_actions_m, mino)
                                 for gi in (g - 0.5, g, g + 0.5)}
                   for wi in (w - 1, w - 0.5, w, w + 0.5, w + 1)}
    # DCF inversé : quelle croissance perpétuelle le cours actuel suppose-t-il ?
    bas, haut = -5.0, w - 0.1
    for _ in range(60):
        milieu = (bas + haut) / 2
        if par_action(dcf(lignes, w, milieu)[0], base, nb_actions_m, mino) > cours:
            haut = milieu
        else:
            bas = milieu
    return {"wacc_pct": w, "cout_fonds_propres_pct": ke, "cout_dette_apres_impot_pct": kd,
            "croissance_perpetuelle_pct": g, "projection": lignes, "sensibilite": sensibilite,
            "valeur_entreprise": ve, "part_valeur_terminale_pct": part_terminale / ve * 100,
            "prix_par_action": par_action(ve, base, nb_actions_m, mino),
            "croissance_implicite_dans_le_cours_pct": (bas + haut) / 2}


def annees_disponibles(c):
    """Les années présentes pour les ventes et le résultat (2 ou 3 selon les rapports)."""
    return sorted(set(c["postes"].get("ventes", {})) & set(c["postes"].get("resultat_operationnel_courant", {})))


def main(dossier, fichier_hyp):
    import yaml
    c = json.load(open(f"{dossier}/chiffres.json"))
    h = yaml.safe_load(open(fichier_hyp))
    ANNEES[:] = annees_disponibles(c)
    manquants = [f"{p} {a}" for p in NECESSAIRES if p not in FACULTATIFS or c["postes"].get(p)
                 for a in ANNEES if a not in c["postes"].get(p, {})]
    if manquants or h["annee_de_base"] not in ANNEES:
        sys.exit("Calcul impossible, chiffres non vérifiés dans le rapport : " + ", ".join(manquants or [h["annee_de_base"]])
                 + ". Relancer la lecture ou compléter chiffres.json à la main, page à l'appui.")
    r = ratios(c)
    base = r[h["annee_de_base"]]
    mino = serie(c, "interets_minoritaires")[h["annee_de_base"]]

    m = marche([h["ticker"]] + h["comparables"])
    soc = m[h["ticker"]]
    nb_actions_m = soc["sharesOutstanding"] / 1e6
    capi = soc["currentPrice"] * nb_actions_m
    # trésorerie supérieure à la dette (Hermès) : pas de dette dans le WACC, la trésorerie s'ajoute à la valeur
    poids_dette = max(0.0, base["dette_financiere_nette"]) / (max(0.0, base["dette_financiere_nette"]) + capi)

    e = evaluer(h, base, nb_actions_m, mino, soc["currentPrice"], poids_dette)
    w, ke, kd, g, lignes, sensibilite = e["wacc_pct"], e["cout_fonds_propres_pct"], e["cout_dette_apres_impot_pct"], \
        e["croissance_perpetuelle_pct"], e["projection"], e["sensibilite"]

    # comparables : on écarte les valeurs aberrantes de Yahoo (bénéfice quasi nul -> multiple absurde)
    ve_ebitda = [m[t]["enterpriseToEbitda"] for t in h["comparables"] if m[t]["enterpriseToEbitda"] and 0 < m[t]["enterpriseToEbitda"] < 40]
    per = [m[t]["trailingPE"] for t in h["comparables"] if m[t]["trailingPE"] and 0 < m[t]["trailingPE"] < 60]
    q = lambda xs: statistics.quantiles(xs, n=4)  # [Q1, médiane, Q3]
    dette_totale = base["dette_financiere_nette"] + base["dettes_locatives"]  # EBITDA IFRS 16 -> on retire aussi les loyers
    prix_ebitda = [(x * base["ebitda"] - dette_totale - mino) / nb_actions_m for x in q(ve_ebitda)]
    bpa = serie(c, "bpa_dilue")[h["annee_de_base"]]
    prix_per = [x * bpa for x in q(per)]

    toutes = [v for ligne in sensibilite.values() for v in ligne.values()]
    resultat = {
        "societe": h["societe"], "ticker": h["ticker"], "annee_de_base": h["annee_de_base"],
        "historique": r, "marche": m,
        "cours": soc["currentPrice"], "capitalisation": capi, "nb_actions_m": nb_actions_m,
        "hypotheses": h, "interets_minoritaires": mino, "poids_dette": poids_dette,
        "wacc": {"wacc_pct": w, "beta_retenu": h["wacc"]["beta"], "cout_fonds_propres_pct": ke, "cout_dette_apres_impot_pct": kd, "poids_dette_pct": poids_dette * 100},
        "projection": lignes,
        "dcf": {k: e[k] for k in ("valeur_entreprise", "part_valeur_terminale_pct", "prix_par_action",
                                  "croissance_perpetuelle_pct", "croissance_implicite_dans_le_cours_pct")},
        "sensibilite": sensibilite,
        "comparables": {"ve_ebitda_q1_med_q3": q(ve_ebitda), "per_q1_med_q3": q(per),
                        "prix_ve_ebitda": prix_ebitda, "prix_per": prix_per,
                        "retenus_ve_ebitda": len(ve_ebitda), "retenus_per": len(per)},
        "fourchettes": {
            "DCF (WACC ± 1 pt, g ± 0,5 pt)": [min(toutes), max(toutes)],
            "VE/EBITDA des pairs": [prix_ebitda[0], prix_ebitda[2]],
            "PER des pairs": [prix_per[0], prix_per[2]],
            "Cours sur 52 semaines": [soc["fiftyTwoWeekLow"], soc["fiftyTwoWeekHigh"]],
        },
    }
    json.dump(resultat, open(f"{dossier}/valorisation.json", "w"), ensure_ascii=False, indent=1)
    return resultat


if __name__ == "__main__":
    res = main(sys.argv[1], sys.argv[2])
    print(f"Cours {res['cours']:.2f} € | WACC {res['wacc']['wacc_pct']:.2f} % | DCF {res['dcf']['prix_par_action']:.0f} € "
          f"(terminale {res['dcf']['part_valeur_terminale_pct']:.0f} % de la VE) | g implicite {res['dcf']['croissance_implicite_dans_le_cours_pct']:.2f} %")
    for nom, (a, b) in res["fourchettes"].items():
        print(f"  {nom:45} {a:7.0f} – {b:7.0f} €")
