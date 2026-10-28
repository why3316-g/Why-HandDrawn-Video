"""Approved 2026-10-28 emotion strokes. Sequential, deterministic, scaleable."""
import math

STYLES=('sadness','anxiety','anger','helplessness','loneliness','pressure','relief','hope')

def draw(F, panel, style, x, y, width, height, at, dur=1.2, intensity='light'):
    """Place in a dedicated clear region; x/y are its top-left, not face coordinates."""
    if style not in STYLES or intensity not in ('light','medium'):
        raise ValueError('Unknown approved emotion/intensity')
    if min(width,height,dur)<=0: raise ValueError('Positive dimensions/duration required')
    n=5 if intensity=='light' else 8
    paths=[]
    for k in range(n):
        u=(k+.5)/n
        if style=='sadness': p=[(u,.1+(k%3)*.15),(max(0,u-.07),.45+(k%3)*.15)]
        elif style=='helplessness': p=[(u,.1),(u,.35+.18*(k%2))]
        elif style=='pressure': p=[(u,0),(u,.8-.1*(k%3))]
        elif style in ('hope','anger'):
            a=math.pi*(1.12+.76*u)
            p=[(.5+.25*math.cos(a),.9+.25*math.sin(a)),(.5+.48*math.cos(a),.9+.8*math.sin(a))]
        elif style=='loneliness':
            p=[(.5+.46*math.cos(math.pi*(1+u-.04+j*.08/12)),.8+.7*math.sin(math.pi*(1+u-.04+j*.08/12))) for j in range(13)]
        elif style=='relief':
            p=[(.1+.8*t,.85-u*.5-.22*math.sin(t*math.pi/2)) for t in [j/20 for j in range(21)]]
        else:
            p=[(.5+.42*math.sin(t*math.pi*2+.4*k),.5+.35*math.cos(t*math.pi*2*1.3+.8*k)) for t in [j/40 for j in range(41)]]
        paths.append([(x+a*width,y+b*height) for a,b in p])
    start=len(F.EV)
    for k,p in enumerate(paths):
        F.line(panel,p,at+dur*k/n,dur/n,'#ed7929' if style=='hope' else '#171717',max(2,width*.009),False)
        F.EV[-1]['emotion_style']=style
    return list(range(start,len(F.EV)))
