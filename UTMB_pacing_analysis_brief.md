# UTMB 2026 — Analyse comparative du pacing des coureurs de tête

## Objectif

Analyser et comparer la gestion de course (allure, effet du relief, fatigue) de plusieurs
coureurs élites sur l'UTMB 2026, à partir de données kilomètre par kilomètre issues de Strava.
Le but est de produire une analyse propre et documentée, publiable sur GitHub comme preuve de
compétence en traitement de données appliqué au sport.

## Données disponibles

Dossier `utmb_2026_data/`, 4 fichiers Excel, un par coureur :

- `dhiman_utmb2026.xlsx` — Ben Dhiman, 1er, 18:16:29
- `olson_utmb2026.xlsx` — Caleb Olson, 3e, 18:48:24
- `moriset_utmb2026.xlsx` — Virgile Moriset, 4e, 19:00:23
- `lopez_utmb2026.xlsx` — Joaquin Lopez, 5e, 19:06:48

Baptiste Chassagne (2e, 18:47:38) n'a pas publié son activité sur Strava et est donc exclu.

### Structure de chaque fichier

- Ligne 1-2 : `Name` et `Elapsed Time` (temps total officiel de la course)
- Puis un tableau avec une ligne par kilomètre parcouru, colonnes :
  - `KM` : numéro du kilomètre
  - `Allure` : allure brute sur ce kilomètre, format texte `"m:ss/km"`
  - `VAP` : allure ajustée à la pente (grade-adjusted pace), même format texte
  - `Alt.` : variation d'altitude sur ce kilomètre, en mètres, signée (ex. `-12 m`, `26 m`)
  - `Cadence` : cadence moyenne sur ce kilomètre, en pas par minute (`ppm`)

Les 4 fichiers ont exactement les mêmes colonnes, aucune donnée de fréquence cardiaque n'est
disponible (les coureurs ne portaient pas tous une ceinture cardiaque, la colonne a donc été
retirée pour rester cohérent entre les 4 coureurs).

## Tâches à réaliser

1. **Chargement et nettoyage**
   Charger les 4 fichiers, extraire nom et temps total, parser les colonnes `Allure` et `VAP`
   en secondes par kilomètre, parser `Alt.` en mètres (nombre signé), parser `Cadence` en entier.

2. **Reconstruction du profil du parcours**
   Calculer l'altitude cumulée à partir des variations par kilomètre, et le temps cumulé
   (somme des allures) pour situer chaque kilomètre dans la course.

3. **Effet du relief sur l'allure**
   Comparer `Allure` brute et `VAP` pour chaque coureur, afin de visualiser l'écart entre
   l'allure réelle et l'allure "équivalent plat". Un grand écart signale une portion très
   pentue (montée ou descente).

4. **Détection de fatigue**
   Pour chaque coureur, comparer l'évolution de l'écart Allure/VAP entre la première et la
   seconde moitié de course sur des tronçons à dénivelé comparable, pour repérer une éventuelle
   dégradation de la performance en fin de course qui ne s'explique pas seulement par le relief.

5. **Comparaison entre coureurs**
   Sur les tronçons communs (même kilométrage), comparer les 4 coureurs entre eux : qui est le
   plus rapide en montée, en descente, qui montre le moins de signes de fatigue.

6. **Visualisations attendues**
   - Profil d'altitude du parcours (une courbe, commune aux 4 coureurs)
   - Courbe allure vs VAP pour chaque coureur
   - Graphique comparatif des 4 coureurs sur une même métrique (ex. allure ajustée à la pente
     par tranche de 10 km)
   - Graphique de l'indice de fatigue par coureur (première moitié vs seconde moitié)

7. **README.md**
   Rédiger un README clair expliquant la question posée, l'origine des données (Strava, activités
   publiques des coureurs), la méthode utilisée, les résultats principaux, et les limites de
   l'analyse (échantillon de 4 coureurs, une seule édition de course, HR disponible pour un seul
   coureur).

8. **Structure du dépôt**
   Organiser le tout proprement pour un dépôt GitHub : dossier `utmb_2026_data/` pour les fichiers sources,
   un notebook ou des scripts Python clairs, un dossier `figures/` pour les graphiques exportés,
   et le README à la racine.

## Points de vigilance

- Vérifier la cohérence entre le temps total (`Elapsed Time`) et la somme des allures par
  kilomètre ; signaler l'écart s'il y en a un plutôt que de le corriger silencieusement.
- Rester factuel dans les commentaires et le README, sans sur-interpréter de petites variations
  de données comme des signes de fatigue certains.
