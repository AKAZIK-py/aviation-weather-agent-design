#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"
LOG_SCRIPT="$ROOT/scripts/hooks/log_operation.sh"
MODE="print"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --commit)
      MODE="commit"
      shift
      ;;
    --print)
      MODE="print"
      shift
      ;;
    *)
      echo "未知参数: $1" >&2
      exit 1
      ;;
  esac
done

if git diff --cached --quiet; then
  echo "没有已暂存变更，无法生成 commit message。" >&2
  exit 1
fi

CHANGED_FILES="$(git diff --cached --name-only | paste -sd ', ' -)"
DIFF_STAT="$(git diff --cached --stat --no-color)"
DIFF_BODY="$(git diff --cached --no-color --unified=1 | sed -n '1,400p')"
PROMPT=$(cat <<'PROMPT'
You are generating a git commit message for a Python aviation weather agent repository.
Return only a Conventional Commit message.
Rules:
- First line: <type>: <summary>
- summary <= 72 chars
- Add a blank line and 1-4 bullet points only if they add real value
- Prefer feat/fix/refactor/test/chore/docs
- Mention tests only when relevant
- Do not wrap in markdown fences
PROMPT
)

MESSAGE=""
if [[ "${AUTO_COMMIT_USE_LLM:-1}" != "0" ]] && command -v claude >/dev/null 2>&1; then
  set +e
  MESSAGE="$(printf '%s\n\nChanged files:\n%s\n\nDiff stat:\n%s\n\nDiff:\n%s\n' "$PROMPT" "$CHANGED_FILES" "$DIFF_STAT" "$DIFF_BODY" | claude -p 2>/dev/null | sed '/^[[:space:]]*$/N;/^\n$/D')"
  CLAUDE_STATUS=$?
  set -e
  if [[ $CLAUDE_STATUS -ne 0 ]]; then
    MESSAGE=""
  fi
fi

if [[ -z "$MESSAGE" ]]; then
  FIRST_FILE="$(git diff --cached --name-only | head -n 1)"
  FILE_COUNT="$(git diff --cached --name-only | wc -l | tr -d ' ')"
  if [[ "$FILE_COUNT" == "1" ]]; then
    MESSAGE="chore: update ${FIRST_FILE}"
  else
    MESSAGE="chore: update ${FILE_COUNT} files"
  fi
fi

if [[ "$MODE" == "print" ]]; then
  printf '%s\n' "$MESSAGE"
  "$LOG_SCRIPT" --hook auto-commit --tool git --files "$CHANGED_FILES" --result success --detail "$MESSAGE"
  exit 0
fi

SUBJECT="$(printf '%s' "$MESSAGE" | sed -n '1p')"
BODY="$(printf '%s' "$MESSAGE" | sed '1d')"

if [[ -n "${BODY//[$'\t\r\n ']/}" ]]; then
  git commit -m "$SUBJECT" -m "$BODY"
else
  git commit -m "$SUBJECT"
fi

"$LOG_SCRIPT" --hook auto-commit --tool git --files "$CHANGED_FILES" --result success --detail "$SUBJECT"
