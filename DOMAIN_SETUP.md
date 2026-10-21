# Raccorder geo-cadastre.fr à Géo-Cadastre

Le propriétaire a retenu ce domaine existant chez one.com. Aucun achat ni
nouveau forfait d’hébergement n’est nécessaire. Le site reste hébergé sur
GitHub Pages, le backend sur Render Free avec stockage persistant Neon Free.

La vitrine renommée est accessible à son adresse GitHub Pages tant que le domaine
n’est pas activé et vérifié :
https://matthieuangeli-code.github.io/satellite-timeline-viewer/

## 1. Enregistrements chez one.com

Ouvrir le domaine `geo-cadastre.fr`, puis ses réglages DNS. Sauvegarder les
valeurs actuelles avant de modifier les seuls enregistrements du site web.
Pour la racine, le champ Nom/Hôte est `@` ou vide selon l’interface.

| Type | Nom | Valeur |
|---|---|---|
| A | @ | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |
| CNAME | www | matthieuangeli-code.github.io |

La cible CNAME ne contient ni `https://`, ni le nom du dépôt.
Remplacer les anciens A du site à la racine, plutôt que de conserver des
adresses d’anciens hébergements dans le même ensemble. Conserver les MX et TXT
liés aux e-mails et ne pas modifier les autres domaines.

Si des AAAA existent déjà pour le site et pointent ailleurs, les remplacer par
les quatre adresses IPv6 GitHub ci-dessous, ou retirer uniquement ces anciens
AAAA web si l’on utilise les A IPv4 seuls :

| Type | Nom | Valeur |
|---|---|---|
| AAAA | @ | 2606:50c0:8000::153 |
| AAAA | @ | 2606:50c0:8001::153 |
| AAAA | @ | 2606:50c0:8002::153 |
| AAAA | @ | 2606:50c0:8003::153 |

## 2. Activation sur GitHub et vérification

Dans le dépôt `satellite-timeline-viewer` : **Settings → Pages → Custom domain**,
renseigner `geo-cadastre.fr`. Effectuer la vérification de propriété du domaine
si GitHub la demande. Attendre la validation DNS et le certificat, puis activer
**Enforce HTTPS** lorsqu’il est disponible. Vérifier le domaine racine et www.

Le site est publié par un workflow Actions : un fichier CNAME ajouté aux fichiers
statiques est ignoré et n’est pas requis. Ne pas annoncer le domaine comme actif
sur la seule présence d’un tel fichier ou d’un réglage GitHub.

## 3. Bascule de l’application

Après vérification HTTPS, publier les URL canoniques, les métadonnées de partage
et le sitemap avec la base `https://geo-cadastre.fr/`. Mettre à jour l’URL frontend
publique dans le backend pour les origines autorisées et les retours Stripe TEST.
Préserver la base, les secrets et la clé de signature. Finir les essais en cours
avant bascule : les jetons conservés dans un navigateur sur l’ancienne origine
ne sont pas transférés automatiquement à la nouvelle.

Vérifier ensuite l’exploration mobile/ordinateur et le parcours sandbox réel.
Les achats réels restent fermés ; ce raccordement ne les active pas.

Source officielle consultée le 21 octobre 2026 :
[GitHub Pages — gérer un domaine personnalisé](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site).
