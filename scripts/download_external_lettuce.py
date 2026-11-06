"""Acquire CC-BY-4.0 WUR/4TU data separately from NASA sources."""
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://doi.org/10.4121/5a7472f0-8a67-4ec0-84c9-9d032990d654.v1"
FILES = {
    "original_dataset_lettuce.xlsx": "https://data.4tu.nl/file/5a7472f0-8a67-4ec0-84c9-9d032990d654/6df07236-42b1-4ac4-8fc4-841ff338ec6d",
    "readme.txt": "https://data.4tu.nl/file/5a7472f0-8a67-4ec0-84c9-9d032990d654/656d358e-0593-4a58-85fd-fb679d72963b",
}

def acquire():
    folder = ROOT / "data/raw/WUR-lettuce"
    folder.mkdir(parents=True, exist_ok=True)
    provenance = ROOT / "data/metadata/external_lettuce.json"
    prior = json.loads(provenance.read_text()) if provenance.exists() else {}
    records = []
    for name, url in FILES.items():
        path = folder / name
        if not path.exists():
            request = urllib.request.Request(url, headers={"User-Agent":"SpaceAgriSim scientific reproducibility"})
            with urllib.request.urlopen(request, timeout=90) as response:
                body = response.read(2_000_001)
                if len(body) > 2_000_000:
                    raise ValueError("External file exceeded size budget")
                path.write_bytes(body)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = next((r['sha256'] for r in prior.get('files',[]) if r['name']==name), None)
        if expected and expected != digest:
            raise ValueError(f"Source checksum mismatch: {name}")
        records.append({"name":name,"url":url,"path":str(path.relative_to(ROOT)).replace('\\','/'),"sha256":digest,"bytes":path.stat().st_size})
    payload = {"id":"WUR-lettuce","sourceType":"external scientific data (not NASA)","sourceUrl":SOURCE,"title":"Plant Factories Are Heating Up: lettuce growth dataset","license":"CC-BY-4.0","creators":"Esther Meinen, Laura Carotti, Luuk Graamans, Federico Puksic, Michele Butturini, Cecilia Stanghellini","retrievedAt":prior.get("retrievedAt",datetime.now(timezone.utc).isoformat()),"files":records,"conditions":"Lactuca sativa cv. Batavia Othilie; Earth chambers; 16 h photoperiod; non-limiting water, nutrients and CO2. Four experiments, 2018–2019.","limitations":["Not NASA or spaceflight data.","Tip-burn-related treatment omissions create selection bias.","Plant identifiers are reused across experiments; split by whole experiment."]}
    provenance.write_text(json.dumps(payload,indent=2,ensure_ascii=True)+'\n',encoding='utf-8')
    return payload

if __name__ == '__main__':
    print(json.dumps(acquire(),indent=2))
