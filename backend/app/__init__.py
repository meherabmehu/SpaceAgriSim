"""SpaceAgriSim backend package."""
import pathlib
import sys

# The repository data layer (``safedata``) lives at the repository root, beside the
# ``data/`` and ``ml/`` trees it reads. Adding the root here, once, means every module in
# the package can import it without each one repeating the path arithmetic.
_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
