# Test report

Last release verification (2026-11-07):

| Check | Result |
| --- | --- |
| Backend pytest suite | 97 passed, 1 skipped optional PostgreSQL integration test (2 upstream deprecation warnings) |
| Frontend lint | passed |
| Type checking | passed |
| Production Vite build | passed |
| Playwright responsive workflows | 15 passed across desktop, tablet and mobile (5 per profile; mobile split into two command runs due execution-window limit) |
| Python runtime dependency audit | executed from `backend/requirements.txt`; developer virtualenv audit also reports upgradeable `pip`/`certifi`, which are not application requirements |
| npm production dependency audit | 0 known vulnerabilities |
| Docker Compose configuration | passed; local Docker daemon was unavailable for an image runtime test |

Browser coverage includes keyboard/sidebar navigation, mission controls, comparison, laboratory, dataset explorer, advisors, reports and the accessible 3D fallback/control path. Phase 3 also lazy-loads the greenhouse wrapper: the main bundle is 595.10 kB minified, and the 922.21 kB WebGL scene is fetched only when 3D is enabled.

