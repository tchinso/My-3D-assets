"""Four reference-led kitbashes using the original catalog's rigged topology.

Source atlases, folds, skin weights and garment seams remain the foundation.
New leatherwork, cape, tiered silk, flowers and handheld props are fitted in
the donor bind pose. No source file is changed.
"""
from __future__ import annotations

import math
import numpy as np
from PIL import Image, ImageDraw

DESIGNS = [
    dict(id=11, slug='11_quinn_adventurer', name='Quinn', name_ko='퀸',
         tagline='Leather & lace · twin dagger scout', hair='Shizuko (Swimsuit)', face='Nonomi',
         hair_color='#796052', eye_color='#77b9c2', palette=['#8a6754','#eee6dc','#a72e36','#dec586'],
         style='adventurer', legs='bare', attack='daggers',
         design='첫 번째 참고 이미지의 갈색 긴 트윈테일과 빨강 리본, 청록색 눈. 회갈색 크롭 프릴 재킷과 흰 크라바트, 갈색 가죽 치마·벨트·크로스백, 긴 부츠와 두 자루 단검.'),
    dict(id=12, slug='12_kimon_fox_idol', name='Kimon', name_ko='키몬',
         tagline='Golden fox · starbell encore', hair='Izuna (Swimsuit)', face='Momoi (Maid)',
         hair_color='#f3be54', eye_color='#d76a83', palette=['#fff3d7','#ed842d','#72d3d8','#f3be54'],
         style='fox_idol', legs='bare', attack='fox_baton',
         extra_source_roles={'abdomen':'Hina (Swimsuit).glb'},
         design='두 번째 참고 이미지의 황금빛 단발·짧은 포니테일과 큰 여우 귀, 붉은 눈. 크림색·주황색 크롭 상의와 넓은 분리 소매, 청록색 짧은 치마와 옆으로 길게 내려오는 체크 패널, 별 장식 방울 바통.'),
    dict(id=13, slug='13_florielle_witch', name='Florielle', name_ko='플로리엘',
         tagline='Flower witch · celestial grimoire', hair='Yuzu (Maid)', face='Natsu',
         hair_color='#98605c', eye_color='#9ab25c', palette=['#f8eada','#e995ae','#252a4d','#d9b475'],
         style='flower_witch', legs='white', attack='witch_staff',
         extra_source_roles={'hat':'Eri.glb'},
         design='세 번째 참고 이미지의 적갈색 긴 웨이브와 꽃·리본이 달린 큰 마녀 모자. 크림색·분홍색 프릴 드레스와 넓은 소매, 별자리 무늬의 남색·분홍 안감 망토, 꽃 지팡이와 허리에 매단 마법서.'),
    dict(id=14, slug='14_rosaria_bride', name='Rosaria', name_ko='로사리아',
         tagline='Pearl crown · rose bouquet', hair='Seia (Swimsuit)', face='Nonomi',
         hair_color='#f5e4ba', eye_color='#6ec3d8', palette=['#fffaf1','#e5e2f7','#e0b7c6','#d6b86e'],
         style='rose_bride', legs='bare', attack='bouquet',
         extra_source_roles={'bare_legs_and_feet':'Hina (Swimsuit).glb'},
         design='네 번째 참고 이미지의 연한 금발 긴 컬과 작은 보석 왕관, 하늘색 눈. 원본 드레스의 코르셋·큰 리본과 흰색·연보라색 겹프릴 하이로 드레스, 진주 목걸이, 흰 장미 부케, 맨다리·맨발.'),
]
COSTUME_SOURCES = {11:'Sakurako (Idol)', 12:'Seia', 13:'Reisa (Magical)', 14:'Saori (Dress) (Cafe)'}


def color(hex):
    return np.array([int(hex[i:i+2],16) for i in (1,3,5)],float)


def tint_eyes(im, target):
    """Replace chromatic iris pigment while retaining ink and white highlights."""
    a=np.array(im);c=a[:,:,:3].astype(float);hi=c.max(2);lo=c.min(2)
    mask=(hi-lo>24)&(hi>65)&(lo<180)
    # Face skin/blush use reddish near-white values; dark lashes stay unchanged.
    skin=(c[:,:,0]>175)&(c[:,:,1]>125)&(c[:,:,2]>110)&(c[:,:,0]>=c[:,:,1])
    mask&=~skin
    lum=c@np.array([.27,.57,.16])/255
    a[:,:,:3][mask]=np.clip(color(target)*(.32+.90*lum[mask,None]),0,255).astype('u1')
    return Image.fromarray(a)


def hair_selection(b,p,s,groups):
    pos=p['pos'].copy();idx=p['idx'];keep=np.ones(len(idx),bool)
    # Animal ears and swim accessories are kept only for the fox idol.
    for g in groups:
        v=np.unique(idx[g]);q=pos[v]
        dom=p['j'][v][np.arange(len(v)),p['w'][v].argmax(1)]
        names=[p['names'][n].lower() for n in dom]
        if b.c['id']!=12 and any('ear_' in n for n in names):keep[g]=False
        if any(t in n for n in names for t in ('cap','sunglass','headband','acc_')):keep[g]=False
    if b.c['id']==11:
        head = next(i for i,n in enumerate(s.doc['nodes']) if n.get('name') == 'Bip001 Head' and i in s.world)
        source_y = s.world[head][1,3]
        selected = np.zeros(len(pos), dtype=bool)
        for group in groups:
            vertices = np.unique(idx[group])
            dominant = p['j'][vertices][np.arange(len(vertices)),p['w'][vertices].argmax(1)]
            if any(p['names'][joint].lower().startswith('bone_hair_t_') for joint in dominant):
                selected[vertices] = True
        pos[selected] = _quinn_tail_fit(pos[selected], source_y)
        delta = b.headpos-s.world[head][:3,3]
        delta[1] += b.head_adjust
        b.quinn_hair_surface = (pos+delta, idx[keep])
    if b.c['id']==14:
        # Relax the swimsuit side ponytail into a low, loose curl cascade.
        long=(pos[:,1]<.73)&(pos[:,2]<.07)
        factor=np.clip((.76-pos[:,1])/.25,0,1)
        pos[long,0]*=(1-.20*factor[long])
        pos[long,2]-=.035*factor[long]
    b.appearance_fit['hair']={'method':'Preserved rigged donor locks; removed unrelated head accessories; tinted original atlas',
                              'donor':s.name+'.glb','iris_tint':b.c['eye_color']}
    if b.c['id']==11:
        b.appearance_fit['hair'].update(
            attachment_fit='Twin-tail roots fitted inward and forward into the scalp; corresponding rest pivots follow the same fit',
            ribbons='Red bow knots projected onto the fitted twin-tail root surface')
    return pos,idx[keep]


def _quinn_tail_fit(points, head_y):
    """Seat complete donor ponytail roots in the back/side scalp volume."""
    q = np.asarray(points, dtype=float).copy()
    upper = np.clip((q[:,1]-head_y-.13)/.12, 0, 1)
    upper = upper*upper*(3-2*upper)
    q[:,0] -= np.sign(q[:,0])*(.014+.012*upper)
    q[:,2] += .050+.025*upper
    return q


def fit_hair_pivots(b):
    """Move only Quinn's imported tail pivots, leaving the body rig unchanged."""
    if b.c['id'] != 11:
        return
    source = b.source(b.c['hair'])
    head = next(i for i,n in enumerate(source.doc['nodes']) if n.get('name') == 'Bip001 Head' and i in source.world)
    delta = b.headpos-source.world[head][:3,3]
    delta[1] += b.head_adjust
    changed = set()
    for name,index in b.bone.items():
        if not name.lower().startswith('shizuko (swimsuit)::bone_hair_t_'):
            continue
        point = b.world[index][:3,3]-delta
        fitted = _quinn_tail_fit(point[None,:], source.world[head][1,3])[0]+delta
        b.world[index] = b.world[index].copy()
        b.world[index][:3,3] = fitted
        changed.add(index)
    parents = {child:index for index,node in enumerate(b.doc['nodes']) for child in node.get('children',[])}
    for index,node in enumerate(b.doc['nodes']):
        if index not in b.world or (index not in changed and parents.get(index) not in changed):
            continue
        parent = parents.get(index)
        local = np.linalg.inv(b.world[parent])@b.world[index] if parent is not None else b.world[index]
        for key in ('translation','rotation','scale'):
            node.pop(key,None)
        node['matrix'] = local.T.reshape(-1).tolist()


def _quinn_ribbon_anchor(b, side):
    """Place the knot on the actual curved ponytail surface, including depth."""
    x, y = side*.195, b.headpos[1]+b.head_adjust+.235
    pos, idx = b.quinn_hair_surface
    triangles = pos[idx]
    a, c, d = triangles[:,0], triangles[:,1], triangles[:,2]
    e0, e1 = c[:,:2]-a[:,:2], d[:,:2]-a[:,:2]
    point = np.array([x,y])-a[:,:2]
    den = e0[:,0]*e1[:,1]-e1[:,0]*e0[:,1]
    valid = np.abs(den)>1e-10
    den = np.where(valid,den,1)
    u = (point[:,0]*e1[:,1]-point[:,1]*e1[:,0])/den
    v = (e0[:,0]*point[:,1]-e0[:,1]*point[:,0])/den
    inside = valid&(u>=0)&(v>=0)&(u+v<=1)
    if not inside.any():
        raise ValueError('Quinn ribbon anchor misses the fitted tail root surface')
    z = a[:,2]+u*(c[:,2]-a[:,2])+v*(d[:,2]-a[:,2])
    return np.array([x,y,z[inside].max()+.0015])


def _groups(p):
    # Import lazily to avoid a cycle with the builder's design registry.
    from build_characters import components
    return components(p['pos'],p['idx'])


def _repaint(b,p):
    im=b.src.image(p['mat']['pbrMetallicRoughness']['baseColorTexture']['index'])
    a=np.array(im);c=a[:,:,:3].astype(float);r,g,bl=c.transpose(2,0,1)
    lum=c@np.array([.27,.57,.16])/255
    skin=(r>165)&(g>125)&(bl>110)&(r-g>8)&(r-bl>10)&(r-g<75)
    gold=(r>140)&(g>98)&(bl<g*.71)&(r>g*.94)
    def paint(mask,target,raised=False):
        mask=mask&~skin&~gold
        if not mask.any():return
        ref=max(float(np.quantile(lum[mask],.85)),.05)
        shade=np.clip(lum/ref,.18,1.05)
        if raised:shade=.60+.40*np.minimum(shade,1)
        a[:,:,:3][mask]=np.clip(color(target)*shade[mask,None],0,255).astype('u1')
    if b.c['id']==11:
        paint(c.max(2)<145,'#896c60',True)
        paint((bl>r+8)&(bl>g+3),'#775342')
    elif b.c['id']==12:
        paint((r>g+22)&(g>bl+18),'#ef8d30',True)
        paint(c.max(2)<135,'#66bac1',True)
    elif b.c['id']==13:
        paint((bl>r+8)&(bl>g+5),'#d395a6',True)
        paint((r>g+25)&~skin,'#c5758e',True)
    elif b.c['id']==14:
        paint(c.max(2)<150,'#d7cfdf',True)
    if p['mat'].get('alphaMode','OPAQUE')=='OPAQUE':a[:,:,3]=255
    return Image.fromarray(a)


def _garment(b,p):
    """Select whole clothing islands, then fit original cloth around the reference."""
    pos=p['pos'].copy();idx=p['idx'];keep=np.ones(len(idx),bool);cid=b.c['id']
    for triangles in _groups(p):
        v=np.unique(idx[triangles]);q=pos[v];uv=p['uv'][v]
        lo,hi=q.min(0),q.max(0);center=q.mean(0)
        dom=p['j'][v][np.arange(len(v)),p['w'][v].argmax(1)]
        names=[p['names'][n].lower() for n in dom]
        if hi[1]>b.headpos[1]+.075 and center[1]>b.headpos[1]+.025:
            keep[triangles]=False;continue
        if any(t in n for n in names for t in ('bone_wing','bone_hat','bone_headphone','bone_bird','bone_hair')):
            keep[triangles]=False;continue
        if any('bone_tail' in n for n in names):keep[triangles]=False;continue
        if cid==11:
            # The real raised skirt front and broad sleeve cuffs are retained.
            if hi[1]<.42 and lo[1]>.058 and np.ptp(q[:,0])<.15:
                # Replace printed socks by leather boot geometry below.
                if any('calf' in n or 'thigh' in n for n in names):
                    skin=b.material('Quinn exposed legs','#f6dbcc')
                    b.mesh('Quinn donor leg anatomy',pos,idx[triangles],skin,uv=p['uv'],norm=p['norm'],
                           j=b.map_bones(p,b.src,np.zeros(3)),w=p['w']);keep[triangles]=False
            if center[1]<.53 and center[1]>.485 and hi[1]<.55 and abs(center[0])<.09:
                # The source's fitted waist is skin between crop jacket and belt.
                mi=b.material('Quinn midriff','#f6dbcc')
                b.mesh('Quinn exposed cropped waist',pos,idx[triangles],mi,uv=p['uv'],norm=p['norm'],
                       j=b.map_bones(p,b.src,np.zeros(3)),w=p['w']);keep[triangles]=False
        elif cid==12:
            # Top uses original torso/seams; the lower bodice becomes bare waist.
            if lo[1]>.429 and hi[1]<.56 and abs(center[0])<.10:
                t=np.clip((.56-pos[v,1])/.13,0,1);pos[v,1]+=.05*t
            if hi[1]<.44 and lo[1]>.20 and np.ptp(q[:,0])>.25:
                # Keep source pleats but shorten them into the turquoise underskirt.
                pos[v,1]=.438-(.438-pos[v,1])*.57
            if hi[1]<.43 and np.ptp(q[:,0])<.25 and any('calf' in n or 'thigh' in n for n in names):
                mi=b.material('Kimon bare legs','#f9dfcf')
                b.mesh('Kimon donor bare legs',pos,idx[triangles],mi,uv=p['uv'],norm=p['norm'],
                       j=b.map_bones(p,b.src,np.zeros(3)),w=p['w']);keep[triangles]=False
        elif cid==14:
            # Keep original corset, chest lace and large back bow. Replace the
            # floor-length skirts and hidden stocking anatomy with layered silk.
            cloth=any('dress' in n for n in names)
            if cloth or (lo[1]<.43 and hi[1]<.545 and uv[:,0].max()<.76):
                keep[triangles]=False
            if hi[1]<.14:keep[triangles]=False
        elif cid==13 and hi[1]<.40 and np.ptp(q[:,0])<.16 and any('calf' in n or 'thigh' in n for n in names):
            mi=b.material('Florielle ivory stockings','#f7eef0')
            b.mesh('Florielle plain ivory legwear',pos,idx[triangles],mi,uv=p['uv'],norm=p['norm'],
                   j=b.map_bones(p,b.src,np.zeros(3)),w=p['w']);keep[triangles]=False
    if cid==12:
        centers=pos[idx].mean(1)
        waist=(centers[:,1]>.439)&(centers[:,1]<.505)&(np.abs(centers[:,0])<.110)
        keep&=~waist
    idx=idx[keep]
    if not len(idx):return
    mat=b.wardrobe_material('Reference tailored source / '+b.src.name+' / '+p['mat']['name'],p,_repaint(b,p))
    b.mesh('Reference donor garment / '+p['name'],pos,idx,mat,uv=p['uv'],norm=None,
           j=b.map_bones(p,b.src,np.zeros(3)),w=p['w'])


def _point(b,name,center,size,mat,bone='Bip001 Head',rays=5):
    center=np.asarray(center,float);vertices=[center+[0,0,.003]]
    for k in range(2*rays):
        t=math.pi/2+k*math.pi/rays;r=size if k%2==0 else size*.44
        vertices.append(center+[r*math.cos(t),r*math.sin(t),0])
    faces=[[0,k+1,(k+1)%(2*rays)+1]for k in range(2*rays)]
    b.mesh(name,vertices,faces,mat,bone)


def _flower(b,name,c,size,petal,heart,bone='Bip001 Head',count=5):
    c=np.asarray(c,float)
    for k in range(count):
        a=2*math.pi*k/count
        b.ellipsoid(name+' petal',c+[math.cos(a)*size*.55,math.sin(a)*size*.55,0],
                    [size*.45,size*.42,size*.17],petal,bone,16,8)
    b.ellipsoid(name+' center',c+[0,0,size*.17],[size*.20]*3,heart,bone,12,6)


def _palm(b,side):
    hand=b.world[b.bone[f'Bip001 {side} Hand']][:3,3].copy()
    fingers=[b.world[b.bone[n]][:3,3]for n in [f'Bip001 {side} Finger1',f'Bip001 {side} Finger2']if n in b.bone]
    if fingers:hand+=.5*(np.mean(fingers,axis=0)-hand)
    return hand


def _leatherwork(b,gold,cream):
    leather=b.material('Quinn leather grain','#755443',b.clothing_texture('#87624e'))
    dark=b.material('Quinn leather seam','#563c32');red=b.material('Quinn red silk','#a8323b')
    # These coordinates already follow the donor surfaces. Use the actual
    # joints directly so the older generic forward garment offset is not added.
    pelvis, spine = b.bone['Bip001 Pelvis'], b.bone['Bip001 Spine1']
    b.lathe('Quinn wide leather waist belt',[(.478,.09,.064),(.45,.098,.071)],leather,'Bip001 Pelvis',segments=64)
    # Buckle is an open metal frame, rather than a solid square.
    b.tube('Quinn silver buckle frame',[[-.029,.468,.126],[.029,.468,.126],[.029,.433,.133],[-.029,.433,.133],[-.029,.468,.126]],
           [.004]*5,b.material('Quinn brushed buckle','#e1e5ec',metal=.65),pelvis)
    b.tube('Quinn buckle tongue',[[0,.448,.135],[.025,.448,.135]],[.0025,.0025],gold,pelvis)
    # Strap follows the surface of the cropped donor blouse and left hip.
    b.tube('Quinn diagonal stitched satchel strap',[[-.066,.618,.087],[-.025,.564,.119],[.018,.511,.129],[.106,.453,.095]],
           [.007]*4,leather,spine)
    b.ellipsoid('Quinn rounded leather satchel',[.146,.441,.093],[.060,.049,.033],leather,pelvis)
    b.patch('Quinn satchel flap',[[.092,.47,.133],[.199,.47,.133],[.183,.426,.151],[.149,.415,.157],[.113,.429,.151]],dark,pelvis)
    b.ellipsoid('Quinn bag clasp',[.146,.435,.161],[.008,.009,.004],gold,pelvis,12,6)
    b.bow('Quinn ivory cravat',[0,.609,.080],.040,cream,spine)
    b.ellipsoid('Quinn turquoise brooch',[0,.618,.090],[.012,.014,.006],b.material('Quinn brooch','#62babe'),spine,16,8)
    for side,letter in [(-1,'R'),(1,'L')]:
        tail_root = b.bone[f'Shizuko (Swimsuit)::bone_hair_t_{letter.lower()}_00']
        b.bow('Quinn red hair ribbon',_quinn_ribbon_anchor(b,side),.037,red,tail_root)
        upper=b.world[b.bone[f'Bip001 {letter} UpperArm']][:3,3]
        elbow=b.world[b.bone[f'Bip001 {letter} Forearm']][:3,3]
        wrist=b.world[b.bone[f'Bip001 {letter} Hand']][:3,3]
        jacket=b.material('Quinn taupe jacket silk','#8b7468',b.clothing_texture('#8b7468'))
        b.tube('Quinn cropped jacket upper sleeve',[upper,upper*.4+elbow*.6,elbow],[.037,.039,.033],jacket,f'Bip001 {letter} UpperArm',20)
        b.tube('Quinn tailored jacket forearm',[elbow,elbow*.25+wrist*.75,wrist],[.034,.030,.027],jacket,f'Bip001 {letter} Forearm',20)
        # Boots use actual leg rest endpoints, split at calf/foot joints.
        calf=b.world[b.bone[f'Bip001 {letter} Calf']][:3,3];foot=b.world[b.bone[f'Bip001 {letter} Foot']][:3,3]
        b.tube('Quinn tall stitched boot',[calf+[0,.027,0],calf,foot],[.039,.037,.026],leather,f'Bip001 {letter} Calf',24)
        b.ellipsoid('Quinn leather boot toe',foot+[0,-.012,.027],[.031,.027,.056],leather,f'Bip001 {letter} Foot',20,10)
        h=_palm(b,letter);bone=f'Bip001 {letter} Hand'
        b.tube('Quinn dagger grip',[h+[0,-.027,0],h+[0,.025,0]],[.007,.007],dark,bone,16)
        b.tube('Quinn dagger curved guard',[h+[-.025,.028,0],h+[0,.038,.004],h+[.025,.028,0]],[.003]*3,gold,bone)
        vertices=[h+[-.018,.040,0],h+[.018,.040,0],h+[0,.208,0],h+[0,.055,.004]]
        b.mesh('Quinn twin leaf dagger',vertices,[[0,3,2],[3,1,2]],b.material('Quinn dagger steel','#dce6e8',metal=.65),bone)


def _fox_panels(b,gold,cream):
    orange=b.material('Kimon orange piping','#ed8830');teal=b.material('Kimon turquoise silk','#7ed2d2')
    texture=Image.new('RGBA',(512,512),(255,244,215,255));d=ImageDraw.Draw(texture)
    for y in range(0,512,64):
        for x in range(0,512,64):
            if (x//64+y//64)%2:d.rectangle((x,y,x+63,y+63),fill=(245,207,109,255))
    check=b.material('Kimon yellow check panels','#ffffff',texture)
    _abdomen(b)
    # Izuna's ear topology is in the Body primitive, separate from the hair.
    s=b.source(b.c['hair']);sh=next(i for i,n in enumerate(s.doc['nodes'])if n.get('name')=='Bip001 Head'and i in s.world)
    delta=b.headpos-s.world[sh][:3,3];delta[1]+=b.head_adjust
    for p in s.parts():
        if not p['mat']['name'].endswith('_Body'):continue
        selected=[]
        ear=np.array(['ear_'in n.lower()for n in p['names']])
        coverage=(ear[p['j']]*p['w']).sum(1)
        for g in _groups(p):
            v=np.unique(p['idx'][g])
            if coverage[v].max()>.2 and p['pos'][v,1].mean()>.82:selected.extend(g)
        if selected:
            im=s.image(p['mat']['pbrMetallicRoughness']['baseColorTexture']['index']);a=np.array(im)
            c=a[:,:,:3].astype(float);lum=c@np.array([.27,.57,.16])/255
            white=(c.min(2)>170)&(c.max(2)-c.min(2)<45)
            a[:,:,:3][~white]=np.clip(color('#edbd60')*(.35+.65*lum[~white,None]),0,255).astype('u1')
            a[:,:,:3][white]=np.clip(color('#fff4dd')*(.8+.2*lum[white,None]),0,255).astype('u1')
            b.mesh('Kimon actual Izuna fox ears',p['pos']+delta,p['idx'][selected],b.material('Kimon golden fox ear atlas','#ffffff',Image.fromarray(a)),
                   'Bip001 Head',uv=p['uv'],norm=p['norm'])
    for side in (-1,1):
        v=[];uv=[];faces=[]
        for k in range(9):
            t=k/8;y=.448-.34*t;width=.055+.06*t
            for i in range(9):
                f=i/8;x=side*(.095+width*f);z=.075-.205*t+.026*math.sin(math.pi*f)
                v.append([x,y+.028*math.cos(math.pi*f)*t,z]);uv.append([f,t])
        for k in range(8):
            for i in range(8):a=k*9+i;faces.extend([[a,a+9,a+1],[a+1,a+9,a+10]])
        # A light leg influence gives the open panels a distinct alternating sway.
        bones=[('Bip001 Pelvis',.85),(f'Bip001 {"L"if side>0 else"R"} Thigh',.15)]
        b.mesh('Kimon split checked coat tail',v,faces,check,bones,uv=uv)
        for edge in [0,8]:
            points=[v[k*9+edge]for k in range(9)]
            b.tube('Kimon orange panel border',points,[.003]*9,orange,bones)
    b.bow('Kimon orange bow tie',[0,.59,.101],.047,orange,'Bip001 Spine1')
    b.lathe('Kimon turquoise pleated underskirt',[(.441,.102,.073),(.337,.18,.122)],teal,'Bip001 Pelvis',segments=72,pleats=.055)
    # Deliberate star/bell motifs instead of the swimsuit donor's headband.
    _point(b,'Kimon lilac hair star',[-.047,b.headpos[1]+.205,.148],.020,b.material('Kimon violet stars','#a09ccb'))
    b.bow('Kimon ponytail ribbon',[.164,b.headpos[1]+.15,-.025],.032,teal)
    h=_palm(b,'R');bone='Bip001 R Hand'
    b.tube('Kimon starbell baton',[h+[0,-.045,0],h+[0,.145,0]],[.005,.005],orange,bone,16)
    _point(b,'Kimon baton gold star',h+[0,.184,0],.041,gold,bone)
    b.ellipsoid('Kimon hanging bell',h+[.035,.145,0],[.013,.016,.013],gold,bone,20,10)
    b.bow('Kimon baton turquoise ribbon',h+[0,.128,.006],.030,teal,bone)


def _abdomen(b):
    """Fit an actual exposed donor abdomen between the cropped shirt and skirt."""
    from build_characters import components
    s=b.source('Hina (Swimsuit)');p=next(p for p in s.parts()if p['mat']['name'].endswith('_Body'))
    group=max(components(p['pos'],p['idx'],weld=True),key=len);idx=p['idx'][group]
    joints=s.doc['skins'][s.doc['nodes'][p['node']]['skin']]['joints'];transforms=[];remap=[]
    for source_node in joints:
        anchor=source_node
        while s.doc['nodes'][anchor].get('name','')not in b.bone or s.doc['nodes'][anchor].get('name','').startswith('Bip001_B'):
            if anchor not in s.parents:break
            anchor=s.parents[anchor]
        target=b.bone.get(s.doc['nodes'][anchor].get('name'),b.bone['Bip001 Pelvis'])
        remap.append(target);transforms.append(b.world[target]@np.linalg.inv(s.world[anchor]))
    blend=(np.array(transforms)[p['j']]*p['w'][:,:,None,None]).sum(1)
    pos=np.einsum('nij,nj->ni',blend,np.c_[p['pos'],np.ones(len(p['pos']))])[:,:3]
    centers=pos[idx].mean(1);idx=idx[(centers[:,1]>.424)&(centers[:,1]<.518)]
    b.mesh('Kimon fitted exposed donor abdomen',pos,idx,b.material('Kimon warm porcelain abdomen','#f9dfcf'),
           uv=p['uv'],norm=None,j=np.array(remap,np.uint16)[p['j']],w=p['w'])


def _witch(b,gold,cream):
    navy=b.material('Florielle starlit velvet','#282c50');pink=b.material('Florielle rose lining','#d47c9c')
    sky=b.material('Florielle blue silk','#b8d4e8');leaf=b.material('Florielle leaves','#72986c')
    # Eri supplies the real pointed hat mesh, including its curved brim and UVs.
    s=b.source('Eri');sh=next(i for i,n in enumerate(s.doc['nodes'])if n.get('name')=='Bip001 Head'and i in s.world)
    delta=b.headpos-s.world[sh][:3,3];delta[1]+=b.head_adjust
    for p in s.parts():
        if not p['mat']['name'].endswith('_Body'):continue
        selected=[]
        for g in _groups(p):
            v=np.unique(p['idx'][g]);q=p['pos'][v]
            dom=p['j'][v][np.arange(len(v)),p['w'][v].argmax(1)]
            names=[p['names'][n].lower()for n in dom]
            if any('hat' in n for n in names)and q[:,1].mean()>.84:selected.extend(g)
        if selected:
            im=s.image(p['mat']['pbrMetallicRoughness']['baseColorTexture']['index']);a=np.array(im)
            lum=a[:,:,:3].astype(float)@np.array([.27,.57,.16])/255
            a[:,:,:3]=np.clip(color('#35334e')*(.38+.62*lum[:,:,None]),0,255).astype('u1');im=Image.fromarray(a)
            b.mesh('Florielle fitted Eri pointed hat',p['pos']+delta,p['idx'][selected],b.material('Florielle donor hat velvet','#ffffff',im),'Bip001 Head',uv=p['uv'],norm=p['norm'])
    b.bow('Florielle hat sky ribbon',[-.137,b.headpos[1]+.245,.094],.073,sky)
    for k in range(3):_flower(b,'Florielle hat blossom',[-.15+k*.032,b.headpos[1]+.263-k*.019,.112],.021,pink,gold)
    # Open front cape wraps the shoulders, leaving the original bodice visible.
    vertices=[];uv=[];faces=[];segments=64;rows=12
    for k in range(rows+1):
        t=k/rows;rx=.093+.172*t;rz=.065+.142*t
        for i in range(segments+1):
            a=.72+(2*math.pi-1.44)*i/segments
            vertices.append([math.sin(a)*rx,.603-.355*t+.018*math.sin(7*a)*t,.036+math.cos(a)*rz])
            uv.append([i/segments,t])
    for k in range(rows):
        for i in range(segments):a=k*(segments+1)+i;c=a+segments+1;faces.extend([[a,c,a+1],[a+1,c,c+1]])
    cloth=[('Bip001 Spine1',.20),('Bip001 Spine',.45),('Bip001 Pelvis',.35)]
    b.mesh('Florielle flowing constellation cape',vertices,faces,navy,cloth,uv=uv)
    lining=np.array(vertices);lining[:,2]-=.002
    b.mesh('Florielle cape rose silk lining',lining,faces,pink,cloth,uv=uv)
    # Surface stars use cape coordinates so the markings sit on its curved face.
    for k in range(18):
        a=1.02+(2*math.pi-2.04)*(k%6)/5;t=.32+.24*(k//6)
        c=np.array([math.sin(a)*(.093+.172*t),.603-.355*t,.036+math.cos(a)*(.065+.142*t)])
        _point(b,'Florielle embroidered cape star',c+[0,0,-.003],.009 if k%3 else .014,gold,cloth)
    for side in ('L','R'):
        b.sleeve(side,cream,long=True,puff=True)
    h=_palm(b,'R');bone='Bip001 R Hand'
    b.tube('Florielle lacquered flower staff',[h+[0,-.34,0],h+[0,.34,0]],[.006,.004],navy,bone,20)
    b.tube('Florielle staff gold collar',[h+[0,.285,0],h+[0,.328,0]],[.013,.014],gold,bone,20)
    _flower(b,'Florielle staff blossom',h+[0,.36,0],.052,cream,gold,bone,6)
    _point(b,'Florielle hanging staff star',h+[.07,.303,0],.022,gold,bone)
    b.tube('Florielle star charm chain',[h+[0,.34,0],h+[.063,.331,0],h+[.07,.316,0]],[.0018]*3,gold,bone)
    book=b.material('Florielle oxblood book','#773c43')
    c=np.array([.132,.39,.109]);v=[c+[x,y,z]for z in (-.018,.018)for y in (-.061,.061)for x in (-.044,.044)]
    faces=[[0,1,3],[0,3,2],[4,6,7],[4,7,5],[0,4,5],[0,5,1],[2,3,7],[2,7,6],[0,2,6],[0,6,4],[1,5,7],[1,7,3]]
    b.mesh('Florielle hip grimoire',v,faces,book,'Bip001 Pelvis')
    _point(b,'Florielle grimoire gold seal',c+[0,0,.019],.021,gold,'Bip001 Pelvis')


def _silk_tier(b,name,top,bottom,rx,rz,mat,phase=0):
    v=[];uv=[];faces=[];segments=96;rows=7
    for k in range(rows+1):
        t=k/rows
        for i in range(segments+1):
            a=2*math.pi*i/segments;front=(1+math.cos(a))/2
            highlow=.125*front**3
            y=top*(1-t)+(bottom+highlow)*t+.010*math.sin(12*a+phase)*t*t
            radius=(.79+.21*t)*(1+.036*math.cos(12*a+phase))
            v.append([math.sin(a)*rx*radius,y,.026+math.cos(a)*rz*radius]);uv.append([i/segments,t])
    for k in range(rows):
        for i in range(segments):a=k*(segments+1)+i;c=a+segments+1;faces.extend([[a,c,a+1],[a+1,c,c+1]])
    # Cloth follows the pelvis with a modest thigh influence on the open front.
    j=np.zeros((len(v),4),np.uint16);w=np.zeros((len(v),4),float)
    for i,q in enumerate(v):
        j[i,:2]=[b.bone['Bip001 Pelvis'],b.bone['Bip001 L Thigh'if q[0]>0 else'Bip001 R Thigh']]
        w[i,:2]=[.94,.06]
    b.mesh(name,v,faces,mat,uv=uv,j=j,w=w)
    lace=b.material('Rosaria pearl lace trim','#eee5f3')
    b.tube(name+' scalloped lace edge',v[-segments-1:],[.0028]*(segments+1),lace,[('Bip001 Pelvis',1.)],seg=8)


def _bride(b,gold,cream):
    silk=b.material('Rosaria ivory silk','#fff8ef',b.clothing_texture('#fff8ef'))
    lilac=b.material('Rosaria lilac undersilk','#dedcf2',b.clothing_texture('#dedcf2'))
    pink=b.material('Rosaria crown velvet','#b95779');leaf=b.material('Rosaria bouquet greenery','#6d946b')
    # Reflect the actual loose back curl islands to balance the donor's side
    # ponytail into the reference's wide cascade. Preserve their UV topology.
    s=b.source(b.c['hair']);sh=next(i for i,n in enumerate(s.doc['nodes'])if n.get('name')=='Bip001 Head'and i in s.world)
    delta=b.headpos-s.world[sh][:3,3];delta[1]+=b.head_adjust
    for p in s.parts():
        if not p['mat']['name'].endswith('_Hair'):continue
        selected=[]
        for g in _groups(p):
            q=p['pos'][np.unique(p['idx'][g])]
            if q[:,0].min()>.115 and q[:,2].max()<-.035 and q[:,1].min()<.65:selected.extend(g)
        if selected:
            pos=p['pos'].copy();pos[:,0]*=-.94;pos[:,2]-=.026;pos+=delta
            im=s.image(p['mat']['pbrMetallicRoughness']['baseColorTexture']['index']);a=np.array(im)
            lum=a[:,:,:3].astype(float)@np.array([.27,.57,.16])/255
            a[:,:,:3]=np.clip(color(b.c['hair_color'])*(.64+.36*lum[:,:,None]),0,255).astype('u1')
            b.mesh('Rosaria reflected loose donor curl cascade',pos,p['idx'][selected,::-1],b.material('Rosaria reflected original hair atlas','#ffffff',Image.fromarray(a)),
                   'Bip001 Head',uv=p['uv'],norm=None)
    # Continuous silk below the overlapping ruffles prevents gaps during poses.
    v=[];uv=[];faces=[];segments=96;rows=24
    for k in range(rows+1):
        t=k/rows;rx=.088+.197*t**.65;rz=.068+.150*t**.65
        for i in range(segments+1):
            a=2*math.pi*i/segments;front=(1+math.cos(a))/2
            v.append([math.sin(a)*rx,.476-.443*t+.122*front**3*t,.026+math.cos(a)*rz])
            uv.append([i/segments,t])
    for k in range(rows):
        for i in range(segments):a=k*(segments+1)+i;c=a+segments+1;faces.extend([[a,c,a+1],[a+1,c,c+1]])
    b.mesh('Rosaria continuous high-low silk foundation',v,faces,silk,'Bip001 Pelvis',uv=uv)
    for k,(top,bottom,rx,rz)in enumerate([(.47,.292,.179,.131),(.375,.209,.222,.162),(.278,.116,.258,.187),(.185,.035,.285,.218)]):
        _silk_tier(b,'Rosaria layered high-low silk '+str(k+1),top,bottom,rx,rz,silk if k<3 else lilac,k*.7)
    b.bare_leg_source(.40,with_feet=True)
    b.bow('Rosaria large draped waist bow',[-.071,.435,.157],.073,silk,'Bip001 Pelvis')
    # The small physical crown replaces the donor's fox ears and floating halo.
    crown_y=b.headpos[1]+.274;crown_x=-.020
    b.ellipsoid('Rosaria crown rose cushion',[crown_x,crown_y+.010,.018],[.065,.033,.051],pink)
    points=[]
    for i in range(81):
        a=2*math.pi*i/80;points.append([crown_x+.071*math.sin(a),crown_y-.014,.018+.055*math.cos(a)])
    b.tube('Rosaria jeweled gold crown band',points,[.004]*len(points),gold)
    jewel=b.material('Rosaria crown turquoise gems','#6bbfc6')
    for k in range(7):
        a=2*math.pi*k/7;c=[crown_x+.07*math.sin(a),crown_y-.012,.018+.056*math.cos(a)]
        b.ellipsoid('Rosaria crown jewel',c,[.007,.009,.006],jewel if k%2 else pink,'Bip001 Head',14,8)
    b.tube('Rosaria crown arched gold finial',[[crown_x-.023,crown_y+.028,.018],[crown_x,crown_y+.068,.018],[crown_x+.023,crown_y+.028,.018]], [.003]*3,gold)
    b.ellipsoid('Rosaria crown pearl',[crown_x,crown_y+.070,.018],[.006]*3,cream,'Bip001 Head',12,6)
    # Necklace conforms to the donor neckline.
    neck=[]
    for i in range(25):
        a=math.pi*i/24;neck.append([.047*math.cos(a),.622-.018*math.sin(a),.047+.025*math.sin(a)])
    b.tube('Rosaria fine gold necklace',neck,[.002]*len(neck),gold,'Bip001 Spine1')
    h=_palm(b,'R');bone='Bip001 R Hand'
    for dx in [-.020,0,.020]:b.tube('Rosaria bouquet stem',[h+[dx*.3,-.049,0],h+[dx,.091,0]],[.0028,.0024],leaf,bone)
    for k in range(7):
        a=k*math.pi/3;c=h+[.042*math.cos(a) if k<6 else 0,.105+.026*math.sin(a) if k<6 else .105,.025]
        _flower(b,'Rosaria layered white rose',c,.026,cream,b.material('Rosaria rose pearl heart','#e3bccc'),bone,7)
    b.bow('Rosaria bouquet silk bow',h+[0,.046,.019],.034,silk,bone)


def outfits(b):
    for p in b.costume_parts:_garment(b,p)
    gold=b.material('Reference accessory gold','#d8b775',metal=.65)
    cream=b.material('Reference ivory pearl','#fff5e7')
    {11:_leatherwork,12:_fox_panels,13:_witch,14:_bride}[b.c['id']](b,gold,cream)
    b.appearance_fit['reference']={'image_index':b.c['id']-10,'construction':'Catalog-selected rigged donor clothing and hair; tailored topology, repainted atlases and fitted original accessories',
                                 'original_sd_proportions':True,'authored_motion_set':['Idle','Walk','Run','Attack','Defend','Victory','Lose']}
