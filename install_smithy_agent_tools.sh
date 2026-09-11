#!/usr/bin/env bash
set -euo pipefail

# Install the AshFall/Smithy model capability as a real tool available to the
# existing Cosmic agents. This intentionally does not replace or wrap the
# agents themselves and does not modify cosmic-agent-core.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="/usr/local/lib/cosmic/ashfall"
BIN="/usr/local/sbin/cosmic-agent-smithy"
CONF_DIR="/etc/cosmic"
CONF="${CONF_DIR}/smithy-agent.env"
TOOLS_DIR="/var/lib/agent-bus/tools"
MANIFEST="${TOOLS_DIR}/SMITHY.json"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo ./install_smithy_agent_tools.sh"
  exit 2
fi

for f in ashfall_store.py smithy.py smithy_agent_runtime.py cosmic_smithy_tool.py; do
  [[ -f "${ROOT}/${f}" ]] || { echo "Missing ${ROOT}/${f}" >&2; exit 3; }
done

install -d -m 0755 "${PREFIX}" "${CONF_DIR}" "${TOOLS_DIR}" "/var/lib/ashfall/smithy/models"
for f in ashfall_store.py smithy.py smithy_agent_runtime.py cosmic_smithy_tool.py; do
  install -m 0755 "${ROOT}/${f}" "${PREFIX}/${f}"
done

ln -sfn "${PREFIX}/cosmic_smithy_tool.py" "${BIN}"

# Give every real agent a stable, obvious tool endpoint while keeping one
# implementation and one shared evidence history.
for agent in jarvis aaron george leeloo; do
  ln -sfn "${BIN}" "/usr/local/sbin/${agent}-smithy"
done

# Preserve an existing configuration. The runtime searches the configured
# store plus canonical/per-user AshFall stores, so installation does not
# require replacing the existing agent services.
if [[ ! -f "${CONF}" ]]; then
  cat > "${CONF}" <<'EOF'
# Smithy agent-tool configuration.
# Optional overrides:
# ASHFALL_STORE=/var/lib/ashfall/evidence.jsonl
# SMITHY_CACHE_DIR=/var/lib/ashfall/smithy/models
# SMITHY_RKNN_DIR=/var/lib/ashfall/smithy/models
EOF
  chmod 0644 "${CONF}"
fi

cat > "${MANIFEST}" <<'EOF'
{
  "schema": "cosmic.agent.tool.v1",
  "tool": "smithy",
  "entrypoint": "/usr/local/sbin/cosmic-agent-smithy",
  "agent_entrypoints": {
    "JARVIS": "/usr/local/sbin/jarvis-smithy",
    "AARON": "/usr/local/sbin/aaron-smithy",
    "GEORGE": "/usr/local/sbin/george-smithy",
    "LEELOO": "/usr/local/sbin/leeloo-smithy"
  },
  "description": "Optional locally forged computational artifacts created by Smithy from AshFall evidence.",
  "agents": ["JARVIS", "AARON", "GEORGE", "LEELOO"],
  "selection": {
    "agent_decides": true,
    "model_decides": false,
    "accelerator_auto_prefers": "npu_when_rknn_artifact_exists"
  },
  "actions": ["available", "use"],
  "input": {
    "model": "latest|model_id",
    "accelerator": "auto|cpu|npu",
    "reason": "required",
    "observation_evidence_id": "optional"
  },
  "policy": {
    "model_is_not_agent": true,
    "mutates_host": false,
    "changes_frequency": false,
    "autonomous_control": false
  }
}
EOF
chmod 0644 "${MANIFEST}"

# Standard environment hook for future service drop-ins; it does not replace
# or modify the existing agent services.
cat > "/usr/local/sbin/smithy-agent-env" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
set -a
source /etc/cosmic/smithy-agent.env
set +a
exec "$@"
EOF
chmod 0755 /usr/local/sbin/smithy-agent-env

python3 -m py_compile \
  "${PREFIX}/ashfall_store.py" \
  "${PREFIX}/smithy.py" \
  "${PREFIX}/smithy_agent_runtime.py" \
  "${PREFIX}/cosmic_smithy_tool.py"

printf '%s\n' \
  "SMITHY AGENT TOOL INSTALLED" \
  "---------------------------" \
  "Entrypoint: ${BIN}" \
  "Manifest:  ${MANIFEST}" \
  "Per-agent endpoints: /usr/local/sbin/{jarvis,aaron,george,leeloo}-smithy" \
  "Config:    ${CONF}" \
  "" \
  "Example:" \
  "  sudo ${BIN} available --agent jarvis" \
  "  sudo ${BIN} use --agent aaron --model latest --accelerator auto --reason 'AARON-selected evaluation'" \
  "" \
  "No cosmic-agent-core replacement, host mutation, or NPU frequency control was installed."
