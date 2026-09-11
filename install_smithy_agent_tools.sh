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

install -d -m 0755 "${PREFIX}" "${CONF_DIR}" "${TOOLS_DIR}"
for f in ashfall_store.py smithy.py smithy_agent_runtime.py cosmic_smithy_tool.py; do
  install -m 0755 "${ROOT}/${f}" "${PREFIX}/${f}"
done

ln -sfn "${PREFIX}/cosmic_smithy_tool.py" "${BIN}"

# Preserve an existing configuration. The runtime itself also searches the
# canonical system store plus per-user AshFall stores, so installation does
# not require knowing which account owns the current evidence stream.
if [[ ! -f "${CONF}" ]]; then
  cat > "${CONF}" <<'EOF'
# Smithy agent-tool configuration.
# Override these paths only when the deployment uses a non-standard store.
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

# Give the existing service account a standard environment hook without
# replacing its service definition. systemd services can opt in via a drop-in
# later; the per-user CLI remains usable immediately.
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
  "Config:    ${CONF}" \
  "" \
  "Agent discovery:" \
  "  sudo ${BIN} available --agent jarvis" \
  "" \
  "Agent use (CPU):" \
  "  sudo ${BIN} use --agent aaron --model latest --accelerator cpu --reason 'evaluate current system state'" \
  "" \
  "Agent use (NPU auto):" \
  "  sudo ${BIN} use --agent aaron --model latest --accelerator auto --reason 'accelerated evaluation of current system state'" \
  "" \
  "No cosmic-agent-core replacement, host mutation, or NPU frequency control was installed."
