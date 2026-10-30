# RomM frontend

## Layout

The UI lives under `frontend/src/`. It has its own design system (tokens), primitive library (`R*` components in `src/lib/`), universal input (mouse/touch/keyboard/gamepad), and responsive system. Shared stores, services, composables, utils, locales and the router live directly under `frontend/src/`.

The `frontend-*` skills in `.claude/skills/` hold the detailed rules. **Read the relevant skill before editing v2 code.**

## Commands (`cd frontend`)

```bash
npm install                         # install (Node 24)
npm run dev                         # dev server :3000
npm run typecheck                   # vue-tsc --build: the app, the Node tooling and the e2e suite
npm run typecheck:scripts           # Node only: scripts/, eslint-plugin-romm/, tool configs, the e2e suite
npm run test                        # vitest (+ Storybook play() and a11y tests in Chromium)
npm run test:coverage               # the same, with a v8 coverage report in coverage/ (open index.html)
npm run test:e2e                    # playwright, see e2e/README.md
npm run build                       # production build
npm run generate                    # regenerate types from backend OpenAPI (backend must be running)
npm run build:tokens                # regenerate v2 tokens.css (auto on predev/prebuild)
npm run storybook                   # component library on :6006
python3 src/locales/check_i18n_locales.py   # i18n parity check
python3 src/locales/check_i18n_sorted.py    # locale keys sorted (--fix to sort)
```
