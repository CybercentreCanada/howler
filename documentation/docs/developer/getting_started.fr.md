# Dépendances système

Afin de contribuer à Howler, vous devrez d'abord préparer votre environnement de développement.

??? tip "Notes sur le système d'exploitation"
    Veuillez noter que ces commandes ont été écrites pour être utilisées dans Ubuntu, soit sur Windows via WSL ou un OS
    Ubuntu autonome. Vous devrez adapter les instructions spécifiques au système d'exploitation à votre système
    d'exploitation personnel.

```shell
# Cloner le monorepo Howler
mkdir -p ~/repos && cd ~/repos
git clone git@github.com:CybercentreCanada/howler.git
cd howler
```

## Dépendances frontend

### Node.js

L'interface utilisateur de Howler est développée en utilisant [Vite](https://vitejs.dev/), qui nécessite Node.js v20
ou supérieur. Nous recommandons d'utiliser [Node Version Manager (nvm)](https://github.com/nvm-sh/nvm) pour gérer les
versions de Node.js.

??? tip "Installation sans NVM"
    NVM n'est pas requis - si vous préférez installer Node.js vous-même, vous pouvez le faire. Assurez-vous simplement
    que la version que vous installez est v20 ou supérieure pour être compatible avec Vite.

```shell
# Installer nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# Redémarrer votre shell ou exécuter :
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

# Installer et utiliser Node.js v20 (comme spécifié dans ui/.nvmrc)
nvm install v20
nvm use v20

# Optionnel : Définir v20 comme version par défaut
nvm alias default v20
```

### pnpm

L'interface utilisateur de Howler utilise [pnpm](https://pnpm.io/) pour la gestion des packages. Le projet impose
l'utilisation de pnpm via un script de préinstallation.

```shell
# Installer pnpm globalement
npm install -g pnpm

# Vérifier l'installation
pnpm --version
```

## Dépendances backend

### Docker

Le backend de Howler dépend de conteneurs Docker pour des services comme les bases de données, les files d'attente de
messages et d'autres composants d'infrastructure. Vous aurez besoin de Docker et Docker Compose installés.

Suivez le guide d'installation officiel de Docker pour votre système d'exploitation :
[Installation de Docker Engine](https://docs.docker.com/engine/install/)

Pour Ubuntu spécifiquement, voir : [Installer Docker sur Ubuntu](https://docs.docker.com/engine/install/ubuntu/)

<!-- markdownlint-disable -->
??? tip "Étapes post-installation"
    Après avoir installé Docker, vous voudrez peut-être ajouter votre utilisateur au groupe `docker` pour exécuter les
    commandes Docker sans `sudo` :

    ```shell
    # Ajouter le groupe docker (peut déjà exister)
    sudo groupadd docker

    # Ajouter l'utilisateur actuel au groupe docker
    sudo usermod -aG docker $USER

    # Se déconnecter et se reconnecter pour que le changement de groupe prenne effet
    ```

    Vérifier que Docker fonctionne :

    ```shell
    docker run hello-world
    ```
<!-- markdownlint-enable -->

### Python

Le backend de Howler nécessite Python 3.12. Nous recommandons d'utiliser [pyenv](https://github.com/pyenv/pyenv) pour
gérer les versions de Python, car cela vous permet d'installer et de basculer facilement entre plusieurs versions de
Python.

#### Installation de pyenv

Pour des instructions d'installation détaillées, consultez le
[guide d'installation de pyenv](https://github.com/pyenv/pyenv#installation).

**Installation rapide pour Ubuntu/WSL :**

```shell
# Installer les dépendances de construction
sudo apt update
sudo apt install -y build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev curl git \
libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev

# Installer pyenv
curl https://pyenv.run | bash

# Ajouter pyenv à votre configuration shell
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc

# Si vous utilisez zsh au lieu de bash, remplacez ~/.bashrc par ~/.zshrc dans les commandes ci-dessus
```

Redémarrez votre shell ou exécutez :

```shell
exec "$SHELL"
```

#### Installation de Python 3.12

```shell
# Installer Python 3.12
pyenv install 3.12

# Définir Python 3.12 comme version globale par défaut
pyenv global 3.12

# Vérifier l'installation
python --version  # Devrait afficher Python 3.12.x
```

??? tip "Installation sans pyenv"
    Si vous préférez ne pas utiliser pyenv, vous pouvez installer Python 3.12 directement. Assurez-vous simplement
    d'avoir Python 3.12 ou supérieur disponible dans votre environnement.
