# Source this file from Bash. Functions intentionally avoid changing caller shell options.

_howler_wt_valid_name() {
	[[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$ ]]
}

_howler_wt_repo_root() {
	local common_dir
	common_dir=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || {
		printf 'Not inside a Git worktree.\n' >&2
		return 1
	}
	dirname "$common_dir"
}

_howler_wt_require_ignored_root() {
	local repo_root=$1
	mkdir -p "$repo_root/.worktrees" || return 1
	if ! git -C "$repo_root" check-ignore -q -- .worktrees/probe; then
		printf '.worktrees/ is not ignored; add it to .gitignore before creating worktrees.\n' >&2
		return 1
	fi
}

_howler_wt_read_base() {
	local repo_root=$1
	local task=$2
	local base_file="$repo_root/.worktrees/$task.base"
	local base_sha

	if [[ ! -f "$base_file" ]]; then
		printf 'Task base is not initialized; run orchestrate_start %s HEAD first.\n' "$task" >&2
		return 1
	fi
	IFS= read -r base_sha <"$base_file" || return 1
	if [[ ! "$base_sha" =~ ^[0-9a-f]{40,64}$ ]] || ! git -C "$repo_root" cat-file -e "$base_sha^{commit}" 2>/dev/null; then
		printf 'Invalid or unavailable base commit recorded in %s.\n' "$base_file" >&2
		return 1
	fi
	printf '%s\n' "$base_sha"
}

_howler_wt_require_unused() {
	local repo_root=$1
	local branch=$2
	local path=$3

	if git -C "$repo_root" show-ref --verify --quiet "refs/heads/$branch"; then
		printf 'Branch already exists: %s\n' "$branch" >&2
		return 1
	fi
	if [[ -e "$path" ]]; then
		printf 'Worktree path already exists: %s\n' "$path" >&2
		return 1
	fi
}

_howler_wt_validate_scope() {
	local target=$1
	local base_sha=$2
	local manifest="$target/TASK.md"
	local allowed_csv forbidden_csv file pattern allowed_match forbidden_match
	local -a allowed_patterns=() forbidden_patterns=()

	allowed_csv=$(sed -n 's/^- \*\*Exclusive Allowed Path Patterns:\*\* //p' "$manifest")
	forbidden_csv=$(sed -n 's/^- \*\*Forbidden Path Patterns:\*\* //p' "$manifest")
	if [[ -z "$allowed_csv" ]]; then
		printf 'Task manifest must declare exclusive allowed path globs.\n' >&2
		return 1
	fi
	IFS=',' read -r -a allowed_patterns <<<"$allowed_csv"
	IFS=',' read -r -a forbidden_patterns <<<"$forbidden_csv"
	for pattern in "${allowed_patterns[@]}"; do
		pattern="${pattern#"${pattern%%[![:space:]]*}"}"
		pattern="${pattern%"${pattern##*[![:space:]]}"}"
		if [[ "$pattern" == '*' || "$pattern" == '**' ]]; then
			printf 'Refusing an unrestricted allowed path pattern in %s.\n' "$manifest" >&2
			return 1
		fi
	done
	while IFS= read -r -d '' file; do
		allowed_match=false
		for pattern in "${allowed_patterns[@]}"; do
			pattern="${pattern#"${pattern%%[![:space:]]*}"}"
			pattern="${pattern%"${pattern##*[![:space:]]}"}"
			if [[ -n "$pattern" && "$file" == $pattern ]]; then
				allowed_match=true
				break
			fi
		done
		if [[ "$allowed_match" != true ]]; then
			printf 'Changed path is outside this task manifest allowed set: %s\n' "$file" >&2
			return 1
		fi
		for pattern in "${forbidden_patterns[@]}"; do
			pattern="${pattern#"${pattern%%[![:space:]]*}"}"
			pattern="${pattern%"${pattern##*[![:space:]]}"}"
			if [[ -n "$pattern" && "$file" == $pattern ]]; then
				printf 'Changed path matches this task manifest forbidden set: %s\n' "$file" >&2
				return 1
			fi
		done
	done < <(git -C "$target" diff --name-only --no-renames -z "$base_sha..HEAD")
}

orchestrate_start() {
	if [[ $# -ne 2 ]] || ! _howler_wt_valid_name "${1-}"; then
		printf 'Usage: orchestrate_start <task-name> <base-ref>\n' >&2
		return 2
	fi

	local task=$1
	local base_ref=$2
	local repo_root current_head base_sha base_file
	repo_root=$(_howler_wt_repo_root) || return 1
	_howler_wt_require_ignored_root "$repo_root" || return 1
	current_head=$(git -C "$repo_root" rev-parse --verify HEAD) || return 1
	base_sha=$(git -C "$repo_root" rev-parse --verify "$base_ref^{commit}") || {
		printf 'Base ref does not resolve to a commit: %s\n' "$base_ref" >&2
		return 1
	}
	if [[ "$base_sha" != "$current_head" ]]; then
		printf 'The base must be the primary working tree HEAD (%s), not %s.\n' "$current_head" "$base_sha" >&2
		return 1
	fi

	base_file="$repo_root/.worktrees/$task.base"
	if [[ -e "$base_file" ]]; then
		if [[ "$(cat "$base_file")" == "$base_sha" ]]; then
			printf 'Task %s is already pinned to %s.\n' "$task" "$base_sha"
			return 0
		fi
		printf 'Task base file already exists with a different commit: %s\n' "$base_file" >&2
		return 1
	fi
	printf '%s\n' "$base_sha" >"$base_file" || return 1
	printf 'Pinned task %s to primary HEAD %s; the primary branch was not changed.\n' "$task" "$base_sha"
}

orchestrate_spawn() {
	if [[ $# -ne 6 ]] || ! _howler_wt_valid_name "${1-}" || ! _howler_wt_valid_name "${2-}"; then
		printf 'Usage: orchestrate_spawn <task-name> <role> <allowed-globs> <forbidden-globs> <contract> <verification-command>\n' >&2
		return 2
	fi

	local task=$1
	local role=$2
	local allowed_paths=$3
	local forbidden_paths=$4
	local contract=$5
	local verification_command=$6
	local repo_root base_sha agent_branch target manifest
	repo_root=$(_howler_wt_repo_root) || return 1
	_howler_wt_require_ignored_root "$repo_root" || return 1
	base_sha=$(_howler_wt_read_base "$repo_root" "$task") || return 1
	agent_branch="agent/$task/$role"
	target="$repo_root/.worktrees/$task-$role"
	manifest="$target/TASK.md"
	_howler_wt_require_unused "$repo_root" "$agent_branch" "$target" || return 1

	git -C "$repo_root" worktree add -b "$agent_branch" "$target" "$base_sha" || return 1
	{
		printf '# TASK.md: %s\n\n' "$role"
		printf -- '- **Task ID:** %s-%s\n' "$task" "$role"
		printf -- '- **Base Commit:** `%s`\n' "$base_sha"
		printf -- '- **Target Worktree:** `.worktrees/%s-%s`\n' "$task" "$role"
		printf -- '- **Exclusive Allowed Path Patterns:** %s\n' "$allowed_paths"
		printf -- '- **Forbidden Path Patterns:** %s\n' "$forbidden_paths"
		printf -- '- **Contract Interface:** %s\n' "$contract"
		printf -- '- **Verification Command:** `%s`\n' "$verification_command"
	} >"$manifest" || {
		printf 'Could not write task manifest; worktree retained at %s for inspection.\n' "$target" >&2
		return 1
	}

	printf 'Created %s on %s from %s with manifest %s\n' "$target" "$agent_branch" "$base_sha" "$manifest"
}

orchestrate_patch() {
	if [[ $# -ne 3 ]] || ! _howler_wt_valid_name "${1-}" || ! _howler_wt_valid_name "${2-}" || [[ "${3-}" != --review-approved ]]; then
		printf 'Usage: orchestrate_patch <task-name> <role> --review-approved\n' >&2
		return 2
	fi

	local task=$1
	local role=$2
	local repo_root base_sha agent_branch target manifest worktree_patch patch_file current_branch status
	repo_root=$(_howler_wt_repo_root) || return 1
	base_sha=$(_howler_wt_read_base "$repo_root" "$task") || return 1
	agent_branch="agent/$task/$role"
	target="$repo_root/.worktrees/$task-$role"
	manifest="$target/TASK.md"
	worktree_patch="$target/.agent.patch"
	patch_file="$repo_root/.worktrees/$task-$role.patch"

	if [[ ! -d "$target" || ! -f "$manifest" ]]; then
		printf 'Agent worktree or its task manifest is missing: %s\n' "$target" >&2
		return 1
	fi
	current_branch=$(git -C "$target" branch --show-current) || return 1
	if [[ "$current_branch" != "$agent_branch" ]]; then
		printf 'Expected %s checked out in %s; found %s.\n' "$agent_branch" "$target" "$current_branch" >&2
		return 1
	fi
	if ! git -C "$target" merge-base --is-ancestor "$base_sha" HEAD; then
		printf 'Agent branch no longer descends from pinned base %s.\n' "$base_sha" >&2
		return 1
	fi
	status=$(git -C "$target" status --porcelain --untracked-files=all) || return 1
	if git -C "$target" ls-files --error-unmatch -- TASK.md >/dev/null 2>&1; then
		printf 'Refusing patch generation: TASK.md must remain an uncommitted coordination manifest.\n' >&2
		return 1
	fi
	if [[ "$status" != '?? TASK.md' ]] &&
		! { [[ -z "$status" ]] && git -C "$target" check-ignore -q -- TASK.md; }; then
		printf 'Commit only the reviewer-approved code on the agent branch first; unexpected worktree status:\n%s\n' "$status" >&2
		return 1
	fi
	if grep -Fqx -- "- **Task ID:** $task-$role" "$manifest" && grep -Fqx -- "- **Base Commit:** \`$base_sha\`" "$manifest"; then
		:
	else
		printf 'Task manifest identity/base does not match the requested patch.\n' >&2
		return 1
	fi
	_howler_wt_validate_scope "$target" "$base_sha" || return 1
	if [[ -e "$patch_file" || -e "$worktree_patch" ]]; then
		printf 'Patch already exists; preserve/review it before generating another: %s\n' "$patch_file" >&2
		return 1
	fi
	if git -C "$target" diff --quiet "$base_sha..HEAD"; then
		printf 'No committed change to package for %s.\n' "$agent_branch" >&2
		return 1
	fi
	git -C "$target" diff --binary "$base_sha..HEAD" >"$worktree_patch" || return 1
	if [[ ! -s "$worktree_patch" ]]; then
		rm -- "$worktree_patch"
		printf 'Generated patch is empty; no patch retained.\n' >&2
		return 1
	fi
	cp -- "$worktree_patch" "$patch_file" || return 1
	printf 'Generated reviewed patch %s from %s (base %s).\n' "$patch_file" "$agent_branch" "$base_sha"
}

orchestrate_apply() {
	if [[ $# -ne 3 ]] || ! _howler_wt_valid_name "${1-}" || ! _howler_wt_valid_name "${2-}" || [[ "${3-}" != --review-approved ]]; then
		printf 'Usage: orchestrate_apply <task-name> <role> --review-approved\n' >&2
		return 2
	fi

	local task=$1
	local role=$2
	local repo_root current_dir base_sha patch_file path patch_path root_path
	local -a patch_paths=() root_paths=() untracked_paths=()
	repo_root=$(_howler_wt_repo_root) || return 1
	current_dir=$(pwd -P) || return 1
	if [[ "$current_dir" != "$repo_root" ]]; then
		printf 'Run patch application from the primary repository root (%s), not a subdirectory or agent worktree.\n' "$repo_root" >&2
		return 1
	fi
	base_sha=$(_howler_wt_read_base "$repo_root" "$task") || return 1
	patch_file="$repo_root/.worktrees/$task-$role.patch"
	if [[ ! -s "$patch_file" ]]; then
		printf 'Reviewed patch is missing or empty: %s\n' "$patch_file" >&2
		return 1
	fi
	if [[ "$(git -C "$repo_root" rev-parse HEAD)" != "$base_sha" ]]; then
		printf 'Primary HEAD changed since task start; review/rebase the task against the new base before applying.\n' >&2
		return 1
	fi
	while IFS= read -r -d '' path; do patch_paths+=("$path"); done < <(
		git -C "$repo_root/.worktrees/$task-$role" diff --name-only --no-renames -z "$base_sha..HEAD"
	)
	while IFS= read -r -d '' path; do root_paths+=("$path"); done < <(
		git -C "$repo_root" diff --name-only --no-renames -z HEAD
	)
	while IFS= read -r -d '' path; do untracked_paths+=("$path"); done < <(
		git -C "$repo_root" ls-files --others --exclude-standard -z
	)
	root_paths+=("${untracked_paths[@]}")
	for patch_path in "${patch_paths[@]}"; do
		for root_path in "${root_paths[@]}"; do
			if [[ "$patch_path" == "$root_path" ]]; then
				printf 'Refusing patch: path is already modified in the primary working tree: %s\n' "$patch_path" >&2
				return 1
			fi
		done
	done
	(
		cd "$repo_root" || exit 1
		git apply --check --binary "$patch_file" || exit 1
		git apply --binary "$patch_file"
	) || {
		printf 'Patch check/application failed; primary working tree was not force-modified. Inspect and resolve in the agent worktree.\n' >&2
		return 1
	}
	printf 'Applied approved patch %s to primary working tree %s.\n' "$patch_file" "$repo_root"
}

orchestrate_teardown() {
	if [[ $# -ne 3 ]] || ! _howler_wt_valid_name "${1-}" || ! _howler_wt_valid_name "${2-}" || [[ "${3-}" != --patch-applied ]]; then
		printf 'Usage: orchestrate_teardown <task-name> <role> --patch-applied\n' >&2
		return 2
	fi

	local task=$1
	local role=$2
	local repo_root current_dir base_sha agent_branch target manifest worktree_patch patch_file status
	repo_root=$(_howler_wt_repo_root) || return 1
	base_sha=$(_howler_wt_read_base "$repo_root" "$task") || return 1
	agent_branch="agent/$task/$role"
	target="$repo_root/.worktrees/$task-$role"
	manifest="$target/TASK.md"
	worktree_patch="$target/.agent.patch"
	patch_file="$repo_root/.worktrees/$task-$role.patch"
	if [[ ! -d "$target" || ! -s "$patch_file" ]]; then
		printf 'Cannot verify applied patch; agent worktree or retained patch is missing.\n' >&2
		return 1
	fi
	current_dir=$(pwd -P) || return 1
	case "$current_dir/" in
	"$target"/*)
		printf 'Refusing teardown from inside the target worktree; change to another worktree first.\n' >&2
		return 1
		;;
	esac
	if ! git -C "$repo_root" show-ref --verify --quiet "refs/heads/$agent_branch" ||
		[[ "$(git -C "$target" branch --show-current)" != "$agent_branch" ]]; then
		printf 'Agent branch/worktree identity mismatch for %s.\n' "$agent_branch" >&2
		return 1
	fi
	if ! git -C "$target" merge-base --is-ancestor "$base_sha" HEAD; then
		printf 'Agent branch no longer descends from pinned base %s.\n' "$base_sha" >&2
		return 1
	fi
	status=$(git -C "$target" status --porcelain --untracked-files=all) || return 1
	if git -C "$target" ls-files --error-unmatch -- TASK.md >/dev/null 2>&1; then
		printf 'Refusing teardown: TASK.md is tracked instead of being a coordination manifest.\n' >&2
		return 1
	fi
	local expected_status='?? .agent.patch'
	if ! git -C "$target" check-ignore -q -- TASK.md; then
		expected_status+=$'\n?? TASK.md'
	fi
	if [[ "$status" != "$expected_status" ]] || ! grep -Fqx -- "- **Task ID:** $task-$role" "$manifest"; then
		printf 'Refusing teardown: agent worktree is not clean apart from its generated TASK.md and .agent.patch.\n%s\n' "$status" >&2
		return 1
	fi
	if ! cmp -s "$patch_file" "$worktree_patch" || ! cmp -s "$worktree_patch" <(git -C "$target" diff --binary "$base_sha..HEAD"); then
		printf 'Refusing teardown: source branch no longer matches the retained patch.\n' >&2
		return 1
	fi
	(
		cd "$repo_root" || exit 1
		git apply --check --reverse --binary "$patch_file"
	) || {
		printf 'Refusing teardown: retained patch does not reverse-check against the primary working tree.\n' >&2
		return 1
	}
	rm -- "$manifest" || return 1
	rm -- "$worktree_patch" || return 1
	git -C "$repo_root" worktree remove "$target" || return 1
	printf 'Removed clean agent worktree; retained branch %s and patch %s for recovery.\n' "$agent_branch" "$patch_file"
}
