#!/usr/bin/env bash
# Conventional Commits check for commit-msg.
# Format enforced (matches this machine's git conventions):
#   <type>[(scope)][!]: <description>
#   type in feat fix docs style refactor perf test build ci chore revert
#   lowercase, no trailing period, subject <= 72 chars.
# `!` requires a BREAKING CHANGE: footer. Merge/revert/fixup commits are exempt.
set -uo pipefail

file="${1:-}"
[ -z "$file" ] && file=".git/COMMIT_EDITMSG"
[ -r "$file" ] || { echo "commit-msg: cannot read '$file'" >&2; exit 1; }

# Drop comment lines and everything after git's scissors line.
msg="$(awk '/^#.*>8/ {exit} /^#/ {next} {print}' "$file")"
subject="$(printf '%s\n' "$msg" | head -n 1)"
body="$(printf '%s\n' "$msg" | tail -n +2)"

fail() { echo "commit-msg: $*" >&2; exit 1; }

[ -z "$subject" ] && fail "empty commit message"

# Let git's own commit types through untouched.
case "$subject" in
  Merge*|Revert*|fixup!*|squash!*|amend!*|WIP*) exit 0 ;;
esac

types='feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert'
header_re="^($types)(\([A-Za-z0-9._/-]+\))?(!)?: .+"

if ! printf '%s' "$subject" | grep -Eq "$header_re"; then
  fail "not a conventional commit:
    $subject
  expected: <type>[(scope)][!]: <description>
  types:    ${types//|/, }
  e.g.      fix(harness): cap needle replies at 4096 tokens"
fi

subject_len=${#subject}
[ "$subject_len" -gt 72 ] && fail "subject is ${subject_len} chars, keep it under 72:
    $subject"

desc="${subject#*: }"
case "$desc" in
  [A-Z]*) fail "description must start lowercase: ${desc%% *}" ;;
esac
[ "${desc: -1}" = "." ] && fail "no trailing period in the subject"

if printf '%s' "$subject" | grep -q '!: ' && \
   ! printf '%s' "$body" | grep -q '^BREAKING CHANGE: '; then
  fail "subject marks a breaking change (!) but there is no 'BREAKING CHANGE: ' footer"
fi

while IFS= read -r line; do
  [ "${#line}" -gt 100 ] && fail "body line is ${#line} chars, wrap at ~72:
    ${line:0:72}..."
done <<< "$body"

exit 0
