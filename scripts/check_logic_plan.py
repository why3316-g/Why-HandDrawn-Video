"""检查宽屏全文逻辑分析、官方原件与逐板人物；不代替独立语义审片。"""
import argparse
import json
from pathlib import Path
from hdv.logic import logic_errors

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project',default='.')
    a=ap.parse_args(); p=Path(a.project)
    cfg=json.loads((p/'design/config.json').read_text(encoding='utf-8'))
    spec=json.loads((p/cfg.get('spec_out','design/spec-film.json')).read_text(encoding='utf-8'))
    errors=logic_errors(p,spec['data']['scenes'],spec['data']['events'])
    print(json.dumps({'pass':not errors,'errors':errors},ensure_ascii=False,indent=2))
    raise SystemExit(bool(errors))
