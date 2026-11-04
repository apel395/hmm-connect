# Roboto typography

Roboto is self-hosted from `public/fonts`; the app and browser print templates do
not request Google Fonts. Normal and italic variable WOFF2 assets cover weights
100–900 for Latin/Indonesian text; other scripts retain the system fallback.
Font files are distributed under their included SIL Open Font License, sourced
from `@fontsource-variable/roboto` 5.3.0 (Roboto Project authors).

`src/styles/typography.css` defines the faces and shared sans stack. Tailwind's
`font-sans`, inherited forms, tables and dialogs use Roboto. Explicit browser-print
font declarations and the standalone Inventory print document use Roboto too.
Numeric tabular styling, sizes, values, document dimensions and pagination rules
are retained. The purchasing vector-PDF generator retains its existing embedded
font behavior; it does not render browser CSS.

CI verifies local font requests, regular/medium/bold/italic loading, form/table/
dialog inheritance, tabular numbers, mobile width and Roboto embedded by browser
PDF printing. No migration or accounting changes.
