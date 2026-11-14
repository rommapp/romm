# Filesystem

Reads and writes under the library, resources and assets folders, with path validation that keeps every write inside its base folder.

## invariants

- paths stay in their base: A path built from request or sync input resolves inside its handler's base folder, unless it passes through a symlink an admin placed there.
  over: traversal, absolute, doubled-slash and dot-segment inputs to validate_path, each refused or resolved inside the base
  via: test_validate_path_never_escapes_its_base
  because: uploads, manuals, saves and sync paths are joined from caller input; a path that escapes its base lets a caller overwrite files anywhere the server can write
  crossing: user -> storage
  entrances: http api
  kinds: storage
  checklist: scoped-reads dismissed: this invariant bounds paths, not which records a read returns
  checklist: encrypted-storage dismissed: nothing confidential is encrypted at rest here
  checklist: key-rotation-compatibility dismissed: no encrypted data in scope
  checklist: input-validation declared as paths stay in their base
  checklist: revision-preservation dismissed: no revisioned records in scope
  checklist: commit-ordered-effects dismissed: no queued effects in scope
  checklist: durable-dispatch-intent dismissed: no dispatch in scope
  checklist: declared-target-coverage dismissed: no fan-out targets in scope
  checklist: completion-evidence dismissed: no completion records in scope
