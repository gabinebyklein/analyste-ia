"""Étape 4 : Claude rédige l'analyse à partir des SEULS chiffres calculés.
Python contrôle ensuite que chaque nombre du texte existe dans les données."""
import json, re, sys
import ia

CONSIGNE = """Tu es analyste actions. Rédige en français la fiche d'analyse de {societe} à partir
UNIQUEMENT des données JSON ci-dessous (montants en millions d'euros sauf mention ; *_pct en %).

Règles strictes :
- Chaque phrase s'appuie sur un chiffre des données. N'utilise AUCUN chiffre absent des données.
- Arrondis au plus simple (ex. 80 807 M€ -> 80,8 Md€ ; 22,04 % -> 22,0 %). Pas de calcul nouveau.
- Interdit : « acheter », « vendre », « conserver », « objectif de cours », « recommandation »,
  ou toute formulation qui dit quoi faire de l'action. Tu décris, tu ne conseilles pas.
- Style sobre de note de banque, phrases courtes, pas de superlatifs.

Contenu attendu : une phrase de synthèse ; 3 points forts ; 3 points de vigilance ;
la lecture de la valorisation en 3 phrases (DCF, comparables, ce que le cours suppose) ;
2 phrases pour un gestionnaire de patrimoine (dividende, endettement, volatilité via le beta), sans conseil.

Données :
{donnees}"""


phrases = lambda: {"type": "array", "items": {"type": "string"}}
SCHEMA = {
    "type": "object",
    "properties": {
        "en_une_phrase": {"type": "string"},
        "points_forts": phrases(),
        "points_de_vigilance": phrases(),
        "lecture_de_la_valorisation": {"type": "string"},
        "pour_un_gestionnaire_de_patrimoine": {"type": "string"},
    },
    "required": ["en_une_phrase", "points_forts", "points_de_vigilance",
                 "lecture_de_la_valorisation", "pour_un_gestionnaire_de_patrimoine"],
    "additionalProperties": False,
}


def nombres(texte):
    """Tous les nombres d'un texte, en float ('80,8' -> 80.8 ; '7 123' -> 7123)."""
    brut = re.findall(r"\d+(?:[\s  ]\d{3})*(?:,\d+)?", texte)
    return [float(re.sub(r"[\s  ]", "", n).replace(",", ".")) for n in brut]


def valeurs_sources(objet, acc=None):
    acc = [] if acc is None else acc
    if isinstance(objet, dict):
        for k, v in objet.items():
            if isinstance(k, str) and k.isdigit():
                acc.append(float(k))
            valeurs_sources(v, acc)
    elif isinstance(objet, list):
        for v in objet:
            valeurs_sources(v, acc)
    elif isinstance(objet, (int, float)) and not isinstance(objet, bool):
        acc.append(float(objet))
    return acc


def controler(texte, sources):
    """Un nombre du texte est accepté s'il correspond (arrondi près, en M€ ou Md€) à une valeur source."""
    suspects = []
    texte = re.sub(r"52 semaines|\b(19|20)\d{2}\b", "", texte)   # expressions et années, pas des données
    for n in nombres(texte):
        if n <= 10 and n == int(n):          # « 3 phrases », « 5 ans », petits entiers de rédaction
            continue
        ok = any(abs(abs(s) * f - n) <= max(0.051, 0.006 * n) for s in sources for f in (1, 0.001))
        if not ok:
            suspects.append(n)
    return suspects


def donnees_pour_claude(v):
    """On ne transmet que l'utile, déjà arrondi."""
    m = v["marche"][v["ticker"]]
    arr = lambda x: round(x, 1) if isinstance(x, float) else x
    return {
        "historique": {a: {k: arr(x) for k, x in r.items()} for a, r in v["historique"].items()},
        "cours_eur": v["cours"], "capitalisation_m_eur": round(v["capitalisation"]),
        "rendement_dividende_pct": m["dividendYield"], "beta": m["beta"],
        "cours_52_semaines": [m["fiftyTwoWeekLow"], m["fiftyTwoWeekHigh"]],
        "wacc": {k: arr(x) for k, x in v["wacc"].items()},
        "dcf": {k: arr(x) for k, x in v["dcf"].items() if k != "valeur_entreprise"},
        "comparables": {k: [arr(x) for x in xs] if isinstance(xs, list) else xs for k, xs in v["comparables"].items()},
        "fourchettes_prix_par_action": {k: [round(a), round(b)] for k, (a, b) in v["fourchettes"].items()},
    }


def rediger(v):
    donnees = donnees_pour_claude(v)
    consigne = CONSIGNE.format(societe=v["societe"], donnees=json.dumps(donnees, ensure_ascii=False))
    texte = ia.demander(consigne, SCHEMA)
    return texte, controler(json.dumps(texte, ensure_ascii=False), valeurs_sources(donnees))


if __name__ == "__main__":
    dossier = sys.argv[1]
    v = json.load(open(f"{dossier}/valorisation.json"))
    for essai in range(2):                        # un second essai si un chiffre n'est pas retrouvé
        texte, suspects = rediger(v)
        if not suspects:
            break
    texte["chiffres_non_retrouves"] = suspects
    json.dump(texte, open(f"{dossier}/analyse.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(texte, ensure_ascii=False, indent=1))
    print(f"Coût de l'appel à l'IA : {ia.cout():.3f} $")
