#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 <remote-url> [branch] [commit-message]

Examples:
  $0 https://github.com/HP04Harsh/infraGenie.git main "Prepare repo for push"

This script will:
  - verify this is a git repo
  - show status
  - stage all changes and commit (if any)
  - add or update remote `origin`
  - push the specified branch and set upstream

You will be prompted before destructive actions.
EOF
  exit 1
}

if [ "$#" -lt 1 ]; then
  usage
fi

REMOTE_URL=$1
BRANCH=${2:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)}
COMMIT_MSG=${3:-"chore: commit before pushing to ${REMOTE_URL} (${BRANCH})"}

if ! command -v git >/dev/null 2>&1; then
  echo "git is not installed. Install git and retry." >&2
  exit 2
fi

if [ ! -d .git ]; then
  echo "This directory does not appear to be a git repository. Initialize first with: git init" >&2
  exit 3
fi

echo "Repository detected. Current branch: ${BRANCH}"
echo

git status --porcelain=2 --branch

echo
read -p "Stage all changes and create a commit (if needed)? [y/N] " answer
case "$answer" in
  [Yy]* ) ;;
  * ) echo "Aborting per user choice."; exit 0 ;;
esac

# Stage and commit
if git diff --quiet && git diff --cached --quiet; then
  echo "No changes to commit."
else
  git add -A
  if git commit -m "$COMMIT_MSG"; then
    echo "Committed changes: $COMMIT_MSG"
  else
    echo "Nothing to commit (maybe identical index)."
  fi
fi

# Configure remote
if git remote get-url origin >/dev/null 2>&1; then
  echo "Remote 'origin' exists: $(git remote get-url origin)"
  read -p "Replace remote 'origin' with ${REMOTE_URL}? [y/N] " rep
  case "$rep" in
    [Yy]* ) git remote remove origin; git remote add origin "$REMOTE_URL" ;;
    * ) echo "Keeping existing remote." ;;
  esac
else
  git remote add origin "$REMOTE_URL"
fi

# Push
echo "Pushing branch ${BRANCH} to origin..."
if git push -u origin "${BRANCH}"; then
  echo "Push successful."
  git ls-remote --heads origin "${BRANCH}"
else
  echo "Push failed. Check your credentials and remote URL." >&2
  exit 4
fi
