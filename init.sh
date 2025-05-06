curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
nvm install 22.15.0
nvm use 22.15.0


pip install uv
uv venv
source .venv/bin/activate
uv sync
npm i -g npx