"""Étape 5 : met tout en page sur une fiche A4, puis l'imprime en PDF (Chrome sans fenêtre)."""
import datetime, html, json, pathlib, subprocess, sys

OUTIL = pathlib.Path(__file__).resolve().parent.parent / "outils" / "html2pdf"   # WebKit de macOS, sans fenêtre


def fr(x, d=0):
    """Nombre à la française : 80807 -> '80 807' ; 22.04 -> '22,0'."""
    s = f"{x:,.{d}f}".replace(",", " ").replace(".", ",")
    return s.replace("-", "−")


def md(x):
    return fr(x / 1000, 1)


def tableau_historique(c, r):
    p = lambda poste: c["postes"][poste]["2025"]["page"]
    lignes = [
        ("Ventes (Md€)", lambda a: md(r[a]["ventes"]), p("ventes")),
        ("Croissance des ventes", lambda a: fr(r[a]["croissance_ventes_pct"], 1) + " %" if r[a]["croissance_ventes_pct"] is not None else "–", p("ventes")),
        ("Marge brute", lambda a: fr(r[a]["marge_brute_pct"], 1) + " %", p("marge_brute")),
        ("Marge opérationnelle courante", lambda a: fr(r[a]["marge_roc_pct"], 1) + " %", p("resultat_operationnel_courant")),
        ("Résultat net part du groupe (Md€)", lambda a: md(c["postes"]["resultat_net_part_du_groupe"][a]["valeur"]), p("resultat_net_part_du_groupe")),
        ("Cash-flow disponible d'exploitation (Md€)", lambda a: md(r[a]["fcf_exploitation"]), p("flux_exploitation")),
        ("Dette financière nette (Md€)", lambda a: md(r[a]["dette_financiere_nette"]), p("dette_financiere_long_terme")),
        ("Dette nette y. c. loyers / EBITDA", lambda a: fr(r[a]["levier_dette_nette_sur_ebitda"], 1) + "x", p("dettes_locatives_long_terme")),
        ("Rentabilité des capitaux propres", lambda a: fr(r[a]["rentabilite_capitaux_propres_pct"], 1) + " %", p("capitaux_propres")),
    ]
    tete = "<tr><th></th>" + "".join(f"<th>{a}</th>" for a in sorted(r)) + "<th class='src'>Page</th></tr>"
    corps = "".join(f"<tr><td>{nom}</td>" + "".join(f"<td class='n'>{f(a)}</td>" for a in sorted(r)) + f"<td class='src'>{pg}</td></tr>"
                    for nom, f, pg in lignes)
    return f"<table class='hist'>{tete}{corps}</table>"


def football_field(fourchettes, cours):
    vals = [x for ab in fourchettes.values() for x in ab] + [cours]
    lo, hi = min(vals) * 0.9, max(vals) * 1.05
    L, W, H, ligne = 150, 190, 20, 0
    x = lambda v: L + (v - lo) / (hi - lo) * W
    barres = ""
    for i, (nom, (a, b)) in enumerate(fourchettes.items()):
        y = 4 + i * (H + 6)
        barres += (f"<text x='{L - 8}' y='{y + 16}' text-anchor='end' class='lab' dy='-2.5'>{html.escape(nom)}</text>"
                   f"<rect x='{x(a):.1f}' y='{y}' width='{x(b) - x(a):.1f}' height='{H}' class='bar{' marche' if 'Cours' in nom else ''}'/>"
                   f"<text x='{x(a) + 3:.1f}' y='{y + 13.5}' class='val in'>{fr(a)}</text>"
                   f"<text x='{x(b) - 3:.1f}' y='{y + 13.5}' text-anchor='end' class='val in'>{fr(b)}</text>")
        ligne = y + H
    return (f"<svg viewBox='0 0 {L + W + 50} {ligne + 30}' class='ff'>{barres}"
            f"<line x1='{x(cours):.1f}' x2='{x(cours):.1f}' y1='0' y2='{ligne + 6}' class='cours'/>"
            f"<text x='{x(cours):.1f}' y='{ligne + 22}' text-anchor='middle' class='coursl'>Cours : {fr(cours)} €</text></svg>")


def sensibilite(s, w_central, g_central):
    gs = list(next(iter(s.values())).keys())
    tete = "<tr><th>WACC \\ g</th>" + "".join(f"<th>{fr(float(g), 1)} %</th>" for g in gs) + "</tr>"
    corps = ""
    for w, ligne in s.items():
        corps += f"<tr><th>{fr(float(w), 1)} %</th>" + "".join(
            f"<td class='n{' c' if abs(float(w) - w_central) < 0.01 and abs(float(g) - g_central) < 0.01 else ''}'>{fr(v)}</td>"
            for g, v in ligne.items()) + "</tr>"
    return f"<table class='sens'>{tete}{corps}</table>"


def page(c, v, a):
    r, d, w = v["historique"], v["dcf"], v["wacc"]
    nb_verifies = sum(len(x) for x in c["postes"].values())
    liste = lambda xs: "".join(f"<li>{html.escape(x)}</li>" for x in xs)
    aujourdhui = datetime.date.today().strftime("%d/%m/%Y")
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{v['societe']} – Fiche d'analyse</title>
<style>
@page {{ size: A4; margin: 0; }}
html {{ background:#fff; }}
:root {{ --encre:#16181d; --gris:#5d6470; --filet:#d9dce1; --accent:#14532d; --fond:#f4f5f2; }}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ padding: 11mm 12mm; width: 210mm; font: 8.6pt/1.42 "Helvetica Neue", Helvetica, Arial, sans-serif; color:var(--encre); font-variant-numeric: tabular-nums; }}
header {{ display:flex; justify-content:space-between; align-items:flex-end; border-bottom:2px solid var(--encre); padding-bottom:5px; }}
h1 {{ font: 600 21pt/1 "Iowan Old Style", Georgia, serif; letter-spacing:-.01em; }}
h1 small {{ font: 400 9pt "Helvetica Neue", sans-serif; color:var(--gris); margin-left:6px; letter-spacing:0; }}
.meta {{ text-align:right; color:var(--gris); font-size:7.4pt; line-height:1.35; }}
h2 {{ font: 600 7.6pt "Helvetica Neue", sans-serif; text-transform:uppercase; letter-spacing:.08em; color:var(--accent); margin:10px 0 4px; }}
.une {{ font: 10.5pt/1.4 "Iowan Old Style", Georgia, serif; margin-top:8px; }}
.chiffres {{ display:flex; gap:0; margin-top:8px; border-top:1px solid var(--filet); border-bottom:1px solid var(--filet); }}
.chiffres div {{ flex:1; padding:5px 8px; border-left:1px solid var(--filet); }}
.chiffres div:first-child {{ border-left:0; padding-left:0; }}
.chiffres b {{ display:block; font: 600 13pt "Helvetica Neue", sans-serif; }}
.chiffres span {{ color:var(--gris); font-size:7.2pt; }}
.grille {{ display:grid; grid-template-columns: 1.08fr 1fr; gap:14px; }}
table {{ border-collapse:collapse; width:100%; }}
th, td {{ padding:2.4px 4px; border-bottom:1px solid var(--filet); text-align:left; }}
th {{ font-weight:600; color:var(--gris); font-size:7.4pt; }}
td.n, .sens th, .hist th {{ text-align:right; white-space:nowrap; }}
.hist td:first-child, .hist th:first-child {{ text-align:left; padding-left:0; }}
.src {{ color:var(--gris); font-size:7pt; text-align:right; }}
.sens td.c {{ background:var(--fond); font-weight:700; }}
ul {{ padding-left:12px; }} li {{ margin-bottom:3px; }}
.ff {{ width:100%; }}
.ff .lab {{ font-size:8px; fill:var(--encre); }} .ff .val {{ font-size:7.5px; fill:var(--gris); }}
.ff .val.in {{ fill:#fff; font-weight:600; }}
.ff .bar {{ fill:var(--accent); opacity:.85; }} .ff .bar.marche {{ fill:#9aa1ab; }}
.ff .cours {{ stroke:#b42318; stroke-width:1.4; stroke-dasharray:3 2; }} .ff .coursl {{ font-size:8px; fill:#b42318; font-weight:600; }}
.cadre {{ background:var(--fond); padding:7px 9px; margin-top:4px; }}
p + p {{ margin-top:4px; }}
footer {{ margin-top:10px; padding-top:5px; border-top:1px solid var(--filet); color:var(--gris); font-size:6.8pt; line-height:1.4; }}
.hyp {{ color:var(--gris); font-size:7.2pt; margin-top:4px; }}
</style></head><body>
<header>
  <h1>{v['societe']}<small>{v['ticker']} · Fiche d'analyse</small></h1>
  <div class="meta">Source : Document d'enregistrement universel {v['annee_de_base']}<br>Cours et comparables : Yahoo Finance, {aujourdhui}<br>Montants en euros</div>
</header>
<p class="une">{html.escape(a['en_une_phrase'])}</p>
<div class="chiffres">
  <div><b>{fr(v['cours'], 2)} €</b><span>Cours</span></div>
  <div><b>{md(v['capitalisation'])} Md€</b><span>Capitalisation</span></div>
  <div><b>{fr(d['prix_par_action'])} €</b><span>Valeur DCF par action</span></div>
  <div><b>{fr(d['croissance_implicite_dans_le_cours_pct'], 1)} %</b><span>Croissance perpétuelle implicite dans le cours</span></div>
  <div><b>{fr(v['marche'][v['ticker']]['dividendYield'], 1)} %</b><span>Rendement du dividende</span></div>
</div>
<div class="grille">
  <section>
    <h2>Chiffres clés, lus dans le rapport</h2>
    {tableau_historique(c, r)}
    <h2>Points forts</h2><ul>{liste(a['points_forts'])}</ul>
    <h2>Points de vigilance</h2><ul>{liste(a['points_de_vigilance'])}</ul>
  </section>
  <section>
    <h2>Fourchettes de valeur par action (€)</h2>
    {football_field(v['fourchettes'], v['cours'])}
    <h2>Lecture de la valorisation</h2>
    <p>{html.escape(a['lecture_de_la_valorisation'])}</p>
    <h2>Sensibilité du DCF (€ par action)</h2>
    {sensibilite(v['sensibilite'], w['wacc_pct'], d['croissance_perpetuelle_pct'])}
    <p class="hyp">WACC {fr(w['wacc_pct'], 2)} % : coût des fonds propres {fr(w['cout_fonds_propres_pct'], 2)} %, poids de la dette {fr(w['poids_dette_pct'], 1)} %. La valeur terminale pèse {fr(d['part_valeur_terminale_pct'])} % de la valeur d'entreprise.</p>
    <h2>Pour un gestionnaire de patrimoine</h2>
    <div class="cadre">{html.escape(a['pour_un_gestionnaire_de_patrimoine'])}</div>
  </section>
</div>
<footer>
  Méthode : Claude lit les états financiers du rapport annuel et cite la page de chaque chiffre ; un programme vérifie que chaque chiffre figure bien
  sur la page citée ({nb_verifies} chiffres vérifiés, {len(c['rejetes'])} rejeté). Tous les calculs sont faits en Python. Hypothèses du DCF détaillées et justifiées
  dans le dépôt. Pages = numéros du fichier PDF. Analyste IA, conçu par Gabin Eby Klein avec Claude.
  <br><b>Document pédagogique : ne constitue ni un conseil en investissement ni une recommandation.</b>
</footer>
</body></html>"""


if __name__ == "__main__":
    dossier = pathlib.Path(sys.argv[1]).resolve()
    c = json.load(open(dossier / "chiffres.json"))
    v = json.load(open(dossier / "valorisation.json"))
    a = json.load(open(dossier / "analyse.json"))
    (dossier / "fiche.html").write_text(page(c, v, a))
    pdf = dossier / f"fiche-{v['societe'].lower()}.pdf"
    subprocess.run([str(OUTIL), str(dossier / "fiche.html"), str(pdf)], capture_output=True, timeout=60)
    print(pdf)
