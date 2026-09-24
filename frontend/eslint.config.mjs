import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";

export default defineConfig([
  ...nextVitals,
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
  {
    rules: {
      // Standard "fetch on mount" data-loading pattern trips this rule even
      // though the setState calls happen asynchronously inside a .then/.catch,
      // not synchronously during the effect body.
      "react-hooks/set-state-in-effect": "off",
    },
  },
]);
