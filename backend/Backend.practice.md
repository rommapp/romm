- worktree test database: A backend test run in a git worktree uses its own temporary database, never the shared romm_test.
  when: command uv run pytest
  step: set ROMM_TEST_DB_TAG to a tag unique to the worktree before running pytest
  step: select the tests affected by the change; never run the whole suite locally
  step: leave the shared romm_test alone: never stamp or downgrade it
  pitfall: a worktree on another branch migrated the shared romm_test to a revision the current branch lacked, and every test errored in setup with "Can't locate revision" (503c9b290)
  learned: 503c9b290
  because: every checkout shares romm_test, so one branch's migrations break every other branch's test run
- regenerate frontend types: A change to a backend response schema or route ships with the frontend types regenerated from the OpenAPI schema.
  when: edit backend/endpoints/responses/**/*.py | edit backend/endpoints/**/*.py adding protected_route
  step: run npm run generate in frontend with the backend running
    leaves: the changed files under frontend/src/__generated__
  step: run npm run typecheck in frontend
  pitfall: a new API field reached the UI only once the generated models were updated in the same change (212caf1a2)
  learned: 212caf1a2
  because: the backend owns the API contract; stale generated types let the frontend typecheck against a shape the API no longer returns
