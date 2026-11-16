#!/usr/bin/env bash
# Creates or updates the single preview comment on a pull request.
# Usage: preview_comment.sh <pr-number> <body>   (needs GH_TOKEN and GITHUB_REPOSITORY)

set -o errexit
set -o nounset
set -o pipefail

pr="$1"
marker="<!-- romm-preview -->"
body="${marker}
$2"

comment_id=$(gh api "repos/${GITHUB_REPOSITORY}/issues/${pr}/comments" --paginate \
	--jq ".[] | select(.user.login == \"github-actions[bot]\" and (.body | startswith(\"${marker}\"))) | .id" |
	head -n 1)

if [[ -n ${comment_id} ]]; then
	gh api -X PATCH "repos/${GITHUB_REPOSITORY}/issues/comments/${comment_id}" -f body="${body}" >/dev/null
else
	gh api "repos/${GITHUB_REPOSITORY}/issues/${pr}/comments" -f body="${body}" >/dev/null
fi
