# Installer NEXA CREDIT sur un NAS

Guide écrit pour un **Synology (DSM 7.2 ou plus récent)**. Il s'adapte à QNAP (Container Station) ou à tout NAS qui fait tourner Docker. Les menus changent d'une version à l'autre : si un intitulé ne correspond pas exactement, cherchez l'équivalent.

Durée : environ 1 heure la première fois.

---

## 0. Vérifications préalables

- **Docker disponible** : Synology → Centre de paquets → *Container Manager*. S'il n'apparaît pas, votre modèle ne le prend pas en charge : NEXA ne pourra pas tourner sur ce NAS.
- **Mémoire** : 1 Go libre suffit.
- **Accès SSH** activé : Panneau de configuration → Terminal & SNMP → *Activer le service SSH*. Vous pourrez le désactiver après l'installation.
- **Un gestionnaire de mots de passe** (Bitwarden, 1Password…) pour y ranger la clé de chiffrement.

## 1. Copier le logiciel sur le NAS

En SSH (`ssh votre-admin@IP-DU-NAS`) :

```bash
cd /volume1/docker            # dossier créé par Container Manager
sudo git clone -b claude/actelo-software-copy-t36ihc https://github.com/ELHIMASS/fabien.git nexa
cd nexa/nexa-credit
```

Le dépôt est privé : `git` vous demandera un identifiant GitHub et un *personal access token*. Sans SSH, vous pouvez aussi télécharger le ZIP de la branche sur GitHub et le déposer dans `docker/` avec File Station.

## 2. Créer les secrets (étape la plus importante)

```bash
sudo cp .env.example .env
sudo docker run --rm python:3.11-slim sh -c "pip -q install cryptography && python -c \"import secrets;from cryptography.fernet import Fernet;print('NEXA_JWT_SECRET='+secrets.token_urlsafe(48));print('NEXA_FILE_KEY='+Fernet.generate_key().decode())\""
```

Copiez les deux lignes affichées dans `.env` (`sudo vi .env`, ou éditez-le avec File Station).

> ⚠️ **Copiez `NEXA_FILE_KEY` tout de suite dans votre gestionnaire de mots de passe.** Elle chiffre les pièces et les sauvegardes. Si le NAS casse et que vous n'avez plus cette clé, **toutes les données sont perdues, même avec des sauvegardes**.

## 3. Droits sur le dossier de données

```bash
id                         # note uid=… et gid=… (souvent 1026 et 100 sur Synology)
sudo mkdir -p data
sudo chown 1026:100 data   # remplacez par vos valeurs
sudo chmod 700 data
```

Reportez ces valeurs dans `.env` (`NEXA_UID`, `NEXA_GID`).

## 4. Premier démarrage, en réseau local uniquement

Pour ce premier test en HTTP, mettez temporairement `NEXA_COOKIE_SECURE=0` dans `.env`, puis :

```bash
sudo docker compose up -d --build     # 3 à 10 minutes la première fois
sudo docker compose ps                 # « healthy » après une minute environ
```

Ouvrez **http://IP-DU-NAS:8000** depuis un ordinateur de la maison. L'écran de création du cabinet s'affiche : créez votre compte administrateur.

Vous pouvez aussi passer par Container Manager → *Projet* → *Créer*, choisir le dossier `nexa-credit`, et il détecte le `docker-compose.yml`.

> ❌ **N'ouvrez pas le port 8000 sur votre box.** L'accès depuis Internet se fait par le tunnel (étape 5), jamais par une redirection de port.

## 5. Accès depuis Internet, en HTTPS (indispensable pour l'espace client)

Méthode recommandée : **Cloudflare Tunnel**. Aucun port n'est ouvert sur la box, le HTTPS est automatique et seul NEXA est exposé, pas le reste du NAS.

Il vous faut un **nom de domaine** (environ 10 € par an, par exemple `nexa-credit.fr`) géré par Cloudflare (compte gratuit).

1. Cloudflare → *Zero Trust* → *Networks* → *Tunnels* → *Create a tunnel* → type *Cloudflared* → nommez-le `nexa`.
2. Choisissez l'environnement *Docker* et copiez **uniquement le jeton** (la longue chaîne après `--token`).
3. *Public hostname* : sous-domaine `app`, domaine `votre-domaine.fr`, service **HTTP** → `nexa:8000`.
4. Dans `.env` :
   ```
   CLOUDFLARE_TUNNEL_TOKEN=le-jeton-copié
   NEXA_COOKIE_SECURE=1
   NEXA_FORWARDED_ALLOW_IPS=*
   ```
5. Relancez avec le tunnel :
   ```bash
   sudo docker compose --profile internet up -d
   ```
6. Ouvrez **https://app.votre-domaine.fr**.

### Protection supplémentaire fortement recommandée (en attendant la double authentification dans NEXA)

Cloudflare → *Zero Trust* → *Access* → *Applications* → *Add* → *Self-hosted* :
- domaine `app.votre-domaine.fr`, règle **Allow** limitée à votre adresse e-mail (et à celles de vos collaborateurs) ;
- ajoutez une seconde application **Bypass** (accès pour tous) sur les chemins `app.votre-domaine.fr/espace/*`, `/api/espace/*` et `/assets/*`, pour que vos clients accèdent à leur espace sans compte Cloudflare.

Résultat : pour ouvrir l'interface courtier, il faut d'abord un code reçu par e-mail, **puis** votre mot de passe NEXA. Vos clients, eux, n'accèdent qu'à leur espace de dépôt.

> ℹ️ Avec Cloudflare, le trafic est déchiffré chez Cloudflare (entreprise américaine, qui propose un contrat de sous-traitance RGPD) avant d'arriver au NAS. Mentionnez-le dans votre registre des traitements. Si vous refusez ce compromis, l'alternative est le proxy inversé de DSM avec Let's Encrypt et une redirection du port 443 : dans ce cas, c'est le NAS entier qui devient joignable depuis Internet.

## 6. Sauvegardes (à mettre en place le jour même)

**Sauvegarde quotidienne chiffrée** : Panneau de configuration → *Planificateur de tâches* → *Créer* → *Tâche planifiée* → *Script défini par l'utilisateur*, utilisateur `root`, tous les jours à 2 h :

```bash
docker exec nexa-credit python -m app.sauvegarde
```

Les archives s'accumulent dans `nexa-credit/data/sauvegardes/` (les 30 dernières sont conservées).

**Copie hors du NAS** : *Hyper Backup* → copier `docker/nexa/nexa-credit/data/sauvegardes` vers un disque USB **et** un stockage distant (Synology C2, un autre NAS…). Une sauvegarde qui reste sur le même NAS ne protège ni contre un vol, ni contre un incendie, ni contre un rançongiciel.

**Tester une restauration une fois**, pour de vrai :

```bash
sudo docker compose stop nexa
sudo docker compose run --rm nexa python -m app.sauvegarde liste
sudo docker compose run --rm nexa python -m app.sauvegarde restaurer /data/sauvegardes/nexa-AAAAMMJJ-HHMMSS.nexa-sauvegarde
sudo docker compose start nexa
```

L'ancienne base est conservée à côté, avec le suffixe `.avant-restauration-…`.

## 7. Mettre à jour NEXA

```bash
cd /volume1/docker/nexa/nexa-credit
sudo docker exec nexa-credit python -m app.sauvegarde    # toujours sauvegarder avant
sudo git pull
sudo docker compose --profile internet up -d --build
```

## 8. Sécurité du NAS lui-même

- DSM et Container Manager à jour (mises à jour automatiques de sécurité).
- Double authentification activée sur le compte administrateur DSM.
- Compte `admin` par défaut désactivé.
- QuickConnect et les redirections de ports inutiles désactivés.
- SSH désactivé après l'installation.
- Onduleur conseillé : une coupure de courant pendant une écriture peut corrompre la base.

## Limites à connaître

- **Disponibilité** : si la box ou le NAS s'arrête, vos clients ne peuvent plus déposer de pièces. Pour un cabinet seul, c'est acceptable ; pour une équipe, un hébergeur professionnel devient préférable.
- **Pas de double authentification intégrée à NEXA** pour l'instant : d'où la protection Cloudflare Access de l'étape 5.
- La base SQLite convient pour un cabinet. Au-delà de quelques utilisateurs simultanés, passer à PostgreSQL.
