# Mila Agent — one container: Claude Code + the Mila kit (skills, hooks, launcher) + the mila-telegram plugin.
# Build context = the repository root:  docker build -f docker/Dockerfile .  (the root Dockerfile is the same file:
# Railway and other «deploy from GitHub» panels look for ./Dockerfile; test_docker_files checks the two stay equal)
# Same shape as the MILAGPT fleet image (companion-run.sh): receiver daemon + feeder + a Claude Code session in tmux.
# Nothing secret is baked in: the bot token and the Claude login come from environment variables at run time.
FROM node:22-bookworm-slim

ARG CLAUDE_CODE_VERSION=2.1.305   # the version README says Mila is tested on; raise both together
ARG BUN_VERSION=1.2.21
ARG PLUGIN_REPO=https://github.com/shakhruz/mila-telegram.git
# The plugin is pinned to a reviewed commit: a push to the plugin's main does not change this image until the pin moves here.
ARG PLUGIN_REF=817b994674f0c72e47ddecfa4aaba2c8793be399

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates curl git unzip python3 python3-yaml tmux tini procps jq ffmpeg fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*
RUN npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
 && curl -fsSL https://bun.sh/install | BUN_INSTALL=/usr/local bash -s "bun-v${BUN_VERSION}" \
 && bun --version && claude --version

# The plugin with its dependencies in the image (the start does not need the network), and a local marketplace for it.
RUN git clone "${PLUGIN_REPO}" /opt/mila/plugin/mila-telegram && git -C /opt/mila/plugin/mila-telegram checkout -q "${PLUGIN_REF}" \
 && cd /opt/mila/plugin/mila-telegram && bun install --frozen-lockfile --no-summary \
 && mkdir -p /opt/mila/marketplace/.claude-plugin && ln -s /opt/mila/plugin/mila-telegram /opt/mila/marketplace/mila-telegram \
 && printf '{"name":"mila-local","owner":{"name":"Mila"},"plugins":[{"name":"mila-telegram","source":"./mila-telegram","description":"Mila Telegram channel"}]}' \
      > /opt/mila/marketplace/.claude-plugin/marketplace.json

RUN mkdir -p /var/lib/mila/home && chmod 755 /var/lib/mila && ln -s /var/lib/mila/home /home/agent \
 && useradd -M -d /var/lib/mila/home -u 1001 -s /bin/bash agent && chown agent:agent /var/lib/mila/home \
 && useradd -M -u 1002 -d /nonexistent -s /usr/sbin/nologin mila-keys \
 && useradd -M -u 1003 -d /nonexistent -s /usr/sbin/nologin -G agent mila-io \
 && groupadd -g 1004 mila-guest && useradd -M -u 1004 -g mila-guest -d /nonexistent -s /usr/sbin/nologin mila-guest \
 && usermod -aG mila-guest mila-io
COPY . /opt/mila/kit
COPY docker/entrypoint.sh docker/healthcheck.sh docker/claude_login.py docker/birth_claim.py docker/token_page.py docker/key_page.py docker/mila_keyd.py docker/mila_lane.py docker/io_perms.py docker/mila_state.py docker/mila-face.webp /usr/local/bin/
RUN chmod 755 /usr/local/bin/entrypoint.sh /usr/local/bin/healthcheck.sh /usr/local/bin/claude_login.py /usr/local/bin/birth_claim.py /usr/local/bin/token_page.py /usr/local/bin/key_page.py /usr/local/bin/mila_keyd.py /usr/local/bin/mila_lane.py /usr/local/bin/io_perms.py /usr/local/bin/mila_state.py /opt/mila/kit/install/transcribe-voice.sh \
 && chown -R agent:agent /opt/mila/plugin /opt/mila/marketplace

ENV HOME=/var/lib/mila/home MILA_KIT=/opt/mila/kit MILA_STATE=data:/var/lib/mila \
    TELEGRAM_STATE_DIR=/var/lib/mila/home/.claude/channels/telegram \
    DISABLE_AUTOUPDATER=1 DISABLE_TELEMETRY=1 CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1

# Starts as root only to give the home volume to agent (Railway and some panels mount volumes as root),
# then entrypoint drops to agent (uid 1001) with setpriv before anything else runs. Claude Code never runs as root.
# PORT: the one-field token page listens here only while there is no bot token (Railway asks for the port when you generate a
# domain and suggests 8080). docker-compose sets PORT empty — there the token comes from a variable, no page.
ENV PORT=8080
EXPOSE 8080
WORKDIR /var/lib/mila/home
# No VOLUME line: Railway refuses Dockerfiles with VOLUME. ONE volume at /var/lib/mila (compose: mila-home; Railway: Attach Volume → /var/lib/mila):
# home/ (agent), keys/ (mila-keys), io/ (mila-io) — the volume's root belongs to root, so the session cannot swap keys/ or io/.
# /home/agent is a link to the home for old absolute paths; a volume still mounted at /home/agent lands on the home only — it runs,
# and the owner gets a card to move the mount (keys/ and io/ would live in the container's layer).
HEALTHCHECK --interval=60s --timeout=10s --start-period=180s --retries=3 CMD ["/usr/local/bin/healthcheck.sh"]
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
