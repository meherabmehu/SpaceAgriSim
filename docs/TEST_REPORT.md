# Test report

Last release verification (2026-11-06):

| Check | Result |
| --- | --- |
| Backend pytest suite | 95 passed (2 upstream deprecation warnings) |
| Frontend lint | passed |
| Type checking | passed |
| Production Vite build | passed |
| Playwright responsive workflows | 15 passed across desktop, tablet and mobile |
| Python dependency audit | no known vulnerabilities found |
| npm audit | 0 known vulnerabilities after dependency remediation |
| Docker Compose configuration | passed; local Docker daemon was unavailable for an image runtime test |

Browser coverage includes keyboard/sidebar navigation, mission controls, comparison, laboratory, dataset explorer, advisors, reports and the accessible 3D fallback/control path. The visual build emits a bundle-size advisory for the WebGL scene; it is a performance follow-up, not a failed build.

