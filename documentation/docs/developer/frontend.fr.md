# Développement du frontend

??? warning "Dépendances système"
    Avant d'exécuter ces étapes, assurez-vous d'avoir
    [complété les étapes d'installation ici](/howler/developer/getting_started/#frontend-dependencies).

## Exécuter le serveur de développement

L'exécution de l'interface utilisateur Howler pour le développement est simple :

```shell
# Naviguer vers le répertoire UI
cd ui

# Installer les dépendances
pnpm install

# Exécuter le serveur de développement
pnpm dev
```

Le serveur de développement démarrera sur `http://localhost:5173` par défaut (le port par défaut de Vite).

## Scripts disponibles

L'interface utilisateur fournit plusieurs scripts npm pour le développement :

- `pnpm dev` ou `pnpm start` - Démarrer le serveur de développement Vite
- `pnpm build` - Construire l'application pour la production (exécute le compilateur TypeScript et la construction Vite)
- `pnpm serve` - Prévisualiser la construction de production localement
- `pnpm lint` - Formater le code en utilisant Prettier
- `pnpm test` - Exécuter les tests avec couverture en utilisant Vitest
- `pnpm test-ui` - Exécuter les tests avec interface et couverture

## Dépendances clés

L'interface utilisateur Howler est construite avec des technologies web modernes :

### Framework de base

- **React 18** - Le framework d'interface utilisateur qui alimente l'application
- **React Router v6** - Routage côté client
- **TypeScript** - Sécurité des types et expérience de développement améliorée
- **Vite** - Outil de construction et serveur de développement rapide

### Composants UI et stylisation

- **Material-UI (MUI) v5** - Bibliothèque de composants principale fournissant le système de design

### Gestion d'état et données

- **axios** - Client HTTP pour les requêtes API
- **use-context-selector** - Contexte React optimisé pour la gestion d'état
- **react-pluggable** - Système de plugins pour l'extensibilité

### Édition de code et de contenu

- **Monaco Editor** - Composant d'éditeur de VS Code (via @monaco-editor/react)
- **react-markdown** - Rendu Markdown avec support markdown GitHub-flavored

### Utilitaires

- **dayjs** - Bibliothèque de date/heure légère
- **lodash-es** - Bibliothèque d'utilitaires moderne (modules ES)
- **i18next** - Framework d'internationalisation

### Outils de développement

- **Vitest** - Framework de tests unitaires rapide (natif Vite)
- **ESLint** - Linting de code avec intégration TypeScript, React et Prettier
- **Prettier** - Formatage de code
- **lint-staged** - Exécuter les linters sur les fichiers mis en scène

## Visual Studio Code

Si vous développez dans VS Code, il est recommandé d'installer les extensions recommandées de l'espace de travail pour
le support intégré de Prettier et ESLint. Celles-ci se trouvent dans le fichier `.vscode/extensions.json`.
