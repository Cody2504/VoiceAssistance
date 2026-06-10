import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

// Each locale is split into per-area source files. Every file contributes a
// distinct top-level key (app/nav/landing/playground/…), so a plain spread
// merges them into the single `common` namespace with no key collisions and,
// importantly, lets different areas be edited independently.
import enCommon from "./locales/en/common.json";
import enLanding from "./locales/en/landing.json";
import enMarketing from "./locales/en/marketing.json";
import enPlayground from "./locales/en/playground.json";
import enPgkit from "./locales/en/pgkit.json";
import enConsole from "./locales/en/console.json";
import enChat from "./locales/en/chat.json";
import enSettings from "./locales/en/settings.json";
import enAdmin from "./locales/en/admin.json";

import viCommon from "./locales/vi/common.json";
import viLanding from "./locales/vi/landing.json";
import viMarketing from "./locales/vi/marketing.json";
import viPlayground from "./locales/vi/playground.json";
import viPgkit from "./locales/vi/pgkit.json";
import viConsole from "./locales/vi/console.json";
import viChat from "./locales/vi/chat.json";
import viSettings from "./locales/vi/settings.json";
import viAdmin from "./locales/vi/admin.json";

const en = {
  ...enCommon,
  ...enLanding,
  ...enMarketing,
  ...enPlayground,
  ...enPgkit,
  ...enConsole,
  ...enChat,
  ...enSettings,
  ...enAdmin,
};

const vi = {
  ...viCommon,
  ...viLanding,
  ...viMarketing,
  ...viPlayground,
  ...viPgkit,
  ...viConsole,
  ...viChat,
  ...viSettings,
  ...viAdmin,
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: { en: { common: en }, vi: { common: vi } },
    fallbackLng: "en",
    defaultNS: "common",
    interpolation: { escapeValue: false },
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
      lookupLocalStorage: "i18nextLng",
    },
  });

export default i18n;
