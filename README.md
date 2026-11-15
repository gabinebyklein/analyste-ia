# Analyste IA

Transforme le rapport annuel d'une entreprise cotée (492 pages pour LVMH) en **fiche d'analyse d'une page** : chiffres clés, valorisation par DCF et par comparables, points forts, points de vigilance et lecture pour un gestionnaire de patrimoine.

**Le principe : l'IA lit, le code calcule, et rien n'est cru sur parole.**

| Étape | Qui | Garde-fou |
|---|---|---|
| 1. Extraction du texte, page par page | Python (PyMuPDF) | numéro de page conservé |
| 2. Lecture des états financiers | Claude | chaque chiffre est rendu **avec sa page** ; Python vérifie qu'il est écrit tel quel sur cette page, sinon il est rejeté |
| 3. Ratios, DCF, comparables, sensibilité | Python | hypothèses écrites et justifiées dans `hypotheses/*.yaml` |
| 4. Rédaction de l'analyse | Claude | ne reçoit que les chiffres calculés ; Python contrôle que chaque nombre du texte existe dans les données ; aucun conseil d'achat ou de vente |
| 5. Mise en page A4 et PDF | Python + WebKit | |

## Exemple : LVMH, exercice 2025

- 66 chiffres lus dans le rapport, 66 vérifiés, 0 rejeté
- Contrôle de cohérence : le cash-flow disponible d'exploitation 2024 recalculé (10 478 M€) correspond au chiffre publié par LVMH
- Résultat : [`rapports/lvmh-2025/fiche-lvmh.pdf`](rapports/lvmh-2025/fiche-lvmh.pdf)

Le DCF inversé indique la croissance perpétuelle que le cours actuel suppose. C'est souvent plus parlant qu'une valeur cible : elle se compare directement aux hypothèses de l'analyste.

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

## Limites connues

- Les états financiers sont repérés par leur titre français (rapports d'émetteurs français).
- Le DCF est volontairement simple : 5 ans de projection, valeur terminale de Gordon, loyers IFRS 16 traités comme des charges d'exploitation.
- Les multiples des comparables viennent de Yahoo Finance ; les valeurs aberrantes (VE/EBITDA > 40, PER > 60) sont écartées.

---

Projet personnel de Gabin Eby Klein, conçu et piloté avec Claude.
**Document pédagogique : ne constitue ni un conseil en investissement ni une recommandation.**
