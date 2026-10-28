"""Approved white-paper props; import immutable sprites into the normal hero pipeline."""
import hashlib
import json

def draw(F, panel, prop_id, cx, top, height, at, dur=1.5):
    root=F.P/'assets/images/narrative-props-v01'
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    item=next((x for x in manifest['items'] if x['id']==prop_id),None)
    if not item or not item['approved']: raise ValueError('Unknown/unapproved narrative prop')
    if hashlib.sha256((root/item['file']).read_bytes()).hexdigest()!=item['sha256']:
        raise ValueError('Narrative prop content hash mismatch')
    lib=json.loads((root/'strokes.json').read_text(encoding='utf-8'))
    sid='prop-'+prop_id
    source=dict(lib['source_images'][prop_id]);source['file']='narrative-props-v01/'+item['file']
    sprite=dict(lib['sprites'][prop_id]);sprite['group']=sid
    F.lib['source_images'][sid]=source;F.lib['sprites'][sid]=sprite
    F.aspect[sid]=sprite['rect'][2]/sprite['rect'][3]
    width=height*F.aspect[sid]
    if not item['min_display_width']<=width<=item['max_display_width']:
        raise ValueError('Prop display width outside approved small-object range')
    F.hero(panel,sid,cx,top,height,at,dur)
    F.EV[-1]['prop_id']=prop_id
    return len(F.EV)-1
