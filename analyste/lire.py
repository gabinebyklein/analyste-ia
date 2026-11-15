"""Étape 2 : Claude lit les états financiers et rend chaque chiffre AVEC sa page.
Puis Python vérifie que chaque chiffre figure bien dans la page citée.
Un chiffre introuvable est rejeté : l'IA ne peut pas inventer."""
import json, re, sys, unicodedata
import ia

# Les trois états financiers, repérés par leur titre en haut de page
TITRES = {
    "compte_de_resultat": "COMPTE DE RÉSULTAT CONSOLIDÉ",
    "bilan": "BILAN CONSOLIDÉ",
    "flux": "TABLEAU DE VARIATION DE LA TRÉSORERIE CONSOLIDÉE",
}

# Ce que l'on demande à Claude, poste par poste
POSTES = {
    "ventes": "Ventes / chiffre d'affaires",
    "marge_brute": "Marge brute",
    "resultat_operationnel_courant": "Résultat opérationnel courant",
    "resultat_net_part_du_groupe": "Résultat net, part du Groupe",
    "bpa_dilue": "Résultat net part du Groupe par action après dilution (en euros)",
    "capitaux_propres": "Capitaux propres totaux (y compris intérêts minoritaires)",
    "interets_minoritaires": "Intérêts minoritaires (au bilan)",
    "dette_financiere_long_terme": "Dette financière à plus d'un an",
    "dette_financiere_court_terme": "Dette financière à moins d'un an",
    "tresorerie": "Trésorerie et équivalents de trésorerie (actif du bilan)",
    "dettes_locatives_long_terme": "Dettes locatives à plus d'un an (passif du bilan)",
    "dettes_locatives_court_terme": "Dettes locatives à moins d'un an (passif du bilan)",
    "resultat_operationnel": "Résultat opérationnel (après autres produits et charges)",
    "dotations_amortissements": "Dotations nettes aux amortissements et provisions (tableau de flux)",
    "amortissement_droits_utilisation": "Amortissement des droits d'utilisation (tableau de flux)",
    "impot_paye": "Impôt payé (opérations d'exploitation)",
    "variation_bfr": "Variation du besoin en fonds de roulement",
    "flux_exploitation": "Variation de la trésorerie issue des opérations d'exploitation",
    "investissements_operationnels": "Investissements d'exploitation (capex)",
    "remboursements_dettes_locatives": "Remboursements des dettes locatives",
    "interets_locatifs_payes": "Dettes locatives : intérêts payés",
    "dividendes_verses": "Dividendes et acomptes versés (total, opérations de financement)",
}


def normaliser(texte):
    """Enlève espaces fins, insécables et séparateurs pour comparer des nombres."""
    texte = unicodedata.normalize("NFKC", texte)
    return re.sub(r"[\s  ]", "", texte)


def pages_des_etats(pages):
    """Page dont une ligne est exactement le titre de l'état (espaces insécables neutralisés)."""
    def lignes(texte):
        return {re.sub(r"\s+", " ", unicodedata.normalize("NFKC", l)).strip() for l in texte.splitlines()}
    trouve = {}
    for cle, titre in TITRES.items():
        for p in pages:
            if titre in lignes(p["texte"]):
                trouve[cle] = p["page"]
                break
    return trouve


def demander_a_claude(extraits):
    consigne = (
        "Tu es analyste financier. Voici les états financiers consolidés d'une entreprise, "
        "chaque page précédée de [PAGE n].\n"
        "Pour chaque poste demandé et pour CHAQUE année présente, recopie le chiffre EXACTEMENT "
        "comme il est écrit dans la page (mêmes chiffres, signe entre parenthèses conservé), "
        "et donne le numéro de [PAGE] d'où il vient. Si un poste n'existe pas, ne le mets pas. "
        "N'invente rien, ne calcule rien.\n\n"
        "Postes : " + json.dumps(POSTES, ensure_ascii=False) + "\n\n" + extraits
    )
    schema = {
        "type": "object",
        "properties": {
            "unite": {"type": "string"},
            "valeurs": {"type": "array", "items": {
                "type": "object",
                "properties": {
                    "poste": {"type": "string", "enum": list(POSTES)},
                    "annee": {"type": "string"},
                    "valeur": {"type": "string"},
                    "page": {"type": "integer"},
                },
                "required": ["poste", "annee", "valeur", "page"],
                "additionalProperties": False,
            }},
        },
        "required": ["unite", "valeurs"],
        "additionalProperties": False,
    }
    reponse = ia.demander(consigne, schema)
    postes = {}
    for v in reponse["valeurs"]:
        # plusieurs candidats possibles pour un même chiffre : on les garde tous, la vérification tranche
        postes.setdefault(v["poste"], {}).setdefault(v["annee"], []).append({"valeur": v["valeur"], "page": v["page"]})
    return {"unite": reponse["unite"], "postes": postes}


def en_nombre(valeur):
    """'(1 065)' -> -1065.0 ; '84 683' -> 84683.0 ; '17,55' -> 17.55"""
    v = normaliser(valeur)
    negatif = v.startswith("(") and v.endswith(")") or v.startswith("-")
    v = v.strip("()-").replace(",", ".")
    return -float(v) if negatif else float(v)


def verifier(lecture, pages_par_numero):
    """Garde un chiffre seulement s'il est écrit tel quel dans la page citée.
    Si deux candidats vérifiés se contredisent, le chiffre est écarté : on ne choisit pas au hasard."""
    verifie, rejete = {}, []
    for poste, annees in lecture["postes"].items():
        for annee, candidats in (annees or {}).items():
            bons = set()
            for item in candidats:
                # chaque cellule d'un tableau est une ligne du texte : le chiffre doit être une cellule entière
                cellules = {normaliser(l).strip("()-") for l in pages_par_numero.get(item["page"], "").splitlines()}
                brut = normaliser(item["valeur"] or "").strip("()-")
                if brut and brut in cellules:
                    bons.add((en_nombre(item["valeur"]), item["page"]))
                else:
                    rejete.append(f"{poste} {annee} = {item['valeur']} (page {item['page']})")
            if len({v for v, _ in bons}) == 1:
                valeur, page = min(bons, key=lambda b: b[1])
                verifie.setdefault(poste, {})[annee] = {"valeur": valeur, "page": page}
            elif bons:
                rejete.append(f"{poste} {annee} : valeurs contradictoires {sorted(v for v, _ in bons)}")
    return verifie, rejete


if __name__ == "__main__":
    fichier_pages, sortie = sys.argv[1], sys.argv[2]
    pages = [json.loads(l) for l in open(fichier_pages)]
    par_numero = {p["page"]: p["texte"] for p in pages}

    etats = pages_des_etats(pages)
    print("États trouvés :", etats)
    extraits = "\n\n".join(f"[PAGE {n}]\n{par_numero[n]}" for n in sorted(etats.values()))

    lecture = demander_a_claude(extraits)
    verifie, rejete = verifier(lecture, par_numero)

    json.dump({"unite": lecture.get("unite"), "pages_etats": etats, "postes": verifie, "rejetes": rejete},
              open(sortie, "w"), ensure_ascii=False, indent=1)
    n = sum(len(v) for v in verifie.values())
    print(f"{n} chiffres vérifiés, {len(rejete)} rejetés | coût de l'appel à l'IA : {ia.cout():.3f} $")
    for r in rejete:
        print("  rejeté :", r)
