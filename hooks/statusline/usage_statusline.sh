#!/usr/bin/env bash
# Claude Code statusline — 3-line box-drawing layout
# Reads session JSON from stdin, displays rate limits + context usage
# No API calls, no caching, no OAuth — all data comes from stdin
set -euo pipefail

input=$(cat)
[[ -z "$input" ]] && exit 0

# --- Single jq call: extract all fields + compute expected percentages ---
eval "$(echo "$input" | jq -r '
  (now | floor) as $now |

  # Rate limits (may be absent before first API response)
  (.rate_limits.five_hour.used_percentage // -1 | floor)  as $r5  |
  (.rate_limits.five_hour.resets_at // 0)                  as $r5r |
  (.rate_limits.seven_day.used_percentage // -1 | floor)   as $r7  |
  (.rate_limits.seven_day.resets_at // 0)                  as $r7r |

  # Expected % = elapsed / window * 100, clamped 0-100
  (if $r5r > 0 then ((18000 - ($r5r - $now)) / 18000 * 100 | if . < 0 then 0 elif . > 100 then 100 else . end | floor) else -1 end) as $e5 |
  (if $r7r > 0 then ((604800 - ($r7r - $now)) / 604800 * 100 | if . < 0 then 0 elif . > 100 then 100 else . end | floor) else -1 end) as $e7 |

  # Context window
  (.context_window.used_percentage // 0 | floor) as $ctx |
  (.context_window.current_usage.input_tokens // 0) as $tok |

  # Cost + duration
  (.cost.total_cost_usd // 0) as $cost |
  ((.cost.total_duration_ms // 0) / 60000 | floor) as $dur_min |
  (((.cost.total_duration_ms // 0) % 60000) / 1000 | floor) as $dur_sec |

  # Model shortening: claude-sonnet-4-6 -> sonnet-4.6
  (.model.id // "" | gsub("^claude-"; "") | gsub("-(?<v>[0-9]+)-(?<p>[0-9]+)$"; "-\(.v).\(.p)")) as $model |

  # Folder name (basename)
  (.workspace.current_dir // .cwd // "" | split("/") | last // "") as $folder |

  [
    "R5=\($r5)", "E5=\($e5)", "R7=\($r7)", "E7=\($e7)",
    "CTX=\($ctx)", "TOK=\($tok)",
    "COST=\($cost)", "DUR_M=\($dur_min)", "DUR_S=\($dur_sec)",
    "MODEL=\($model)", "FOLDER=\($folder)"
  ] | .[] | . + ""
')"

# --- Colors ---
G='\033[32m'; Y='\033[33m'; R='\033[31m'; C='\033[36m'; D='\033[2m'; B='\033[1m'; X='\033[0m'

# --- Bar builder: make_bar <pct> <width> -> sets BAR variable ---
make_bar() {
  local pct=$1 width=$2 filled=$(( $1 * $2 / 100 )) i=""
  [[ $filled -gt $width ]] && filled=$width
  local empty=$(( width - filled ))
  local bar="["
  for (( i=0; i<filled; i++ )); do bar+="█"; done
  for (( i=0; i<empty; i++ )); do bar+="░"; done
  BAR="${bar}]"
}

# --- Color picker: color_for <actual> <expected> -> sets CLR variable ---
color_for() {
  if [[ $1 -le $2 ]]; then CLR="$G"
  elif [[ $1 -le $(( $2 + 10 )) ]]; then CLR="$Y"
  else CLR="$R"
  fi
}

# --- Format tokens: 45200 -> "45.2k" ---
fmt_tok() {
  if [[ $1 -ge 100000 ]]; then echo "$(( $1 / 1000 ))k tok"
  elif [[ $1 -ge 1000 ]]; then
    local whole=$(( $1 / 1000 )) frac=$(( ($1 % 1000) / 100 ))
    echo "${whole}.${frac}k tok"
  else echo "$1 tok"
  fi
}

# --- Git branch (fast, ~5ms) ---
BRANCH=$(git branch --show-current 2>/dev/null || true)

# --- Format duration ---
if [[ $DUR_M -ge 60 ]]; then
  DUR_FMT="$(( DUR_M / 60 ))h$(( DUR_M % 60 ))m"
else
  DUR_FMT="${DUR_M}m${DUR_S}s"
fi

# ╔══════════════════════════════════════════════════════════╗
# ║  LINE 1: model · cost · duration                        ║
# ╚══════════════════════════════════════════════════════════╝
LINE1="${C}${B}${MODEL}${X}"
LINE1+=" ${D}·${X} ${Y}\$$(printf '%.2f' "$COST")${X}"
LINE1+=" ${D}·${X} ⏱ ${DUR_FMT}"

# ╔══════════════════════════════════════════════════════════╗
# ║  LINE 2: 5h [bar] actual/expected  7d [bar] actual/exp  ║
# ╚══════════════════════════════════════════════════════════╝
if [[ $R5 -ge 0 && $E5 -ge 0 ]]; then
  make_bar "$R5" 6; BAR5="$BAR"
  color_for "$R5" "$E5"
  PART5="5h ${BAR5} ${CLR}${R5}%${X}${D}/${E5}%${X}"
else
  PART5="5h --"
fi

if [[ $R7 -ge 0 && $E7 -ge 0 ]]; then
  make_bar "$R7" 6; BAR7="$BAR"
  color_for "$R7" "$E7"
  PART7="7d ${BAR7} ${CLR}${R7}%${X}${D}/${E7}%${X}"
else
  PART7="7d --"
fi

LINE2="${PART5}  ${PART7}"

# ╔══════════════════════════════════════════════════════════╗
# ║  LINE 3: ctx [wide bar] pct% · tokens                   ║
# ╚══════════════════════════════════════════════════════════╝
make_bar "$CTX" 20; BAR_CTX="$BAR"
if [[ $CTX -ge 90 ]]; then CTX_CLR="$R"
elif [[ $CTX -ge 70 ]]; then CTX_CLR="$Y"
else CTX_CLR="$G"
fi

TOK_FMT=$(fmt_tok "$TOK")
LINE3="ctx ${CTX_CLR}${BAR_CTX}${X} ${CTX}% ${D}·${X} ${TOK_FMT}"

# ╔══════════════════════════════════════════════════════════╗
# ║  LINE 4: folder · branch                                ║
# ╚══════════════════════════════════════════════════════════╝
LINE4=""
[[ -n "$FOLDER" ]] && LINE4+="📁 ${FOLDER}"
[[ -n "$BRANCH" ]] && LINE4+=" ${D}·${X} ⎇ ${BRANCH}"

# --- Output with box-drawing (echo -e per line, per docs) ---
echo -e "┌ ${LINE1}"
echo -e "├ ${LINE2}"
echo -e "├ ${LINE3}"
echo -e "└ ${LINE4}"
