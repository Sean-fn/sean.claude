#!/usr/bin/env bash
# agent365 MCP headersHelper.
# Usage: agent365-auth.sh <resource-url>
# Emits JSON: {"Authorization":"Bearer <jwt>"}
#
# Fetches a delegated Entra token for the given per-server agent365 resource
# via the Azure CLI's cached sign-in. Claude Code's MCP http transport pipes
# the stdout JSON into every outbound request header.
#
# Prereqs:
#   - az CLI installed
#   - `az login` completed once against the tenant that owns the agent365
#     environment (v-seanfang@microsoft.com / 72f988bf-...)
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <resource-url>" >&2
  exit 2
fi

resource="$1"

# --query accessToken -o tsv prints the raw JWT, nothing else.
token=$(az account get-access-token --resource "$resource" --query accessToken -o tsv)

# printf, not echo, so we don't append a trailing newline that some header
# parsers will turn into an invalid header value.
printf '{"Authorization":"Bearer %s"}' "$token"
