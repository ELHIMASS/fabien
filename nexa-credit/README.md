# NEXA CREDIT

Logiciel de gestion des dossiers de crédit immobilier pour courtiers IOBSP.

**Statut : version 0.1, pas encore validée pour la production.** Ne saisissez pas de données clients réelles avant la mise en production décrite plus bas.

## Fonctions

| Module | Contenu |
|---|---|
| Dossiers | Pipeline (Découverte → Facturé), emprunteurs, charges, projet, dates clés (compromis, condition suspensive, acte) |
| Plan de financement | Prêts multiples : amortissable, **PTZ**, **relais**, in fine, différé partiel ou total ; prêt principal ajusté automatiquement au solde du plan |
| Moteur de calcul | Mensualités, tableau d'amortissement, coût total, TAEG estimé (actuariel), capacité d'emprunt |
| Contrôles automatiques | Endettement et durée HCSF, usure, apport supérieur à l'épargne, épargne résiduelle, reste à vivre, saut de charge, période d'essai, CDD, TNS de moins de 3 ans, âge en fin de prêt, pièces manquantes, échéance de la condition suspensive |
| Pièces | Liste générée selon le profil (salarié, TNS, SCI, locatif, relais, construction…), dépôt de fichiers **chiffrés**, statuts à contrôler / validée / refusée, mail de relance généré |
| Banques | Comparatif des offres sur un même montant : mensualité, coût total, TAEG estimé, écart avec la meilleure |
| Synthèse bancaire | Présentation du dossier générée automatiquement (points forts, points de vigilance) |
| Facturation | Honoraires et commissions ; facturation bloquée avant le déblocage des fonds (art. L519-6 CMF) |
| Cabinet | Multi-utilisateurs (admin, courtier, assistant), règles d'analyse paramétrables, taux d'usure à saisir chaque trimestre |
| RGPD | Traçabilité du consentement, export JSON (accès/portabilité), effacement définitif, repérage des dossiers au-delà de la durée de conservation, journal d'audit |

## Architecture

- `backend/` : Python 3.11, FastAPI, SQLAlchemy (SQLite en local, PostgreSQL en production via `NEXA_DATABASE_URL`)
  - `app/calc/finance.py` : moteur de calcul pur, testé
  - `app/calc/analyse.py` : plan, ratios, contrôles, pièces attendues, synthèse
  - `app/routers/` : API REST (documentation interactive sur `/api/docs`)
- `frontend/` : React 19 + Vite, servi par le backend une fois compilé

### Sécurité en place
- Mots de passe hachés en Argon2id, 12 caractères minimum ; 5 tentatives de connexion par tranche de 5 minutes
- Session dans un cookie `httpOnly`, `SameSite=Strict` (et `Secure` en production), plus un en-tête anti-CSRF obligatoire
- Cloisonnement strict entre cabinets (testé)
- Pièces chiffrées au repos (Fernet), type de fichier vérifié par signature et non par l'extension, 15 Mo maximum
- Journal d'audit : connexions, échecs, consultations, modifications, exports, effacements

## Démarrage local

```bash
./demarrer.sh --demo     # compte démo : demo@nexa-credit.fr / DemoNexa2026!
```
Puis ouvrir http://127.0.0.1:8000. Sans `--demo`, le premier écran crée le cabinet et son administrateur.

Développement : `uvicorn app.main:app --reload` dans `backend/` et `npm run dev` dans `frontend/` (http://localhost:5173).

Tests : `cd backend && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest`

## Avant la production (obligatoire)

1. **Hébergement en France/UE** (ISO 27001, idéalement SecNumCloud ; HDS seulement si vous stockez des questionnaires de santé d'assurance emprunteur), sauvegardes chiffrées quotidiennes, HTTPS obligatoire.
2. Variables : `NEXA_ENV=prod`, `NEXA_JWT_SECRET`, `NEXA_FILE_KEY` (sauvegarder cette clé hors serveur : sans elle les pièces sont illisibles), `NEXA_DATABASE_URL` (PostgreSQL).
3. Registre des traitements, mentions d'information client, contrats de sous-traitance (hébergeur) et analyse d'impact (AIPD) si le volume le justifie.
4. Saisir les taux d'usure du trimestre dans Paramètres.
5. Faire relire par un juriste les règles métier codées (HCSF, L519-6, durées de conservation).
6. Test d'intrusion avant d'ouvrir l'accès à d'autres utilisateurs.

## Limites connues (v0.1)

- Le PTZ n'est **pas calculé** (éligibilité, zone, quotité) : saisie manuelle des conditions.
- Prêts lissés et paliers non gérés ; assurance calculée uniquement sur le capital initial.
- TAEG **estimé** : seul celui de l'offre bancaire fait foi.
- Pas encore de lecture automatique des documents (OCR / Cred'IA), de signature électronique, ni d'espace client.
- Limitation des tentatives de connexion en mémoire : prévoir Redis si plusieurs processus.
