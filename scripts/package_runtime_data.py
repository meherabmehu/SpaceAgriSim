"""Bundle only reviewed, small inference assets inside a Python service root."""
import sys as _sys, pathlib as _pathlib   # the repository root holds safedata/
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1]))
import safedata
import hashlib
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def package():
    destination=ROOT/'backend/scientific_data'
    sources=[]
    for name in ['dataset_manifest','download_checksums','quality_report','external_lettuce','phase2_nasa_candidates','phase9_nasa_datasets','osdr_live_status']:
        sources.append(ROOT/'data/metadata'/name)
    # Phase 19: the benchmark panel reads this artifact through the same bundle lookup as the
    # manifest. Without it the endpoint answers "artifact not present" in production while the
    # local build looks fine.
    sources.append(ROOT/'data/derived'/'bpc_benchmark')
    # et0_dataset.csv is the 2.4 MB modelling table the emulator was trained on. No application
    # module reads it - the bundle is for inference assets - and it is three quarters over the
    # size guard below, so it stays out of the service root.
    sources.extend(path for path in (ROOT/'data/processed').glob('*.csv')
                   if path.name != 'et0_dataset.csv')
    sources.extend((ROOT/'data/raw/OSD-745').glob('*TRANSFORMED.csv'))
    # Phase 15: NASA BPC measurement excerpts acquired from NTRS. The evidence corpus reads
    # these from the bundle, so leaving them out of the package empties the literature passages
    # in production while everything still passes locally.
    literature=sorted((ROOT/'data/literature').glob('*'))
    if not literature:
        raise ValueError('Phase 15 literature artifacts are missing; run acquire_ntrs_bpc_measurements.py')
    sources.extend(literature)
    # Phase 19: external-validation screening for the lettuce model (literature/ is globbed, so
    # this file travels with the corpus; the assert above keeps it from being dropped silently).
    # The artifacts directory holds files (the served artifacts and their explanations); the
    # `cards` subdirectory is documentation and is not copied, so only regular files are taken.
    sources.extend(path for path in (ROOT/'ml/artifacts').iterdir() if path.is_file())
    registry=safedata.load(ROOT/'ml/artifacts/registry')
    for item in registry['models']:
        if hashlib.sha256(safedata.bytes(ROOT/item['artifact'])).hexdigest()!=item['sha256']:
            raise ValueError('Model checksum verification failed: '+item['id'])
    # Phase 6 scientific-evidence artifacts. These back /api/science/calibration,
    # /api/science/evidence and /api/scientific-summary. They are placed at
    # scientific_data/phase6/ so app.research.phase6_report() resolves them via
    # its BUNDLE/"phase6" lookup on serverless deployments.
    phase6 = sorted((ROOT/'docs/phase6').glob('*'))
    if not phase6:
        raise ValueError('Phase 6 evidence artifacts are missing; run the analysis scripts')
    paired=[]  # (source file, target)
    for record in sources:
        # A record is named without its encoding; the bundle copies the file the data layer
        # resolves, so the packaged tree carries the same shape the repository stores.
        if not safedata.exists(record):
            raise ValueError('Missing runtime asset: '+str(record))
        source=safedata.resolve(record)
        if source.stat().st_size>2_000_000:
            raise ValueError('Oversized runtime asset: '+str(record))
        paired.append((source, destination/source.relative_to(ROOT)))
    for source in phase6:
        if not safedata.exists(source) or source.stat().st_size>2_000_000:
            raise ValueError('Missing or oversized Phase 6 artifact: '+str(source))
        paired.append((source, destination/'phase6'/source.name))
    for source, target in paired:
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
    print(f'Packaged {len(paired)} verified inference/preview assets; no training executed.')

if __name__=='__main__':package()
