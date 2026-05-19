// ESLint v10 flat config for the Extendable Timer Lovelace card.
// Plugin set mirrors the JS-applicable subset of home-assistant/frontend's
// ESLint config (TypeScript-only plugins are deliberately omitted).

import js from "@eslint/js";
import { fixupPluginRules } from "@eslint/compat";
import lit from "eslint-plugin-lit";
import wc from "eslint-plugin-wc";
import importPluginRaw from "eslint-plugin-import";
import prettier from "eslint-plugin-prettier";
import prettierConfig from "eslint-config-prettier";

// eslint-plugin-import's peerDependencies stop at eslint ^9; the compat shim
// lets it run under eslint 10 cleanly.
const importPlugin = fixupPluginRules(importPluginRaw);

export default [
  js.configs.recommended,
  {
    files: ["**/*.js"],
    languageOptions: {
      ecmaVersion: 2024,
      sourceType: "module",
      globals: {
        // Browser environment for the Lovelace card.
        window: "readonly",
        document: "readonly",
        customElements: "readonly",
        HTMLElement: "readonly",
        console: "readonly",
        fetch: "readonly",
        ResizeObserver: "readonly",
        requestAnimationFrame: "readonly",
        CustomEvent: "readonly",
        Node: "readonly",
        Event: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        history: "readonly",
        WeakSet: "readonly",
      },
    },
    plugins: {
      lit,
      wc,
      import: importPlugin,
      prettier,
    },
    rules: {
      ...lit.configs.recommended.rules,
      ...wc.configs.recommended.rules,
      "import/no-unresolved": "off", // card imports Lit from a CDN URL at runtime
      "import/order": ["warn", { "newlines-between": "always" }],
      "prettier/prettier": "error",
    },
  },
  prettierConfig, // disables ESLint stylistic rules that conflict with Prettier
];
