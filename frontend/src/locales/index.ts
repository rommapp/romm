import { createI18n } from "vue-i18n";

type NamespacedMessages = Record<string, Record<string, string>>;

const localeModules = import.meta.glob<{ default: Record<string, string> }>(
  "./*/**/*.json",
);

const i18n = createI18n({
  legacy: false,
  locale: "en_US",
  fallbackLocale: "en_US",
  messages: {},
  pluralRules: {
    cs_CZ(choice: number) {
      if (choice === 0) return 0;
      if (choice === 1) return 1;
      return choice >= 2 && choice <= 4 ? 2 : 3;
    },
  },
});

// Each namespace is its own chunk, so messages only land a tick or two after
// this module evaluates. Bootstrap awaits this before installing the router:
// the navigation guard translates the route title on the very first
// navigation, and without messages it would write the raw key to the tab.
export const localesReady = (async () => {
  const messages: Record<string, NamespacedMessages> = {};

  await Promise.all(
    Object.entries(localeModules).map(async ([path, load]) => {
      const matched = path.match(
        /\.\/([A-Za-z0-9-_]+)\/([A-Za-z0-9-_]+)\.json$/i,
      );
      if (!matched) return;

      const [, locale, namespace] = matched;
      try {
        const localeModule = await load();
        messages[locale] ??= {};
        messages[locale][namespace] = localeModule.default;
      } catch (error) {
        // A namespace that fails to load (stale chunk after a redeploy) must
        // not hold up the app: the rest of the UI still translates, and the
        // missing keys fall back to their key names.
        console.error(`Error loading locale messages for ${path}: `, error);
      }
    }),
  );

  Object.entries(messages).forEach(([locale, localeMessages]) => {
    i18n.global.setLocaleMessage(locale, localeMessages);
  });
})();

export default i18n;
