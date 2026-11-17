# Frontend

The Vue 3 web UI: views, router, composables and plugins, talking to the backend over /api and /ws with types generated from its OpenAPI schema.

## folded

- e2e/support: Playwright helpers the e2e specs share
- scripts: build-time Node scripts (tokens, icons, checks)
- src/composables: shared composables the views and components call
- src/locales: the locale loader and its check scripts beside the translation files
- src/plugins: app plugin registration (router, i18n, markdown, theme)
- src/test-utils: vitest helpers
- src/types: shared type declarations
- src/views/Player: the in-browser player view and its emulator glue
