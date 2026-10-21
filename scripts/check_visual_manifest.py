"""Validate recorded visual reviews and original-image reuse; never judge faces."""
from pathlib import Path
import argparse,hashlib,json
from collections import defaultdict

def check(path):
    path=Path(path).resolve();data=json.loads(path.read_text(encoding='utf-8'))
    errors=[];assets=data.get('assets',{});shots=data.get('shots',[]);ids=set();uses=defaultdict(list);hash_uses=defaultdict(list);rows=[]
    if not assets or not shots:errors.append('assets and shots must be non-empty')
    files={}
    for aid,a in assets.items():
        file=(path.parent/a.get('file','')).resolve()
        if not file.is_file():errors.append(f'{aid}: source image missing');continue
        if not a.get('origin_id'):errors.append(f'{aid}: original source identity missing')
        sha=hashlib.sha256(file.read_bytes()).hexdigest();files[aid]=(sha,str(file))
        if a.get('sha256') and a['sha256']!=sha:errors.append(f'{aid}: hash differs from reviewed image')
        for field in ('identity','anatomy','finish'):
            if a.get('quality_review',{}).get(field)!='pass':errors.append(f'{aid}: quality {field} not passed')
    for shot in shots:
        sid=shot.get('id')
        if not sid or sid in ids:errors.append(f'{sid}: missing/duplicate shot identity')
        ids.add(sid)
        if not isinstance(shot.get('start'),(int,float)) or not isinstance(shot.get('end'),(int,float)) or shot['end']<=shot['start']:errors.append(f'{sid}: invalid time span')
        if not shot.get('narration') or not shot.get('roles') or not shot.get('assets'):errors.append(f'{sid}: missing narration, roles or assets')
        for role in shot.get('roles',[]):
            for field in ('name','age','emotion','face','body','gaze','action','avoid'):
                if not role.get(field):errors.append(f'{sid}: role {role.get("name")} missing {field}')
            if role.get('name')=='陪伴师':
                if role.get('gender')!='female':errors.append(f'{sid}: companion must be female')
                if not isinstance(role.get('age'),(int,float)) or not 25<=role['age']<=29:errors.append(f'{sid}: companion must be about 27 years old')
                review=shot.get('companion_review',{})
                for field in ('identity','listening','logo'):
                    if review.get(field)!='pass':errors.append(f'{sid}: companion {field} review not passed')
                if review.get('logo_side')!='wearer_left':errors.append(f'{sid}: companion brooch must be on wearer left chest')
                if not review.get('observation'):errors.append(f'{sid}: actual companion/brooch observation missing')
                logo=(path.parent/review.get('logo_source','')).resolve()
                if not logo.is_file():errors.append(f'{sid}: original brand logo reference missing')
                elif hashlib.sha256(logo.read_bytes()).hexdigest()!=review.get('logo_sha256'):errors.append(f'{sid}: original logo hash missing or changed')
        for aid in set(shot.get('assets',[])):
            if aid not in assets or aid not in files:errors.append(f'{sid}: undefined/missing asset {aid}');continue
            a=assets[aid];region=json.dumps(a.get('source_region','whole'),sort_keys=True)
            original=(a.get('origin_id'),region);hashed=(files[aid][0],region)
            uses[original].append(sid);hash_uses[hashed].append(sid)
            review=shot.get('assessments',{}).get(aid,{})
            for field in ('identity','emotion','action','relation'):
                if review.get(field)!='pass':errors.append(f'{sid}/{aid}: {field} not reviewed/passed')
            if not review.get('observation'):errors.append(f'{sid}/{aid}: actual image observation missing')
            rows.append({'shot':sid,'asset':aid,'origin_id':a.get('origin_id'),'file':files[aid][1],'sha256':files[aid][0]})
    for grouping,label in ((uses,'source'),(hash_uses,'identical image')):
        for key,sids in grouping.items():
            unique=list(dict.fromkeys(sids))
            if len(unique)>2:errors.append(f'{label} used {len(unique)} times (>2): {unique}')
    return {'pass':not errors,'errors':errors,'uses':rows,'max_original_uses':max((len(set(v)) for v in uses.values()),default=0),'limitations':'Checks reviews as records, not image emotions. Derived images must honestly retain original source/region. Visual review remains required.'}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('manifest');ap.add_argument('--out');a=ap.parse_args();report=check(a.manifest)
    if a.out:Path(a.out).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'pass':report['pass'],'errors':report['errors'],'max_original_uses':report['max_original_uses']},ensure_ascii=False,indent=2))
    raise SystemExit(0 if report['pass'] else 1)
