"""Le seul endroit qui parle à l'IA : l'API Claude d'Anthropic.
Il suffit d'une clé API dans la variable d'environnement ANTHROPIC_API_KEY (ou dans un fichier .env).
La réponse est contrainte par un schéma JSON : l'IA ne peut rendre que la structure demandée."""
import json, os, pathlib, sys
import anthropic

MODELE = os.environ.get("ANALYSTE_MODELE", "claude-opus-5-5")
EFFORT = os.environ.get("ANALYSTE_EFFORT", "medium")      # low | medium | high : plus haut = plus soigné, plus cher

# coût en dollars par million de jetons (entrée, sortie), tarifs publics Anthropic
TARIFS = {"claude-opus-5-5": (4.00, 20.00), "claude-sonnet-5-5": (2.00, 10.00), "claude-haiku-5-5": (0.10, 0.50)}
depense = {"entree": 0, "sortie": 0}


def _charger_env():
    """Lit un fichier .env à la racine du projet, s'il existe (jamais versionné)."""
    env = pathlib.Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for ligne in env.read_text().splitlines():
            if "=" in ligne and not ligne.strip().startswith("#"):
                cle, valeur = ligne.split("=", 1)
                os.environ.setdefault(cle.strip(), valeur.strip().strip('"'))


def demander(consigne, schema, max_tokens=16000):
    """Envoie une consigne, renvoie un dict conforme au schéma."""
    _charger_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Clé API manquante : créez-en une sur console.anthropic.com, "
                 "puis écrivez ANTHROPIC_API_KEY=... dans le fichier .env du projet.")
    client = anthropic.Anthropic()
    try:
        reponse = client.beta.messages.create(
            model=MODELE,
            max_tokens=max_tokens,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",                   # si le modèle refuse, l'API relance sur un modèle de secours
            output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": consigne}],
        )
    except anthropic.AuthenticationError:
        sys.exit("Clé API refusée : vérifiez ANTHROPIC_API_KEY.")
    except anthropic.RateLimitError:
        sys.exit("Limite de débit atteinte : réessayez dans une minute.")
    except anthropic.APIStatusError as e:
        if e.status_code == 529:
            sys.exit("API surchargée : réessayez dans quelques minutes.")
        sys.exit(f"Erreur de l'API ({e.status_code}) : {e.message}")
    except anthropic.APIConnectionError:
        sys.exit("Pas de connexion à l'API : vérifiez internet.")

    if reponse.stop_reason == "refusal":
        sys.exit("L'IA a refusé la demande.")
    if reponse.stop_reason == "max_tokens":
        sys.exit("Réponse coupée (max_tokens atteint).")

    depense["entree"] += reponse.usage.input_tokens
    depense["sortie"] += reponse.usage.output_tokens
    texte = next(b.text for b in reponse.content if b.type == "text")
    return json.loads(texte)


def cout():
    e, s = TARIFS.get(MODELE, (0, 0))
    return depense["entree"] / 1e6 * e + depense["sortie"] / 1e6 * s
