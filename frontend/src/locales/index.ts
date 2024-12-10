import { createI18n } from "vue-i18n";

function loadLocales() {
  const locales = import.meta.glob("./*/**/*.json");
  const messages: {
    [key: string]: { [namespace: string]: Record<string, string> };
  } = {};
  Object.keys(locales).forEach(async (key) => {
    const matched = key.match(/\.\/([A-Za-z0-9-_]+)\/([A-Za-z0-9-_]+)\.json$/i);
    if (matched && matched.length > 2) {
      const locale = matched[1];
      const namespace = matched[2];
      if (!messages[locale]) {
        messages[locale] = {};
      }
      const localeModule = (await locales[key]()) as {
        default: Record<string, string>;
      };
      messages[locale][namespace] = localeModule.default;
    }
  });
  return messages;
}

const i18n = createI18n({
  legacy: false,
  locale: "en_US",
  fallbackLocale: "en_US",
  messages: loadLocales(),
});

export default i18n;
