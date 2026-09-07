import { watch } from "vue";
import { createI18n } from "vue-i18n";

type LocaleModule = { default: Record<string, string> };

const FALLBACK_LOCALE = "en_US";

// Written by the language selector via `useLocalStorage`, so it holds the
// raw locale name.
const STORED_LOCALE_KEY = "settings.locale";

const localeModules = import.meta.glob<LocaleModule>("./*/**/*.json");

const modulesByLocale = new Map<
  string,
  Map<string, () => Promise<LocaleModule>>
>();
for (const [path, load] of Object.entries(localeModules)) {
  const matched = path.match(/\.\/([A-Za-z0-9-_]+)\/([A-Za-z0-9-_]+)\.json$/i);
  if (!matched) continue;

  const [, locale, namespace] = matched;
  if (!modulesByLocale.has(locale)) modulesByLocale.set(locale, new Map());
  modulesByLocale.get(locale)?.set(namespace, load);
}

const i18n = createI18n({
  legacy: false,
  locale: FALLBACK_LOCALE,
  fallbackLocale: FALLBACK_LOCALE,
  messages: {},
  pluralRules: {
    cs_CZ(choice: number) {
      if (choice === 0) return 0;
      if (choice === 1) return 1;
      return choice >= 2 && choice <= 4 ? 2 : 3;
    },
  },
});

const pendingLocales = new Map<string, Promise<void>>();

// Fetches every namespace of a language and registers them as one message
// bundle. Memoized, so repeated calls (a language toggled back and forth)
// reuse the first load.
export function loadLocale(locale: string): Promise<void> {
  const pending = pendingLocales.get(locale);
  if (pending) return pending;

  const namespaces = modulesByLocale.get(locale);
  if (!namespaces) return Promise.resolve();

  const loading = (async () => {
    const messages: Record<string, Record<string, string>> = {};

    await Promise.all(
      [...namespaces].map(async ([namespace, load]) => {
        try {
          messages[namespace] = (await load()).default;
        } catch (error) {
          // A namespace that fails to load (a stale chunk after a redeploy)
          // must not hold up the app: the rest of the UI still translates,
          // and the missing keys fall back to their key names.
          console.error(
            `Error loading ${locale}/${namespace} messages:`,
            error,
          );
        }
      }),
    );

    i18n.global.setLocaleMessage(locale, messages);
  })();

  pendingLocales.set(locale, loading);
  return loading;
}

// Namespaces are separate chunks, so messages only land a tick or two after
// this module evaluates. Bootstrap awaits the two bundles the first paint can
// need before installing the router: the navigation guard translates the
// route title on the very first navigation, and without messages it would
// write the raw key to the tab. Other languages load when switched to.
export const localesReady = Promise.all([
  loadLocale(FALLBACK_LOCALE),
  loadLocale(localStorage.getItem(STORED_LOCALE_KEY) ?? FALLBACK_LOCALE),
]);

watch(i18n.global.locale, (locale) => {
  void loadLocale(locale);
});

export default i18n;
