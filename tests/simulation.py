"""Simulation complète SANS clé API et sans dépenser un centime.

Un faux serveur Anthropic tourne en local. Le vrai SDK `anthropic` lui parle en HTTP
(ANTHROPIC_BASE_URL), donc tout le code du projet est exécuté tel quel. Le faux serveur :
  - vérifie chaque requête (modèle, en-tête bêta, schéma JSON valide et strict) ;
  - répond comme l'API, avec les chiffres d'un vrai passage précédent ;
  - glisse un chiffre inventé, pour vérifier que le contrôle par page le rejette ;
  - joue aussi les erreurs (clé refusée, surcharge, refus, réponse coupée).

Lancer depuis la racine du projet : python tests/simulation.py
"""
import http.server, json, os, pathlib, shutil, subprocess, sys, tempfile, threading
import jsonschema

RACINE = pathlib.Path(__file__).resolve().parent.parent
SOURCE = RACINE / "rapports" / "lvmh-2025"
CHIFFRE_INVENTE = {"poste": "ventes", "annee": "2025", "valeur": "99 999", "page": 338}
mode = {"erreur": None}
journal = []


def fr(x):
    """84683.0 -> '84 683' ; -1065 -> '(1 065)' ; 25.67 -> '25,67' (comme dans le rapport)."""
    s = f"{abs(x):,.2f}".rstrip("0").rstrip(".") if x != int(x) else f"{abs(x):,.0f}"
    s = s.replace(",", " ").replace(".", ",")
    return f"({s})" if x < 0 else s


def strict(schema, chemin="racine"):
    """Règles des sorties structurées : tout objet ferme ses champs et les rend tous obligatoires."""
    if schema.get("type") == "object":
        assert schema.get("additionalProperties") is False, f"{chemin} : additionalProperties doit être false"
        assert set(schema.get("required", [])) == set(schema["properties"]), f"{chemin} : tous les champs requis"
        for k, v in schema["properties"].items():
            strict(v, f"{chemin}.{k}")
    if schema.get("type") == "array":
        strict(schema["items"], chemin + "[]")


def reponse_simulee(schema):
    props = schema["properties"]
    if "valeurs" in props:                                   # étape 2 : lecture des états financiers
        c = json.load(open(SOURCE / "chiffres.json"))
        valeurs = [{"poste": p, "annee": a, "valeur": fr(i["valeur"]), "page": i["page"]}
                   for p, annees in c["postes"].items() for a, i in annees.items()]
        return {"unite": c["unite"], "valeurs": valeurs + [CHIFFRE_INVENTE]}
    if set(props) == {"x"}:                                  # requête de test des erreurs
        return {"x": "test"}
    a = json.load(open(SOURCE / "analyse.json"))             # étape 4 : rédaction
    return {k: a[k] for k in props}


class FausseAPI(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def repondre(self, code, corps):
        data = json.dumps(corps).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        corps = json.loads(self.rfile.read(int(self.headers["content-length"])))
        # 1. la requête est-elle celle qu'attend la vraie API ?
        assert self.path.split("?")[0] == "/v1/messages", self.path
        assert "server-side-fallback-2026-07-01" in self.headers.get("anthropic-beta", "")
        assert (self.headers.get("x-api-key") or self.headers.get("authorization", "").startswith("Bearer ")) and self.headers.get("anthropic-version")
        assert corps["model"] == "claude-opus-5-5" and corps["fallbacks"] == "default"
        fmt = corps["output_config"]["format"]
        assert fmt["type"] == "json_schema" and corps["output_config"]["effort"] in ("low", "medium", "high")
        jsonschema.Draft202012Validator.check_schema(fmt["schema"])
        strict(fmt["schema"])

        erreur = mode["erreur"]
        if erreur in (401, 429, 529):
            types = {401: "authentication_error", 429: "rate_limit_error", 529: "overloaded_error"}
            return self.repondre(erreur, {"type": "error", "error": {"type": types[erreur], "message": "simulé"}})

        sortie = reponse_simulee(fmt["schema"])
        jsonschema.validate(sortie, fmt["schema"])          # 2. la réponse respecte le schéma
        texte = json.dumps(sortie, ensure_ascii=False)
        entree = len(json.dumps(corps, ensure_ascii=False)) // 3   # ~3 caractères par jeton en français
        journal.append((entree, len(texte) // 3))
        self.repondre(200, {
            "id": "msg_simulation", "type": "message", "role": "assistant", "model": corps["model"],
            "content": [{"type": "text", "text": texte}],
            "stop_reason": erreur or "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": entree, "output_tokens": len(texte) // 3},
        })


def main():
    serveur = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FausseAPI)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    env = {**os.environ, "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{serveur.server_port}",
           "ANTHROPIC_API_KEY": "sk-ant-simulation", "PYTHONPATH": str(RACINE / "analyste")}

    with tempfile.TemporaryDirectory() as tmp:
        dossier = pathlib.Path(tmp) / "lvmh-2025"
        shutil.copytree(SOURCE, dossier, ignore=shutil.ignore_patterns("pages.jsonl", "fiche*", "*.json"))
        for f in ("chiffres.json", "valorisation.json", "analyse.json"):
            assert not (dossier / f).exists()

        print("=== Chaîne complète, vrai SDK, faux serveur ===")
        r = subprocess.run([sys.executable, "-m", "analyste", str(dossier), str(RACINE / "hypotheses" / "lvmh-2025.yaml")],
                           cwd=RACINE, env=env, capture_output=True, text=True, timeout=600)
        print("\n".join(l for l in r.stdout.splitlines() if l.startswith(("→", "États", "  rejeté")) or "vérifiés" in l or "Coût" in l))
        assert r.returncode == 0, r.stderr[-2000:]
        c = json.load(open(dossier / "chiffres.json"))
        attendu = sum(len(v) for v in json.load(open(SOURCE / "chiffres.json"))["postes"].values())
        assert sum(len(v) for v in c["postes"].values()) == attendu
        assert c["rejetes"] == ["ventes 2025 = 99 999 (page 338)"], c["rejetes"]
        assert json.load(open(dossier / "analyse.json"))["chiffres_non_retrouves"] == []
        assert (dossier / "fiche-lvmh.pdf").stat().st_size > 10_000
        print(f"OK : {attendu} chiffres vérifiés, le chiffre inventé est rejeté, fiche PDF produite")

    e, s = map(sum, zip(*journal))
    print("\n=== Erreurs de l'API ===")
    sys.path.insert(0, str(RACINE / "analyste"))
    os.environ.update({k: env[k] for k in ("ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY")})
    import anthropic, ia
    vrai = anthropic.Anthropic
    anthropic.Anthropic = lambda **kw: vrai(max_retries=0, **kw)        # pas d'attente entre essais
    schema = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"], "additionalProperties": False}
    attendus = {401: "Clé API refusée", 429: "Limite de débit", 529: "surchargée",
                "refusal": "a refusé", "max_tokens": "coupée"}
    for cas, attendu in attendus.items():
        mode["erreur"] = cas
        try:
            ia.demander("test", schema)
            raise AssertionError(f"{cas} : aucune erreur levée")
        except SystemExit as erreur:
            assert attendu in str(erreur), f"{cas} : message inattendu « {erreur} »"
            print(f"OK {cas!s:>10} -> {erreur}")
    mode["erreur"] = None
    serveur.shutdown()

    print(f"\nJetons simulés sur une fiche : {e:,} en entrée, {s:,} en sortie "
          f"-> environ {e / 1e6 * 4 + s / 1e6 * 20:.2f} $ avec Opus 5.5")
    print("TOUT EST BON")


if __name__ == "__main__":
    main()
