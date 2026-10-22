"""机构官网封面：无字AI主视觉+精确原文排字；不用白板插画入口。"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

SKILL = Path(__file__).resolve().parents[1]

def font(size):
    ft=ImageFont.truetype(str(SKILL/'assets/fonts/NotoSansSC-VF.ttf'),size)
    try:ft.set_variation_by_axes([700])
    except (OSError,AttributeError):pass
    return ft

def compose(config, title, background=None):
    lines=config.get('lines',[])
    if not lines or ''.join(lines)!=title:
        raise ValueError('封面标题必须逐字等于原文标题')
    im=ImageOps.fit(background.convert('RGB'),(1920,1080)) if background is not None else Image.new('RGB',(1920,1080),'#0b1b2b')
    draw=ImageDraw.Draw(im)
    x,y=config.get('left',112),config.get('top',328)
    sizes=config.get('sizes',[96]+[55]*(len(lines)-1))
    if len(sizes)!=len(lines):raise ValueError('字号必须逐行给定')
    if x<80 or y<80:raise ValueError('标题须留足安全边距')
    boxes=[]
    for i,(line,size) in enumerate(zip(lines,sizes)):
        ft=font(size);box=draw.textbbox((x,y),line,font=ft)
        if box[2]>config.get('text_right',1270) or box[3]>1000:
            raise ValueError('标题越出安全区，请换行或调整字号')
        draw.text((x,y),line,font=ft,fill='#f8f5ee' if i==0 else '#e2e8ed')
        boxes.append(box);y+=int(size*1.6 if i==0 else size*1.55)
    # 克制的层级分隔，只作排版，不添加新宣传文案。
    draw.line((x,config.get('top',328)-40,x+86,config.get('top',328)-40),fill='#c3a169',width=4)
    return im,{'title':title,'lines':lines,'title_boxes':boxes,'size':[1920,1080],
               'cover_style':'institutional','background_fit':'aspect_preserving_center_crop'}

def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--project',default='.')
    ap.add_argument('--version',default='v01')
    ap.add_argument('--text-only',action='store_true')
    a=ap.parse_args(argv);p=Path(a.project).resolve()
    cfg=json.loads((p/'design/cover-institutional.json').read_text(encoding='utf-8'))
    title=(p/'brief/title.txt').read_text(encoding='utf-8').strip()
    bg=None
    if not a.text_only:
        path=(p/cfg['background']).resolve()
        if not path.is_relative_to(p):raise ValueError('背景必须位于项目内')
        bg=Image.open(path)
    image,record=compose(cfg,title,bg)
    suffix='text' if a.text_only else 'cover'
    output=p/f'renders/institutional-{suffix}-{a.version}.png'
    if output.exists():raise FileExistsError('不覆盖已有封面，请升版本')
    output.parent.mkdir(parents=True,exist_ok=True);image.save(output)
    record.update(output=str(output),sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                  background=cfg.get('background'),human_approved=False)
    if not a.text_only:
        (p/f'design/cover-institutional-record-{a.version}.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(output)

if __name__=='__main__':main()
