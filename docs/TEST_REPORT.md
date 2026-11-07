# Test report

Last release verification (2026-11-07):

| Check | Result |
| --- | --- |
| Backend pytest suite | 97 passed (2 upstream deprecation warnings) |
| Frontend lint | passed |
| Type checking | passed |
| Production Vite build | passed |
| Playwright responsive workflows | 15 passed across desktop, tablet and mobile (5 per profile; mobile split into two command runs due execution-window limit) |
| Python dependency audit | no known vulnerabilities found |
| npm audit | 0 known vulnerabilities after dependency remediation |
| Docker Compose configuration | passed; local Docker daemon was unavailable for an image runtime test |

Browser coverage includes keyboard/sidebar navigation, mission controls, comparison, laboratory, dataset explorer, advisors, reports and the accessible 3D fallback/control path. The Phase 2 frontend build lazy-loads workspace modules; the main bundle is 606.11 kB minified. The WebGL scene remains a 922.21 kB follow-up performance item.

