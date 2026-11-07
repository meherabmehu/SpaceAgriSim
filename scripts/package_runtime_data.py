"""Bundle only reviewed, small inference assets inside a Python service root."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def package():
    destination=ROOT/'backend/scientific_data'
    sources=[]
    for name in ['dataset_manifest.json','download_checksums.json','quality_report.json','external_lettuce.json','phase2_nasa_candidates.json','phase9_nasa_datasets.json']:
        sources.append(ROOT/'data/metadata'/name)
    sources.extend((ROOT/'data/processed').glob('*.csv'))
    sources.extend((ROOT/'data/raw/OSD-745').glob('*TRANSFORMED.csv'))
    sources.extend((ROOT/'ml/artifacts').glob('*.json'))
    registry=json.loads((ROOT/'ml/artifacts/registry.json').read_text())
    for item in registry['models']:
        if hashlib.sha256((ROOT/item['artifact']).read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError('Model checksum verification failed: '+item['id'])
    # Phase 6 scientific-evidence artifacts. These back /api/science/calibration,
    # /api/science/evidence and /api/scientific-summary. They are placed at
    # scientific_data/phase6/ so app.research.phase6_report() resolves them via
    # its BUNDLE/"phase6" lookup on serverless deployments.
    phase6 = sorted((ROOT/'docs/phase6').glob('*.json'))
    if not phase6:
        raise ValueError('Phase 6 evidence artifacts are missing; run the analysis scripts')
    paired=[]  # (source, target)
    for source in sources:
        if not source.is_file() or source.stat().st_size>2_000_000:
            raise ValueError('Missing or oversized runtime asset: '+str(source))
        paired.append((source, destination/source.relative_to(ROOT)))
    for source in phase6:
        if not source.is_file() or source.stat().st_size>2_000_000:
            raise ValueError('Missing or oversized Phase 6 artifact: '+str(source))
        paired.append((source, destination/'phase6'/source.name))
    for source, target in paired:
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
    print(f'Packaged {len(paired)} verified inference/preview assets; no training executed.')

if __name__=='__main__':package()
