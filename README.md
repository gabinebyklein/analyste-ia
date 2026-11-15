# Analyste IA

Transforme le rapport annuel d'une entreprise cotée (492 pages pour LVMH) en **fiche d'analyse d'une page** : chiffres clés, valorisation par DCF et par comparables, points forts, points de vigilance et lecture pour un gestionnaire de patrimoine.

**Le principe : l'IA lit, le code calcule, et rien n'est cru sur parole.**

**Essayer en ligne (DCF réglable) : [analyste-ia.vercel.app](https://analyste-ia.vercel.app)**

| Étape | Qui | Garde-fou |
|---|---|---|
| 1. Extraction du texte, page par page | Python (PyMuPDF) | numéro de page conservé |
| 2. Lecture des états financiers | Claude | les 3 états sont repérés quelle que soit leur formulation ; chaque chiffre est rendu **avec sa page** ; Python vérifie qu'il est écrit tel quel sur cette page, sinon il est rejeté |
| 2 bis. Recoupement officiel | Python | les chiffres sont comparés au dépôt **ESEF** de la société (format réglementaire européen, via filings.xbrl.org) |
| 3. Ratios, DCF, comparables, sensibilité | Python | hypothèses écrites et justifiées dans `hypotheses/*.yaml` |
| 4. Rédaction de l'analyse | Claude | ne reçoit que les chiffres calculés ; Python contrôle que chaque nombre du texte existe dans les données ; aucun conseil d'achat ou de vente |
| 5. Mise en page A4 et PDF | Python + WebKit | |

## Résultats sur trois sociétés (exercice 2025)

| Société | Chiffres lus et vérifiés sur leur page | Recoupés avec le dépôt officiel ESEF | Fiche |
|---|---|---|---|
| LVMH (luxe, 3 ans publiés) | 66 / 66 | 22 / 22 concordent | [`fiche-lvmh.pdf`](rapports/lvmh-2025/fiche-lvmh.pdf) |
| Hermès (luxe, quasi sans dette) | 38 / 38 | 24 / 24 concordent | [`fiche-hermes.pdf`](rapports/hermes-2025/fiche-hermes.pdf) |
| Danone (agroalimentaire, présentation différente) | 30 / 30 | 8 / 8 concordent | [`fiche-danone.pdf`](rapports/danone-2025/fiche-danone.pdf) |

Les trois rapports ne se ressemblent pas : titres des états différents (« Résultat consolidé et résultat par action » chez Danone, « État des flux de trésorerie » chez Hermès), 2 ou 3 années publiées, bilan sur une ou deux pages, dettes de loyers présentées à part ou incluses dans la dette financière. Le programme gère ces cas et dit, poste par poste, ce qu'il fait d'un chiffre absent.

Le DCF inversé indique la croissance perpétuelle que le cours suppose : 0,2 % pour LVMH, 4,6 % pour Hermès, −1,0 % pour Danone. C'est souvent plus parlant qu'une valeur cible. Pour Danone, l'écart entre le DCF et le cours vient du coût du capital : le MEDAF donne un taux bas pour un groupe très défensif, et le marché exige davantage.

## Lancer

```bash
pip install -r requirements.txt
cp .env.exemple .env                                   # puis y coller votre clé API
swiftc -O -o outils/html2pdf outils/html2pdf.swift     # macOS, une fois
# placer le rapport annuel PDF dans rapports/<societe-annee>/ puis :
python -m analyste rapports/lvmh-2025 hypotheses/lvmh-2025.yaml
```

Tester sans clé ni frais : `pip install jsonschema && python tests/simulation.py`. Un faux serveur Anthropic local reçoit les vraies requêtes du SDK, vérifie leur format, y glisse un chiffre inventé (il doit être rejeté) et joue les erreurs de l'API.

Clé API : copier `.env.exemple` en `.env` et y mettre une clé créée sur console.anthropic.com. Modèle par défaut : Claude Opus 5.5 (variable `ANALYSTE_MODELE` pour en changer).
Sans clé API, avec Claude Code installé : `ANALYSTE_IA=claude-code python -m analyste ...` (c'est ainsi qu'ont été produites les fiches Hermès et Danone).

Page web : `python analyste/publier_web.py` regroupe les résultats dans `web/donnees/`, puis `index.html` les affiche et refait le DCF dans le navigateur avec le même fichier `calculer.py` (Pyodide).

## Limites connues

- Les états financiers sont repérés par leur titre français (rapports d'émetteurs français) ; plusieurs formulations sont reconnues.
- Le recoupement ESEF dépend de ce que filings.xbrl.org a déjà publié (exercice 2025 pour Hermès, 2024 pour LVMH et Danone).
- Le DCF est volontairement simple : 5 ans de projection, valeur terminale de Gordon, loyers IFRS 16 traités comme des charges d'exploitation.
- Les multiples des comparables viennent de Yahoo Finance ; les valeurs aberrantes (VE/EBITDA > 40, PER > 60) sont écartées.

---

Projet personnel de Gabin Eby Klein, conçu et piloté avec Claude.
**Document pédagogique : ne constitue ni un conseil en investissement ni une recommandation.**
