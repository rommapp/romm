import { createI18n } from "vue-i18n";

function loadLocales() {
  const locales = import.meta.globEager("./*/**/*.json");
  const messages: {
    [key: string]: { [namespace: string]: Record<string, string> };
  } = {};
  Object.keys(locales).forEach((key) => {
    const matched = key.match(/\.\/([A-Za-z0-9-_]+)\/([A-Za-z0-9-_]+)\.json$/i);
    if (matched && matched.length > 2) {
      const locale = matched[1];
      const namespace = matched[2];
      if (!messages[locale]) {
        messages[locale] = {};
      }
      messages[locale][namespace] = locales[key].default;
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
