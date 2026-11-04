# Chauffage Manager

Intégration Home Assistant : chauffages fil pilote (select ZHA) et thermostats (climate), plannings intégrés, groupes, mode absence multi-personnes.

L'interface est fournie par la carte [Chauffage Manager Card](https://github.com/Mookunicorn/chauffage-manager-card) (dépôt séparé).

[![Ouvrir l'intégration dans HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Mookunicorn&repository=ha-chauffage-manager&category=integration)
[![Ouvrir la carte dans HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Mookunicorn&repository=chauffage-manager-card&category=plugin)

## Installation via HACS
1. HACS → menu ⋮ → **Dépôts personnalisés** :
   - `https://github.com/Mookunicorn/ha-chauffage-manager` → catégorie **Intégration**
   - `https://github.com/Mookunicorn/chauffage-manager-card` → catégorie **Tableau de bord**
2. Télécharger les deux, redémarrer Home Assistant, puis recharger la page sans cache.
3. Paramètres → Appareils et services → Ajouter → **Chauffage Manager** (choisir les personnes).
4. Ajouter la carte :
```yaml
type: custom:chauffage-manager-card
title: Chauffage          # optionnel
tabs: [rooms, schedules, absence, config]   # optionnel, ex. [rooms] pour une carte « pièces » seule
```
5. Onglet **Configuration** : ajouter chaque chauffage (select fil pilote `select.chauffage_*_mode`, + climate optionnel pour la température ; ou climate pour le thermostat), puis les groupes. Onglet **Plannings** : créer les plannings ; assignation dans **Pièces** (mode Auto).

## Fonctionnement
- Un chauffage ou groupe est en **Auto** (suit son planning) ou **Manuel**. En Manuel, un clic sur un mode l'applique ; modifier l'entité à la main reste possible.
- Groupe = commandes et planning communs à tous ses membres (un chauffage ne peut être que dans un groupe).
- Créneau de planning : jours + heure + mode (+ température pour les thermostats). Il reste actif jusqu'au créneau suivant.
- **Absence** : quand aucune des personnes cochées n'est à la maison, l'état (auto/manuel + mode) est sauvegardé puis :
  - programmation « Manuel » → le mode d'absence est appliqué partout ;
  - programmation « Automatique » → les chauffages suivent leur planning.
  Au retour d'au moins une personne, l'état est restauré si l'option est activée. Thermostats : température d'absence réglée par chauffage.
- Entités : `select.chauffage_<nom>_programmation` (auto/manuel), `select.chauffage_mode_absence`, `select.chauffage_programmation_en_absence`, `switch.chauffage_restauration_au_retour`, `binary_sensor.chauffage_absence`.
- Services : `chauffage_manager.set_control` (target, control), `chauffage_manager.set_manual` (target, mode, temperature). `target` = nom ou id.

## Migration depuis une config à base d'input_select / scheduler-card
Supprimer ensuite : les `input_select` de mode et de programmation par chauffage, les `input_text` de valeurs d'absence, les réglages d'absence et de reprise, les automatisations présence/absence/sauvegarde, et les schedules scheduler-card correspondants.
