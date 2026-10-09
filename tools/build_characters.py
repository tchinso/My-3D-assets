"""Build original SD costumes around locally supplied, rigged donor parts.

Run with the bundled Python runtime. Sources are read only; generated GLBs have
embedded PNG textures, one compatible skeleton and seven named animation clips.
"""
from __future__ import annotations
import argparse, copy, hashlib, io, json, math, struct, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('C:/Codex/BlueArchive-GLB')
DTYPES = {5121:'u1',5123:'<u2',5125:'<u4',5126:'<f4'}
COMP = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}

def trs(n):
    if 'matrix' in n: return np.array(n['matrix']).reshape(4,4).T
    x,y,z,w=n.get('rotation',[0,0,0,1])
    m=np.array([[1-2*y*y-2*z*z,2*x*y-2*z*w,2*x*z+2*y*w,0],
      [2*x*y+2*z*w,1-2*x*x-2*z*z,2*y*z-2*x*w,0],
      [2*x*z-2*y*w,2*y*z+2*x*w,1-2*x*x-2*y*y,0],[0,0,0,1]],float)
    m[:3,:3] @= np.diag(n.get('scale',[1,1,1]));m[:3,3]=n.get('translation',[0,0,0])
    return m

class Source:
    def __init__(self,name):
        self.name=name;data=(SOURCE/(name+'.glb')).read_bytes();off=12
        while off<len(data):
            size,kind=struct.unpack_from('<II',data,off);chunk=data[off+8:off+8+size];off+=8+size
            if kind==0x4e4f534a:self.doc=json.loads(chunk)
            elif kind==0x004e4942:self.bin=chunk
        self.world={};self.parents={}
        def walk(i,parent):
            self.world[i]=parent@trs(self.doc['nodes'][i])
            for c in self.doc['nodes'][i].get('children',[]):self.parents[c]=i;walk(c,self.world[i])
        for i in self.doc['scenes'][self.doc.get('scene',0)]['nodes']:walk(i,np.eye(4))
    def acc(self,i):
        a=self.doc['accessors'][i];v=self.doc['bufferViews'][a['bufferView']];dt=np.dtype(DTYPES[a['componentType']]);c=COMP[a['type']]
        out=np.ndarray((a['count'],c),dt,self.bin,offset=v.get('byteOffset',0)+a.get('byteOffset',0),strides=(v.get('byteStride',dt.itemsize*c),dt.itemsize)).copy()
        if a.get('normalized'):out=out.astype(float)/np.iinfo(dt).max
        return out
    def image(self,texture):
        im=self.doc['images'][self.doc['textures'][texture]['source']];v=self.doc['bufferViews'][im['bufferView']]
        return Image.open(io.BytesIO(self.bin[v.get('byteOffset',0):v.get('byteOffset',0)+v['byteLength']])).convert('RGBA')
    def parts(self):
        for ni,n in enumerate(self.doc['nodes']):
            if 'mesh' not in n or ni not in self.world or n.get('weights',[0])[0]>0.5:continue
            for p in self.doc['meshes'][n['mesh']]['primitives']:
                a=p['attributes'];pos=self.acc(a['POSITION']).astype(float);norm=self.acc(a['NORMAL']).astype(float)
                j=self.acc(a['JOINTS_0']).astype(int) if 'JOINTS_0'in a else np.zeros((len(pos),4),int)
                w=self.acc(a['WEIGHTS_0']).astype(float) if 'WEIGHTS_0'in a else np.tile([1,0,0,0],(len(pos),1))
                names=[]
                if 'skin'in n:
                    s=self.doc['skins'][n['skin']];ib=self.acc(s['inverseBindMatrices']).reshape(-1,4,4).transpose(0,2,1)
                    mats=np.array([self.world[bi]@ib[k]for k,bi in enumerate(s['joints'])]);blend=(mats[j]*w[:,:,None,None]).sum(axis=1)
                    pos=np.einsum('nij,nj->ni',blend,np.c_[pos,np.ones(len(pos))])[:,:3]
                    norm=np.einsum('nij,nj->ni',blend[:,:3,:3],norm);names=[self.doc['nodes'][bi]['name']for bi in s['joints']]
                else:
                    pos=(np.c_[pos,np.ones(len(pos))]@self.world[ni].T)[:,:3];norm=norm@self.world[ni][:3,:3].T
                idx=self.acc(p['indices']).reshape(-1,3).astype(int);mat=self.doc['materials'][p.get('material',0)]
                yield {'name':n.get('name',''),'mat':mat,'pos':pos,'norm':norm,'uv':self.acc(a['TEXCOORD_0']) if 'TEXCOORD_0'in a else np.zeros((len(pos),2)), 'j':j,'w':w,'names':names,'idx':idx,'node':ni}

def rgb(h):return np.array([int(h[i:i+2],16)for i in (1,3,5)],float)/255

DESIGNS=[
 dict(id=1,slug='01_marine_maid',name='Marin',name_ko='마린',tagline='Tea service · ribbon rapier',hair='Hatsune Miku',face='Momoi (Maid)',hair_color='#ed9bc2',palette=['#f7f6ff','#192944','#ed9bc2','#9ec9e9'],style='maid',legs='white',attack='rapier',design='분홍 트윈테일을 실제 곱슬 머리 락으로 조합해 풍성한 굵기를 유지한 긴 머리에 한두 번의 가벼운 꼬임을 넣고 곡선 아호게를 추가. 섬세한 땋은 뿌리·옆머리, 남색 리본과 작은 진주, 찻잔·숟가락 머리 참. 흰색·남색 메이드 드레스와 흰 팬티스타킹, 물결 프릴 앞치마와 차 숟가락 모양 레이피어.'),
 dict(id=2,slug='02_azure_reaper',name='Viola',name_ko='비올라',tagline='Blue rose · crescent scythe',hair='Erika',face='Haruka (Dress)',hair_color='#5456c9',palette=['#44336f','#293d80','#467bdb','#5456c9'],style='reaper',legs='thigh',attack='scythe',design='참고 이미지처럼 왕실 파랑·보라색의 짧은 레이어드 단발, 옆으로 흐르는 앞머리와 얼굴을 감싸는 옆머리, 바깥으로 뻗는 끝과 곡선 아호게. 한쪽 커다란 파란 장미, 파랑·보라 짧은 치마, 진파랑 사이하이와 달 모양 낫.'),
 dict(id=3,slug='03_sky_cardigan',name='Sora',name_ko='소라',tagline='Azure waves · scarlet tartan',hair='Azusa (Swimsuit)',face='Nonomi',hair_color='#9dcef0',palette=['#8f919b','#20212b','#ac334c','#9dcef0'],style='reference_school',legs='bare',attack='magic',design='첨부 이미지에 맞춘 하늘색 긴 레이어드 웨이브와 뾰족한 중앙 앞머리, 한쪽 파란 꽃과 작은 땋은 머리. 검정 테두리의 회색 블레이저, 흰 셔츠, 빨강·검정 체크 넥타이와 플리츠 스커트, 맨다리.'),
 dict(id=4,slug='04_tidal_dress',name='Elise',name_ko='엘리제',tagline='Tidal silk · sapphire pendant',hair='Shokuhou Misaki',face='Seia',hair_color='#f4d58d',palette=['#fbfcff','#3d72b2','#93c1e2','#f4d58d'],style='dress',legs='white',attack='magic',design='금발 긴 생머리, 흰색·파랑 원피스와 흰 팬티스타킹. 겹쳐진 시폰 밑단과 투명 레이스, 가슴 장식과 허리 리본.'),
 dict(id=5,slug='05_rosy_blazer',name='Rina',name_ko='리나',tagline='Rose academy · ribbon tie',hair='Miyako',face='Koharu',hair_color='#f2bdcf',palette=['#64465d','#f7eff3','#d697b4','#344c68'],style='blazer',legs='bare',attack='magic',design='연분홍 긴 생머리와 한쪽 리본 묶음, 슬림한 몸통·소매·다리와 블레이저 교복, 맨다리. 넓은 라펠, 목 리본과 배지, 플리츠 스커트와 연분홍 운동화.'),
 dict(id=6,slug='06_clover_sprite',name='Fennel',name_ko='페넬',tagline='Wingless sprite · clover wand',hair='Erika',face='Natsu',hair_color='#f5fff5',palette=['#f5fff4','#a4cb74','#537f53','#efe2a3'],style='sprite',legs='bare',attack='magic',design='흰색 짧은 머리, 날개 없는 요정. 연두·흰색 호박팬츠와 잎사귀 칼라, 맨다리·맨발. 클로버 지팡이와 이슬 방울 장식.'),
 dict(id=7,slug='07_neon_cat',name='Momo',name_ko='모모',tagline='City cat · cropped camisole',hair='Miyo',face='Miyo',hair_color='#f4b5d0',palette=['#fff5fa','#ed98bd','#242335','#a48dce'],style='cat',legs='black',attack='punch',design='참고 이미지의 분홍 긴 레이어드 머리와 부드러운 앞머리, 양옆 땋은 번, 고양이 귀와 밝은 연보라 눈. 배꼽이 보이는 흰·분홍 현대 의상, 검정 팬티스타킹. 분홍 오픈 재킷, 크롭 캐미솔과 흰 쇼츠.'),
 dict(id=8,slug='08_carmine_doll',name='Rosette',name_ko='로제트',tagline='Ribbon doll · winding key',hair='Reisa (Magical)',face='Reisa (Magical)',hair_color='#f5c3d3',palette=['#ca3550','#fff5ef','#f5c3d3','#91ded9','#d2af67'],style='doll',legs='white',attack='magic',design='참고 이미지처럼 실제 나선 머리 락을 양쪽에 조합한 풍성한 파스텔 분홍 트윈테일, 두 번의 넓은 입체 꼬임과 민트·아쿠아 그라데이션 끝. 이마 중앙의 넓은 C자 앞머리 컬과 목 옆으로 길게 흐르는 분홍 옆머리. 빨강·흰색 인형 드레스와 흰 팬티스타킹, 이중 프릴과 레이스 리본, 등 뒤 작은 태엽 장식.'),
 dict(id=9,slug='09_crimson_qipao',name='Meilin',name_ko='메이린',tagline='Scarlet peony · folding fan',hair='Serika (Swimsuit)',face='Kisaki',hair_color='#35272c',palette=['#b52139','#e7585c','#e3b764','#35272c'],style='qipao',legs='bare',attack='fan',design='참고 이미지처럼 굵고 긴 검갈색 트윈테일과 양쪽 묶음의 붉은 꽃리본·금색 장식. 옆트임이 뚜렷한 짧은 빨강 치파오와 맨다리, 금색 매듭과 모란 무늬, 접이식 부채.'),
 dict(id=10,slug='10_snow_buns',name='Nevia',name_ko='네비아',tagline='Snow cloud · fur shawl',hair='Kirara',face='Seia',hair_color='#f3f3fc',palette=['#fbfbff','#dce0ef','#b7bfda','#f1dcea'],style='snow',legs='white',attack='magic',design='흰색 풍성한 긴 머리와 양쪽 번, 짧고 부드러운 흰 옷, 흰 팬티스타킹. 구름 모양 퍼 숄, 겹친 드레스 주름과 금빛 장식.'),
]

# Actual garment topology and painted details, selected from the supplied catalog.
COSTUME_SOURCES={1:'Momoi (Maid)',2:'Haruka (Dress)',3:'Serika',4:'Sena (Casual)',5:'Reisa',6:'Ibuki',7:'Saori (Swimsuit)',8:'Reisa (Magical)',9:'Kisaki',10:'Mutsuki (Dress)'}
from reference_characters import DESIGNS as REFERENCE_DESIGNS, COSTUME_SOURCES as REFERENCE_COSTUMES
DESIGNS.extend(REFERENCE_DESIGNS)
COSTUME_SOURCES.update(REFERENCE_COSTUMES)

def components(pos,idx,weld=False):
    """Triangle components; welding is reserved for the seam-split qipao coat."""
    used=np.unique(idx);parent={int(x):int(x)for x in used}
    def find(x):
        while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
        return x
    def union(a,b):
        a,b=find(int(a)),find(int(b))
        if a!=b:parent[b]=a
    if weld:
        at={}
        for x in used:
            key=tuple(np.round(pos[x],5))
            if key in at:union(int(x),at[key])
            else:at[key]=int(x)
    for a,b,c in idx:union(a,b);union(a,c)
    groups={}
    for k,t in enumerate(idx):groups.setdefault(find(int(t[0])),[]).append(k)
    return [np.array(v,int)for v in groups.values()]

class Builder:
    def __init__(self,cfg):
        self.c=cfg;self.data=bytearray();self.doc={'asset':{'version':'2.0','generator':'My-3D-assets original costume kitbash pipeline'},'scene':0,'scenes':[{'nodes':[]}],'nodes':[],'meshes':[],'materials':[],'textures':[],'images':[],'samplers':[{'magFilter':9729,'minFilter':9987,'wrapS':10497,'wrapT':10497}],'bufferViews':[],'accessors':[],'skins':[]}
        self.mat_cache={};self.sources={};self.bone={};self.world={};self.joint=[];self.src=Source(COSTUME_SOURCES[cfg['id']])
        self.costume_parts=[p for p in self.src.parts() if ('body'in p['name'].lower() or 'jacket'in p['name'].lower()) and not any(t in p['mat']['name'].lower()for t in ['hair','face','eye','mouth','weapon','halo'])]
        body=max((p for p in self.costume_parts if p['mat']['name'].endswith('_Body')),key=lambda p:len(p['idx']))
        needed=set()
        for p in self.costume_parts:
            node=self.src.doc['nodes'][p['node']]
            if 'skin'in node:needed.update(self.src.doc['skins'][node['skin']]['joints'])
        # Hand/finger bones can be unweighted in a garment but still drive props.
        source_head=next(i for i in needed if self.src.doc['nodes'][i].get('name')=='Bip001 Head')
        main_root=source_head
        while main_root in self.src.parents and self.src.doc['nodes'][main_root].get('name')!='Bip001':main_root=self.src.parents[main_root]
        def standard_descendants(i):
            if self.src.doc['nodes'][i].get('name','').startswith('Bip001'):needed.add(i)
            for child in self.src.doc['nodes'][i].get('children',[]):standard_descendants(child)
        standard_descendants(main_root)
        for i in list(needed):
            while i in self.src.parents:i=self.src.parents[i];needed.add(i)
        remap={i:k for k,i in enumerate(sorted(needed))}
        self.source_node_map=remap
        for i in sorted(needed):
            n=copy.deepcopy(self.src.doc['nodes'][i]);n.pop('mesh',None);n.pop('skin',None);n.pop('weights',None)
            n['children']=[remap[k]for k in n.get('children',[])if k in remap]
            if not n['children']:n.pop('children')
            ni=len(self.doc['nodes']);self.doc['nodes'].append(n);self.world[ni]=self.src.world[i];self.bone[n.get('name',f'b{ni}')]=ni
            if self.src.parents.get(i)not in needed:self.doc['scenes'][0]['nodes'].append(ni)
        self.joint=list(range(len(self.doc['nodes'])));self.head=self.bone['Bip001 Head'];self.headpos=self.world[self.head][:3,3]
        self.main_body=body
        # Match the actual chin and neck surfaces, not two exporters' Head pivots.
        def face_chin(s):
            candidates=[p for p in s.parts()if 'face'in p['mat']['name'].lower()and not any(t in p['mat']['name'].lower()for t in ['eye','mouth'])]
            face=max(candidates,key=lambda p:len(p['idx']));return float(face['pos'][np.unique(face['idx']),1].min())
        reference_chin=face_chin(self.src);face_source=self.source(cfg['face']);fh=next(i for i,n in enumerate(face_source.doc['nodes'])if n.get('name')=='Bip001 Head'and i in face_source.world)
        body_image=self.src.image(body['mat']['pbrMetallicRoughness']['baseColorTexture']['index']);array=np.array(body_image);used=np.unique(body['idx']);uv=body['uv'][used];xy=np.clip((uv*np.array(body_image.size)).astype(int),0,np.array(body_image.size)-1);col=array[xy[:,1],xy[:,0],:3].astype(float);p=body['pos'][used]
        skin=(col[:,0]>165)&(col[:,1]>125)&(col[:,2]>110)&(col[:,0]>=.98*col[:,1])&(col[:,0]>1.025*col[:,2])
        neck=skin&(np.abs(p[:,0])<.055)&(p[:,1]>self.headpos[1]-.08)&(p[:,1]<self.headpos[1]+.065)
        neck_top=float(p[neck,1].max())if neck.any()else reference_chin
        target_chin=min(reference_chin,neck_top-.005)-.008
        self.head_adjust=target_chin-(face_chin(face_source)+self.headpos[1]-face_source.world[fh][1,3])
        self.head_fit={'neck_top':neck_top,'chin_target':target_chin,'vertical_adjustment':float(self.head_adjust)}
        self.appearance_fit={}
    def view(self,b,target=None):
        while len(self.data)%4:self.data.append(0)
        v={'buffer':0,'byteOffset':len(self.data),'byteLength':len(b)}
        if target:v['target']=target
        self.doc['bufferViews'].append(v);self.data.extend(b);return len(self.doc['bufferViews'])-1
    def acc(self,a,typ,component_type=5126):
        a=np.asarray(a,dtype=DTYPES[component_type]);a=a.reshape(-1,COMP[typ]);v=self.view(a.tobytes());d={'bufferView':v,'componentType':component_type,'count':len(a),'type':typ}
        if typ=='SCALAR' or typ=='VEC3':d['min']=a.min(axis=0).tolist();d['max']=a.max(axis=0).tolist()
        self.doc['accessors'].append(d);return len(self.doc['accessors'])-1
    def material(self,name,color,image=None,metal=0):
        if name in self.mat_cache:return self.mat_cache[name]
        p={'baseColorFactor':[*rgb(color),1],'metallicFactor':metal,'roughnessFactor':.65 if not metal else .32}
        if image is not None:
            b=io.BytesIO();image.save(b,format='PNG');self.doc['images'].append({'name':name,'mimeType':'image/png','bufferView':self.view(b.getvalue())});self.doc['textures'].append({'sampler':0,'source':len(self.doc['images'])-1});p['baseColorTexture']={'index':len(self.doc['textures'])-1};p['baseColorFactor']=[1,1,1,1]
        mat={'name':name,'pbrMetallicRoughness':p,'doubleSided':True}
        if image is not None and image.getextrema()[3][0]<250:mat.update(alphaMode='MASK',alphaCutoff=.4)
        idx=len(self.doc['materials']);self.doc['materials'].append(mat);self.mat_cache[name]=idx;return idx
    def bone_weights(self,pos,kind):
        j=np.zeros((len(pos),4),np.uint16);w=np.zeros((len(pos),4),float);w[:,0]=1
        if isinstance(kind,str):j[:,0]=self.bone[kind]
        elif isinstance(kind,int):j[:,0]=kind
        else:
            for k,(name,value) in enumerate(kind):j[:,k]=self.bone[name];w[:,k]=value
            w[:,len(kind):]=0
        return j,w
    def mesh(self,name,pos,idx,mat,bones='Bip001 Spine1',uv=None,norm=None,j=None,w=None):
        pos=np.asarray(pos,float);idx=np.asarray(idx,np.uint32).reshape(-1,3)
        if not len(idx):return
        used=np.unique(idx)
        if len(used)<len(pos):
            slots=np.full(len(pos),-1,int);slots[used]=np.arange(len(used));idx=slots[idx].astype(np.uint32);pos=pos[used]
            if uv is not None:uv=np.asarray(uv)[used]
            if norm is not None:norm=np.asarray(norm)[used]
            if j is not None:j=np.asarray(j)[used];w=np.asarray(w)[used]
        if norm is None:
            norm=np.zeros_like(pos);n=np.cross(pos[idx[:,1]]-pos[idx[:,0]],pos[idx[:,2]]-pos[idx[:,0]])
            for k in range(3):np.add.at(norm,idx[:,k],n)
            norm/=np.maximum(np.linalg.norm(norm,axis=1)[:,None],1e-9)
        norm=np.asarray(norm,float);length=np.linalg.norm(norm,axis=1);norm[length<1e-8]=[0,0,1];norm/=np.linalg.norm(norm,axis=1)[:,None]
        if j is None:j,w=self.bone_weights(pos,bones)
        j=np.array(j,dtype=np.uint16,copy=True);w=np.array(w,dtype=float,copy=True)
        # Retargeting may map two source slots to one bone; merge their weights.
        for a in range(4):
            for b in range(a+1,4):
                same=(j[:,a]==j[:,b]);w[same,a]+=w[same,b];w[same,b]=0
        w/=np.maximum(w.sum(axis=1)[:,None],1e-12);j[w<1e-8]=0
        if uv is None:uv=np.c_[pos[:,0]*3,pos[:,1]*3]
        attrs={'POSITION':self.acc(pos,'VEC3'),'NORMAL':self.acc(norm,'VEC3'),'TEXCOORD_0':self.acc(uv,'VEC2'),'JOINTS_0':self.acc(j,'VEC4',5123),'WEIGHTS_0':self.acc(w,'VEC4')}
        self.doc['meshes'].append({'name':name,'primitives':[{'attributes':attrs,'indices':self.acc(idx.reshape(-1),'SCALAR',5125),'material':mat}]})
        ni=len(self.doc['nodes']);self.doc['nodes'].append({'name':name,'mesh':len(self.doc['meshes'])-1,'skin':0});self.doc['scenes'][0]['nodes'].append(ni)
    def source(self,name):
        if name not in self.sources:self.sources[name]=Source(name)
        return self.sources[name]
    def map_bones(self,p,s,delta):
        out={}
        head_source=next(i for i,n in enumerate(s.doc['nodes'])if n.get('name')=='Bip001 Head' and i in s.world)
        source_head=s.world[head_source]
        def add(name):
            scoped=name if s.name==self.src.name or name.startswith('Bip001') or name in ('bone_root','RootNode') else s.name+'::'+name
            if scoped in self.bone:return self.bone[scoped]
            source_i=next((i for i,n in enumerate(s.doc['nodes'])if n.get('name')==name and i in s.world),None)
            if source_i is None:return self.head
            parent=s.parents.get(source_i);parentname=s.doc['nodes'][parent].get('name') if parent is not None else 'Bip001 Head'
            parentnew=add(parentname) if parentname not in ('bone_root','RootNode') else self.head
            world=s.world[source_i].copy();world[:3,3]+=delta
            local=np.linalg.inv(self.world[parentnew])@world
            ni=len(self.doc['nodes']);self.doc['nodes'].append({'name':scoped,'matrix':local.T.reshape(-1).tolist()});self.doc['nodes'][parentnew].setdefault('children',[]).append(ni)
            self.bone[scoped]=ni;self.world[ni]=world;self.joint.append(ni);return ni
        for k,name in enumerate(p['names']):out[k]=add(name)
        return np.array([out.get(k,self.head)for k in p['j'].reshape(-1)],np.uint16).reshape(-1,4)
    def add_source(self,p,s,mode):
        idx=p['idx'].copy();pos=p['pos'].copy();norm=p['norm'].copy();uv=p['uv'].copy();weights=p['w'].copy()
        if mode=='hair' and self.c['id']in(1,2,8):
            from personality_hair import select_and_fit
            pos,idx=select_and_fit(self,p,s,components(pos,idx));norm=None
        if mode=='hair' and self.c['id']>=11:
            from reference_characters import hair_selection
            pos,idx=hair_selection(self,p,s,components(pos,idx))
            norm=None
        if mode=='hair' and self.c['id']==3:
            from hair_filters import hair_indices
            idx=hair_indices(p,s.name,'back'if s.name=='Miyo'else'front')
        if mode=='hair' and self.c['id']==7:
            from hair_filters import hair_indices
            selection={'Miyo':'front','Kirara':'back','Kazusa':'ears'}[s.name]
            idx=hair_indices(p,s.name,selection,components(pos,idx))
        if mode=='hair' and self.c['id']==9:
            from hair_filters import thicken_twintails
            pos=thicken_twintails(p,s.name,components(pos,idx));norm=None
            self.appearance_fit['hair']={'method':'Donor twin-tail cross-section fit, anchored roots and tapered ends','width_scale_max':1.72,'depth_scale_max':1.38,'length_scale':1.0}
        delta=np.zeros(3)
        if mode!='skin':
            sh=next(i for i,n in enumerate(s.doc['nodes'])if n.get('name')=='Bip001 Head' and i in s.world);delta=self.headpos-s.world[sh][:3,3];delta[1]+=self.head_adjust;pos+=delta
        cent=pos[idx].mean(axis=1)
        if mode=='skin':idx=idx[(cent[:,1]<.688)&(cent[:,1]>.035)]
        if mode=='hair' and self.c['id']==9:
            dominant=p['j'][np.arange(len(pos)),p['w'].argmax(axis=1)]
            ear=np.array(['ear'in p['names'][k].lower()for k in dominant]);idx=idx[~ear[idx].any(axis=1)]
        if mode=='hair' and s.name=='Noa':
            keep=np.ones(len(idx),bool)
            for group in components(pos,idx):
                if len(np.unique(idx[group]))<=4:keep[group]=False
            idx=idx[keep]
        if not len(idx):return
        used=np.unique(idx);inv=np.full(len(pos),-1,int);inv[used]=np.arange(len(used));idx=inv[idx];pos=pos[used];norm=norm[used]if norm is not None else None;uv=uv[used];weights=weights[used]
        j=self.map_bones(p,s,delta)[used]
        if mode=='skin':
            # Remove printed swimsuit colours underneath opaque original garments.
            im=Image.new('RGBA',(64,64),(252,220,209,255))
            leg=self.c['legs'];name='Skin / warm porcelain'
            # Split leg surfaces into dedicated physical legwear material ranges.
            legtri=(pos[idx].mean(axis=1)[:,1]<.36)&(np.abs(pos[idx].mean(axis=1)[:,0])<.15)
            self.mesh('Donor anatomy / exposed limbs',pos,idx[~legtri],self.material(name,'#ffffff',im),j=j,w=weights,uv=uv,norm=norm)
            legidx=idx[legtri]
            if leg=='thigh':
                low=pos[legidx].mean(axis=1)[:,1]<.286
                self.mesh('Bare upper thighs',pos,legidx[~low],self.material(name,'#ffffff',im),j=j,w=weights,uv=uv,norm=norm);legidx=legidx[low]
            color={'white':'#f6f2fa','black':'#292432','thigh':'#253973','bare':'#fcdcd1'}[leg]
            lm=self.material('Legwear / '+leg,color)
            self.mesh('Legs / '+leg,pos,legidx,lm,j=j,w=weights,uv=uv,norm=norm);return
        mat=p['mat'];texture=mat.get('pbrMetallicRoughness',{}).get('baseColorTexture');im=s.image(texture['index']) if texture else None
        if im and mat.get('alphaMode','OPAQUE')=='OPAQUE':im.putalpha(255)
        if mode=='hair' and im:
            if self.c['id']in(1,2,8):
                from personality_hair import recolor
                im=recolor(self,p,im)
            else:
                a=np.array(im);lum=(a[:,:,:3].astype(float)@np.array([.27,.57,.16]))/255
                col=rgb(self.c['hair_color']);shade=.64+.36*lum
                a[:,:,:3]=np.clip(col[None,None,:]*shade[:,:,None]*255,0,255).astype('u1');im=Image.fromarray(a)
        if mode=='face' and self.c['id']==3 and im:
            a=np.array(im);col=a[:,:,:3].astype(float);r,g,b=col.transpose(2,0,1)
            iris=(g>r*1.2)&(g>b*1.15)&(g>65)
            lum=col@np.array([.27,.57,.16])/255
            a[:,:,:3][iris]=np.clip(rgb('#e9bd6b')*(.4+.6*lum[iris,None])*255,0,255).astype('u1');im=Image.fromarray(a)
        if mode=='face' and self.c['id']==7 and im:
            # Miyo's eye atlas retains its painted reflections, lashes and blush.
            # Recolour only the golden iris pigments to the reference's lilac.
            a=np.array(im);col=a[:,:,:3].astype(float);r,g,b=col.transpose(2,0,1)
            iris=(r>70)&(g>40)&(b<g*.78)&(g<r*.99)
            lum=col@np.array([.27,.57,.16])/255
            a[:,:,:3][iris]=np.clip(rgb('#aa91e8')*(.38+.72*lum[iris,None])*255,0,255).astype('u1');im=Image.fromarray(a)
        if mode=='face' and self.c['id']>=11 and im:
            from reference_characters import tint_eyes
            im=tint_eyes(im,self.c['eye_color'])
        if mode=='hair' and self.c['id']==8 and im:
            from personality_hair import emit_rosette
            if emit_rosette(self,p,s,pos,idx,uv,norm,j,weights,used,im):return
        mi=self.wardrobe_material(s.name+'/'+mat['name']+'/'+mode,p,im)
        self.mesh(('Hair / ' if mode=='hair'else'Face / ')+s.name+' / '+mat['name'],pos,idx,mi,j=j,w=weights,uv=uv,norm=norm)
    def head_parts(self):
        secondary={1:['Erika','Yoshimi'],3:['Miyo'],7:['Kirara','Kazusa'],8:['Seia (Swimsuit)','Erika']}.get(self.c['id'],[])
        parts_to_import=[('hair',self.c['hair'])]+[('hair',name)for name in secondary]+[('face',self.c['face'])]
        for mode,name in parts_to_import:
            s=self.source(name)
            parts=list(s.parts());mouth=False
            for p in parts:
                mn=p['mat']['name'].lower();nn=p['name'].lower()
                if mode=='hair' and 'hair'in mn and ('body'in nn or 'hair'in nn):
                    self.add_source(p,s,mode)
                    if self.c['id']==8 and s.name=='Seia (Swimsuit)':
                        from personality_hair import add_mirrored_rosette_tail
                        add_mirrored_rosette_tail(self,p,s)
                if mode=='face' and (('face'in mn or 'eyebrow'in mn or 'eyemouth'in mn) and ('body'in nn or 'face'in nn or 'mouth'in nn)):
                    if nn.startswith('mouth'):
                        if mouth:continue
                        mouth=True
                        if self.c['id']==7:
                            # Select Miyo's existing closed smile atlas instead
                            # of the exported default frown; keep its UV plane.
                            p=p.copy();p['mat']=next(m for m in s.doc['materials']if m['name'].endswith('_Mouth_300'))
                            self.appearance_fit['face']={'donor_expression':'Miyo Mouth_300 closed smile','iris_tint':'#aa91e8','painted_highlights':'preserved'}
                    self.add_source(p,s,mode)
        if self.c['id']in(1,2,8):
            from personality_hair import fit_rest_pivots
            fit_rest_pivots(self)
        if self.c['id']==11:
            from reference_characters import fit_hair_pivots
            fit_hair_pivots(self)
    def lathe(self,name,rings,mat,bones='Bip001 Spine',segments=72,pleats=0,slit=False,center=(0,.045)):
        pos=[];uv=[];idx=[]
        for k,(y,rx,rz)in enumerate(rings):
            for i in range(segments+1):
                t=2*math.pi*i/segments;f=1+pleats*math.cos(t*12)
                pos.append([center[0]+math.sin(t)*rx*f,y,center[1]+math.cos(t)*rz*f]);uv.append([i/segments,k/max(1,len(rings)-1)])
        for k in range(len(rings)-1):
            for i in range(segments):
                t=2*math.pi*(i+.5)/segments
                if slit and k>=1 and abs(math.sin(t))>.82:continue
                a=k*(segments+1)+i;b=a+segments+1;idx.extend([[a,b,a+1],[a+1,b,b+1]])
        self.mesh(name,pos,idx,mat,bones,uv=uv)
    def ellipsoid(self,name,center,radii,mat,bones='Bip001 Head',seg=24,rings=12):
        center=np.array(center,float)
        if isinstance(bones,str) and ('Spine'in bones or 'Pelvis'in bones) and center[2]>0 and 'lace'not in name.lower() and 'cuffs'not in name.lower():center[2]+=.065
        p=[];f=[]
        for j in range(rings+1):
            th=math.pi*j/rings
            for i in range(seg+1):
                ph=2*math.pi*i/seg;p.append(np.array(center)+np.array(radii)*[math.sin(th)*math.cos(ph),math.cos(th),math.sin(th)*math.sin(ph)])
        for j in range(rings):
            for i in range(seg):a=j*(seg+1)+i;b=a+seg+1;f.extend([[a,a+1,b],[a+1,b+1,b]])
        self.mesh(name,p,f,mat,bones)
    def tube(self,name,points,radii,mat,bones='Bip001 Head',seg=12):
        points=np.array(points,float);p=[];f=[]
        if isinstance(bones,str) and 'Spine'in bones and (points[:,2]>0).all():points[:,2]+=.065
        for k,point in enumerate(points):
            axis=points[min(k+1,len(points)-1)]-points[max(k-1,0)];axis/=max(np.linalg.norm(axis),1e-9);ref=np.array([0,1,0])if abs(axis[1])<.9 else np.array([1,0,0]);u=np.cross(axis,ref);u/=np.linalg.norm(u);v=np.cross(axis,u)
            for i in range(seg):t=2*math.pi*i/seg;p.append(point+radii[k]*(math.cos(t)*u+math.sin(t)*v))
        for k in range(len(points)-1):
            for i in range(seg):a=k*seg+i;an=k*seg+(i+1)%seg;b=a+seg;bn=an+seg;f.extend([[a,an,b],[an,bn,b]])
        f.extend([[0,i+1,i]for i in range(1,seg-1)]);a=(len(points)-1)*seg;f.extend([[a,a+i,a+i+1]for i in range(1,seg-1)])
        self.mesh(name,p,f,mat,bones)
    def patch(self,name,points,mat,bones='Bip001 Spine1'):
        points=np.array(points,float)
        if isinstance(bones,str) and ('Spine'in bones or 'Pelvis'in bones):points[points[:,2]>0,2]+=.065
        self.mesh(name,points,[[0,i,i+1]for i in range(1,len(points)-1)],mat,bones)
    def bow(self,name,c,size,mat,bones='Bip001 Head'):
        x,y,z=c;s=size
        for side in [-1,1]:
            self.patch(name+' loop',[[x,y,z+.004],[x+side*s,y+s*.55,z],[x+side*s*1.18,y-s*.55,z],[x,y-s*.12,z+.004]],mat,bones)
            self.patch(name+' tail',[[x,y,z],[x+side*s*.28,y-s*1.3,z-.006],[x+side*s*.7,y-s*1.12,z]],mat,bones)
        self.ellipsoid(name+' knot',c,[s*.22,s*.25,s*.15],mat,bones)
    def hem(self,name,y,rx,rz,mat,bones='Bip001 Pelvis',n=30):
        for i in range(n):
            t=2*math.pi*i/n;self.ellipsoid(name,(rx*math.sin(t),y,.045+rz*math.cos(t)),(.015,.009,.012),mat,bones,seg=10,rings=5)
    def sleeve(self,side,mat,long=False,puff=False):
        upper=f'Bip001 {side} UpperArm';fore=f'Bip001 {side} Forearm';hand=f'Bip001 {side} Hand';a=self.world[self.bone[upper]][:3,3];b=self.world[self.bone[fore]][:3,3];c=self.world[self.bone[hand]][:3,3]
        if long:
            self.tube(side+' upper sleeve',[a,a*.4+b*.6,b],[.047,.055 if puff else .041,.039],mat,upper,18)
            self.tube(side+' lower sleeve',[b,b*.3+c*.7,c],[.04,.034,.027],mat,fore,18)
        else:self.tube(side+' short sleeve',[a,a*.35+b*.65],[.045,.062 if puff else .039],mat,upper,18)
    def clothing_texture(self,color,pattern=None):
        base=tuple((rgb(color)*255).astype(int));im=Image.new('RGBA',(512,512),(*base,255));d=ImageDraw.Draw(im)
        if pattern=='check':
            for i in range(0,512,64):d.rectangle((i,0,i+14,511),fill=(217,176,196,255));d.rectangle((0,i,511,i+14),fill=(236,214,224,255))
        if pattern=='peony':
            for x,y in [(120,100),(345,240),(170,400)]:
                for a in range(6):t=a*math.pi/3;cx=x+math.cos(t)*23;cy=y+math.sin(t)*23;d.ellipse((cx-23,cy-25,cx+23,cy+25),outline=(243,166,130,255),width=3)
                d.ellipse((x-13,y-13,x+13,y+13),fill=(230,186,94,255))
        # Subtle textile striations keep the large original garment surfaces legible.
        a=np.array(im);shade=(.96+.04*np.cos(np.arange(512)*2*math.pi/64))[None,:,None];a[:,:,:3]=(a[:,:,:3]*shade).astype('u1');return Image.fromarray(a)
    def costume_texture(self,p):
        """Repaint textile hue while retaining the source's seams and painted folds."""
        texture=p['mat']['pbrMetallicRoughness']['baseColorTexture']['index'];im=self.src.image(texture)
        a=np.array(im);color=a[:,:,:3].astype(float);r,g,b=color.transpose(2,0,1);lum=color@np.array([.27,.57,.16])/255
        skin=(r>165)&(g>125)&(b>110)&(r-g>8)&(r>b*1.025)&((r-g)<75)
        white=(np.min(color,axis=2)>185)&((np.max(color,axis=2)-np.min(color,axis=2))<35)
        gold=(r>145)&(g>105)&(b<g*.74)&(r>g*.94)
        def tint(mask,target,raised=False):
            mask=mask&~skin&~gold
            if not mask.any():return
            reference=max(float(np.quantile(lum[mask],.80)),.02)
            shade=np.clip(lum/reference,.12,1.1)
            if raised:shade=.70+.30*np.minimum(shade,1)
            a[:,:,:3][mask]=np.clip(rgb(target)*shade[mask,None]*255,0,255).astype('u1')
        style=self.c['style']
        if style=='maid':tint((g>r+35)&(b>r+35),'#9acde3')
        elif style=='reaper':tint((b>r+6)&(b>g+8),'#3d538a'if 'alpha'in p['mat']['name'].lower()else '#493969')
        elif style=='cardigan':
            yellow=(r>140)&(np.abs(r-g)<30)&(g-b>22)
            # This pastel yellow is the cardigan fabric, rather than metallic trim.
            mask=yellow&(r-g<12);reference=max(float(np.quantile(lum[mask],.8)),.01)if mask.any()else 1
            a[:,:,:3][mask]=np.clip(rgb('#b0d9ed')*(lum[mask,None]/reference)*255,0,255).astype('u1')
            tint((np.max(color,axis=2)<115)&(b>r-5),'#335576')
        elif style=='dress':tint((b>r+6)&(b>g+3),'#a2cce8')
        elif style=='blazer':tint((b>r+5)&(b>g+3)&~white,'#65516c')
        elif style=='sprite':
            tint((np.max(color,axis=2)<135)&~white,'#eff7e9',True)
            tint((r>g+25)&~skin,'#8dae6c',True)
            yy,xx=np.indices(a.shape[:2]);u=xx/a.shape[1];v=yy/a.shape[0]
            mask=(u>.12)&(u<.24)&(v>.535)&(v<.575)&~skin
            a[:,:,:3][mask]=np.clip(rgb('#a6c87b')*(.72+.28*lum[mask,None])*255,0,255).astype('u1')
        elif style=='cat':
            tint((g>r+10)&(g>b-8),'#e8a1c1',True)
            tint((np.max(color,axis=2)<130)&~white,'#f8f3fa',True)
            tint((b>r+8)&(b>g-5)&~white,'#eadce9',True)
        elif style=='doll':tint((b>r+10)&(b>g+8),'#c33b58')
        elif style=='qipao':
            tint((b>r+7)&(b>g+7),'#b32940')
            tint((b>r+25)&(g>r+10)&(g>120),'#d5ae65',True)
        elif style=='snow':
            tint((r-g>25)&(b-g>12)&~skin,'#f7f5ff',True)
            tint((np.max(color,axis=2)<125)&~white,'#bcc5df',True)
        alpha=p['mat'].get('alphaMode','OPAQUE')
        if alpha=='OPAQUE':a[:,:,3]=255
        from costume_filters import repaint_marks
        return repaint_marks(self.c['id'], p['mat']['name'], Image.fromarray(a))
    def wardrobe_material(self,name,p,im):
        mi=self.material(name,'#ffffff',im);m=self.doc['materials'][mi]
        m['alphaMode']=p['mat'].get('alphaMode','OPAQUE');m['doubleSided']=p['mat'].get('doubleSided',True)
        if m['alphaMode']=='MASK':m['alphaCutoff']=p['mat'].get('alphaCutoff',.5)
        else:m.pop('alphaCutoff',None)
        m['pbrMetallicRoughness']['roughnessFactor']=p['mat']['pbrMetallicRoughness'].get('roughnessFactor',.85)
        return mi
    def leg_texture(self,p,color):
        im=self.src.image(p['mat']['pbrMetallicRoughness']['baseColorTexture']['index']);a=np.array(im);lum=np.array(im.convert('L').filter(ImageFilter.GaussianBlur(3))).astype(float)/255
        a[:,:,:3]=np.clip(rgb(color)[None,None,:]*(.94+.06*lum[:,:,None])*255,0,255).astype('u1');a[:,:,3]=255
        return Image.fromarray(a)
    def slim_body(self,p,pos):
        """Tailor Rina around the existing rest axes, preserving animation pivots.

        Torso and skirt widths are reduced in world space; arms and legs shrink
        across their bone axes, without shortening the limbs or moving joints.
        The neck fades back to its original fit below the unchanged SD head.
        """
        fitted=pos.copy();factor=np.clip((.650-pos[:,1])/.065,0,1)
        fitted[:,0]*=1-.20*factor
        fitted[:,2]=.038+(pos[:,2]-.038)*(1-.14*factor)
        dominant=p['j'][np.arange(len(pos)),p['w'].argmax(1)]
        names=np.array([p['names'][i].lower()for i in dominant])
        def around_chain(vertices,chain,scale):
            if not len(vertices):return
            points=np.array([self.world[self.bone[name]][:3,3]for name in chain])
            q=pos[vertices];nearest=np.empty_like(q);distance=np.full(len(q),np.inf)
            for a,b in zip(points[:-1],points[1:]):
                axis=b-a;t=np.clip((q-a)@axis/max(axis@axis,1e-12),0,1)
                projection=a+t[:,None]*axis;d=((q-projection)**2).sum(1);use=d<distance
                nearest[use]=projection[use];distance[use]=d[use]
            fitted[vertices]=nearest+(q-nearest)*scale
        for side,sign in [('L',1),('R',-1)]:
            arm=np.array([any(t in name for t in ('upperarm','forearm','hand','finger'))for name in names])
            arm|=(np.abs(pos[:,0])>.145)&(pos[:,1]>.395)&(pos[:,1]<.63)
            arm&=pos[:,0]*sign>0
            around_chain(np.flatnonzero(arm),[f'Bip001 {side} UpperArm',f'Bip001 {side} Forearm',f'Bip001 {side} Hand',f'Bip001 {side} Finger2'],.83)
            leg=np.array([any(t in name for t in ('thigh','calf','foot','toe','knee','hip'))for name in names])
            leg&=(pos[:,0]*sign>0)&(pos[:,1]<.43)
            around_chain(np.flatnonzero(leg),[f'Bip001 {side} Thigh',f'Bip001 {side} Calf',f'Bip001 {side} Foot',f'Bip001 {side} Toe0'],.82)
        self.appearance_fit['body']={'method':'Torso/skirt tailoring and limb cross-section fit around unchanged donor bone axes','torso_width_scale':.80,'torso_depth_scale':.86,'arm_cross_section_scale':.83,'leg_cross_section_scale':.82,'head_scale':1.0,'joint_pivots':'unchanged'}
        return fitted
    def add_costume(self,p):
        if self.c['id']==3 and p['mat']['name'].endswith('_Body'):
            self.reference_uniform(p);return
        pos=p['pos'].copy();idx=p['idx'].copy();cent=pos[idx].mean(1);names=p['names']
        dominant=p['j'][np.arange(len(pos)),p['w'].argmax(1)];bone_names=np.array([names[k].lower()for k in dominant])
        keep=np.ones(len(idx),bool);cid=self.c['id']
        # Original headgear and unrelated secondary props are removed by topology.
        excluded=['bone_wing','bone_hat','bone_cap','bone_headphone','bone_bag','bone_tail']
        if cid==6:excluded+=['bone_skirt_ribbon','bone_spine_rope','bone_hair_b_ribbon','bone_hand_l_acc','bone_hand_r_acc']
        unwanted=np.array([any(s in n for s in excluded)for n in bone_names]);keep&=~unwanted[idx].any(1)
        groups=components(pos,idx,weld=cid==9)
        for triangles in groups:
            vertices=np.unique(idx[triangles]);used=pos[vertices];uv=p['uv'][vertices];n=len(vertices)
            lo,hi=used.min(0),used.max(0);uvlo,uvhi=uv.min(0),uv.max(0)
            headpiece=used[:,1].mean()>self.headpos[1]+.06
            if cid==1 and n==256:headpiece=False;pos[vertices,1]+=self.head_adjust # real pleated maid headband
            if headpiece:keep[triangles]=False
            if cid==1 and 165<=n<=185 and hi[1]>.90:keep[triangles]=False
            if cid==9 and 1300<n<1850 and hi[0]-lo[0]>.40 and lo[1]<.16 and hi[1]>.58:keep[triangles]=False
            if cid==6:
                coat=(uvhi[0]<.36 and uvlo[1]>.58)or(.36<uvlo[0] and uvhi[0]<.42 and uvlo[1]>.91)or(.68<uvlo[0] and uvhi[0]<.77 and uvlo[1]>.94)
                if coat:keep[triangles]=False
        from costume_filters import costume_keep
        keep=costume_keep(cid,pos,idx,p['uv'],groups,keep)
        if cid==6:
            # Ibuki's legs terminate inside boots. Replace the whole lower
            # anatomy with a continuous barefoot donor rather than splicing
            # a foot onto an open, differently proportioned calf.
            from costume_filters import leg_triangles
            keep&=~leg_triangles(cid,pos,idx,p['uv'],groups,bone_names)
        # The source camisole also supplies a smooth, skinned abdomen surface.
        # Split it at an existing horizontal torso section for a true crop hem.
        midriff=np.zeros(len(idx),bool)
        if cid==7 and p['name']=='CH0266_Body':
            for triangles in groups:
                vertices=np.unique(idx[triangles]);uv=p['uv'][vertices]
                if len(vertices)==124 and uv[:,0].min()>.67 and uv[:,0].max()<.94:
                    midriff[triangles]=True
            self.crop_camisole(p,pos,idx[midriff & keep],.508)
            keep&=~midriff
        idx=idx[keep]
        if not len(idx):return
        cent=pos[idx].mean(1)
        leg_vertex=np.array([any(t in n for t in (' thigh',' calf',' foot',' knee',' hip'))for n in bone_names])
        legtri=leg_vertex[idx].any(1)&(cent[:,1]<.43)&(np.abs(cent[:,0])<.2)&(cent[:,1]>.072)
        if cid in (4,7,10):
            # Classify whole anatomical components, including helper-weighted
            # knees and ankles, while preserving shoes and skirt lace.
            anatomical=np.zeros(len(p['idx']),bool)
            for triangles in groups:
                vertices=np.unique(p['idx'][triangles]);q=pos[vertices]
                names_used=bone_names[vertices]
                is_leg=np.array([any(t in n for t in (' thigh',' calf',' foot',' knee',' hip',' toe'))for n in names_used])
                standard=np.array([n.startswith('bip001')for n in names_used])
                if q[:,1].max()<.42 and q[:,1].max()>.18 and np.ptp(q[:,0])<.15 and standard.all() and is_leg.mean()>.35:
                    anatomical[triangles]=True
            legtri=anatomical[keep]
        if cid==6:
            anatomical=np.zeros(len(p['idx']),bool)
            for triangles in groups:
                vertices=np.unique(p['idx'][triangles]);uv=p['uv'][vertices]
                if uv[:,0].min()>.009 and uv[:,0].max()<.055 and uv[:,1].min()>.55 and uv[:,1].max()<.57:
                    anatomical[triangles]=True
            legtri=anatomical[keep]
        # Preserve genuine source shoes, stockings get their own material so UVs
        # shared with hands cannot accidentally turn hands into stocking fabric.
        if cid==5:pos=self.slim_body(p,pos)
        cloth_image=self.costume_texture(p);mat=self.wardrobe_material('Source wardrobe / '+self.src.name+' / '+p['mat']['name'],p,cloth_image)
        j=self.map_bones(p,self.src,np.zeros(3))
        def emit(label,tri,material):
            if len(tri):self.mesh(label,pos,tri,material,uv=p['uv'],norm=None if cid==5 else p['norm'],j=j,w=p['w'])
        emit('Tailored source garment / '+p['name'],idx[~legtri],mat)
        leg=self.c['legs'];legidx=idx[legtri]
        if leg=='thigh':
            pelvis=self.world[self.bone['Bip001 Pelvis']][1,3];knee=self.world[self.bone['Bip001 L Calf']][1,3];limit=knee+(pelvis-knee)*.53
            lower=pos[legidx].mean(1)[:,1]<limit
            bare=self.material('Bare upper thighs','#ffffff',self.leg_texture(p,'#fce5db'))
            emit('Bare upper thighs',legidx[~lower],bare);legidx=legidx[lower]
        if len(legidx):
            color={'white':'#f8f5fb','black':'#292330','thigh':'#283b78','bare':'#fce5db'}[leg]
            material=self.material('Legwear / '+leg+' / '+p['mat']['name'],'#ffffff',self.leg_texture(p,color))
            emit('Anatomy / '+leg,legidx,material)
    def crop_camisole(self,p,pos,idx,height):
        """Clip a skinned torso surface into fabric and exposed abdomen."""
        if not len(idx):return
        joints=self.map_bones(p,self.src,np.zeros(3))
        materials=[self.material('Exposed midriff','#ffe8e4'),self.wardrobe_material('Cropped camisole',p,self.costume_texture(p))]
        for upper,material in enumerate(materials):
            points=[];normals=[];uvs=[];js=[];ws=[];faces=[]
            for tri in idx:
                polygon=[(pos[i],p['norm'][i],p['uv'][i],joints[i],p['w'][i])for i in tri]
                clipped=[]
                for a,b in zip(polygon,polygon[1:]+polygon[:1]):
                    inside_a=(a[0][1]>=height)if upper else(a[0][1]<=height)
                    inside_b=(b[0][1]>=height)if upper else(b[0][1]<=height)
                    if inside_a:clipped.append(a)
                    if inside_a!=inside_b:
                        t=(height-a[0][1])/(b[0][1]-a[0][1]);weight={}
                        for ids,values,factor in [(a[3],a[4],1-t),(b[3],b[4],t)]:
                            for joint,value in zip(ids,values):weight[int(joint)]=weight.get(int(joint),0)+float(value)*factor
                        strongest=sorted(weight.items(),key=lambda pair:pair[1],reverse=True)[:4]
                        ji=np.zeros(4,int);wi=np.zeros(4,float)
                        for k,(joint,value)in enumerate(strongest):ji[k]=joint;wi[k]=value
                        wi/=wi.sum()
                        clipped.append((a[0]*(1-t)+b[0]*t,a[1]*(1-t)+b[1]*t,a[2]*(1-t)+b[2]*t,ji,wi))
                offset=len(points)
                for point,normal,uv,ji,wi in clipped:points.append(point);normals.append(normal);uvs.append(uv);js.append(ji);ws.append(wi)
                for k in range(1,len(clipped)-1):faces.append([offset,offset+k,offset+k+1])
            self.mesh('Cropped camisole'if upper else'Exposed abdomen',points,faces,material,uv=uvs,norm=normals,j=js,w=ws)
        # A shallow recessed navel follows the same pelvis/spine blend as its
        # neighbouring abdomen, avoiding a detached decorative dot.
        center=np.array([0,.482,.1095]);points=[];faces=[]
        for radius,z in [(.0032,0),(.0018,-.0005)]:
            for t in np.linspace(0,2*math.pi,17)[:-1]:points.append(center+[radius*math.cos(t),radius*1.25*math.sin(t),z])
        for i in range(16):a=i;b=(i+1)%16;faces.extend([[a,b,a+16],[b,b+16,a+16]])
        points.append(center+[0,0,-.0009])
        for i in range(16):faces.append([16+i,16+(i+1)%16,32])
        self.mesh('Shallow navel',points,faces,self.material('Navel soft shade','#d8aaa4'),bones=[('Bip001 Spine',.8),('Bip001 Pelvis',.2)])
    def barefoot_source(self):
        self.bare_leg_source(.365,with_feet=True)
    def bare_leg_source(self,top,with_feet=False):
        """Retarget a continuous anatomical surface, excluding sandal islands."""
        source=self.source('Hina (Swimsuit)');p=next(p for p in source.parts()if p['mat']['name'].endswith('_Body'))
        main=max(components(p['pos'],p['idx'],weld=True),key=len);idx=p['idx'][main]
        source_joints=source.doc['skins'][source.doc['nodes'][p['node']]['skin']]['joints']
        remap=[];transforms=[]
        for source_node in source_joints:
            anchor=source_node
            while source.doc['nodes'][anchor].get('name','')not in self.bone or source.doc['nodes'][anchor].get('name','').startswith('Bip001_B'):
                if anchor not in source.parents:break
                anchor=source.parents[anchor]
            target=self.bone.get(source.doc['nodes'][anchor].get('name'),self.bone['Bip001 Pelvis'])
            remap.append(target);transforms.append(self.world[target]@np.linalg.inv(source.world[anchor]))
        blend=(np.array(transforms)[p['j']]*p['w'][:,:,None,None]).sum(1)
        pos=np.einsum('nij,nj->ni',blend,np.c_[p['pos'],np.ones(len(p['pos']))])[:,:3]
        norm=np.einsum('nij,nj->ni',blend[:,:3,:3],p['norm'])
        cent=pos[idx].mean(1);keep=cent[:,1]<top
        if not with_feet:keep&=cent[:,1]>.042
        idx=idx[keep];j=np.array(remap,np.uint16)[p['j']]
        im=source.image(p['mat']['pbrMetallicRoughness']['baseColorTexture']['index']);im.putalpha(255)
        mat=self.material('Continuous bare anatomy / Hina Swimsuit','#ffffff',im)
        self.mesh('Continuous bare legs and feet'if with_feet else'Continuous bare legs',pos,idx,mat,uv=p['uv'],norm=norm,j=j,w=p['w'])
    def reference_uniform(self,p):
        """Reassemble Serika's actual tailoring into the supplied blazer design."""
        idx=p['idx'];pos=p['pos'];groups=components(pos,idx);j=self.map_bones(p,self.src,np.zeros(3))
        source_image=self.src.image(p['mat']['pbrMetallicRoughness']['baseColorTexture']['index']);source_image.putalpha(255)
        original=np.array(source_image);colors=original[:,:,:3].astype(float);r,g,b=colors.transpose(2,0,1);lum=colors@np.array([.27,.57,.16])/255
        gray=original.copy();navy=(b>r+9)&(b>g+9)&(np.min(colors,axis=2)>17)
        gray[:,:,:3][navy]=np.clip(rgb('#94959d')*(.62+.38*np.minimum(lum[navy,None]/.23,1))*255,0,255).astype('u1')
        piping=(np.min(colors,axis=2)>195)&((np.max(colors,axis=2)-np.min(colors,axis=2))<45)
        gray[:,:,:3][piping]=np.array([29,30,38],np.uint8)
        gray_mat=self.wardrobe_material('Reference uniform / gray tailoring with black piping',p,Image.fromarray(gray))
        source_mat=self.wardrobe_material('Reference uniform / white shirt and source shoes',p,source_image)
        skin_mat=self.material('Reference uniform / bare hands','#ffe4da')
        # A woven tartan texture follows the source pleats; the original fold
        # lighting is multiplied into it rather than painting a flat skirt.
        yy,xx=np.indices((512,512));px=xx%128;py=yy%128
        tartan=np.empty((512,512,4),np.uint8);tartan[:]=[30,31,39,255]
        broad=((px>29)&(px<51))|((py>29)&(py<51));cross=((px>29)&(px<51))&((py>29)&(py<51))
        tartan[broad,:3]=[117,41,57];tartan[cross,:3]=[165,53,71]
        thin=((px>78)&(px<82))|((py>78)&(py<82));tartan[thin,:3]=[159,57,71]
        fine=(px==12)|(py==12);tartan[fine,:3]=[182,168,171]
        textile=(.96+.04*((xx+yy)%2))[...,None];tartan[:,:,:3]=(tartan[:,:,:3]*textile).astype('u1')
        tartan_mat=self.material('Reference uniform / red black woven tartan','#ffffff',Image.fromarray(tartan))
        silver=self.material('Reference uniform / silver buttons','#d1d1da',metal=.6)
        removed=set(range(12,18))|set(range(43,62))|{68,69,70,100,101,102,103,104,105,106}
        tie=set(range(21,27));skirt=set(range(79,98));black=self.material('Reference uniform / skirt liner','#23242c')
        for k,triangles in enumerate(groups):
            if k in removed:continue
            tri=idx[triangles];cent=pos[tri].mean(1);uv=p['uv'].copy();material=gray_mat;name='Fitted gray blazer'
            if k in tie:
                material=tartan_mat;name='Red tartan necktie';uv=np.c_[(pos[:,0]+.014)/.028,(.65-pos[:,1])/.025]
            elif k in skirt:
                material=tartan_mat;name='Source pleated tartan skirt'
                # Cylindrical UVs follow the continuous skirt circumference.
                uv=np.c_[np.arctan2(pos[:,0],pos[:,2]-.04)/(2*math.pi)*6+.5,(pos[:,1]-.299)*14]
            elif k in (10,11):material=skin_mat;name='Bare source hands'
            elif k in (5,8,18,19,20) or (cent[:,1].max()<.065):material=source_mat;name='White collared shirt or shoes'
            elif k>=107:material=silver;name='Tailoring silver button'
            elif k==66 or k==67:
                tri=tri[cent[:,1]>.32];material=black;name='Concealed skirt liner'
            elif k in (0,1,2,3,37,42):material=gray_mat
            if len(tri):
                if k in skirt:
                    expanded=tri.reshape(-1);tile_uv=uv[expanded].reshape(-1,3,2).copy()
                    wraps=np.ptp(tile_uv[:,:,0],axis=1)>3
                    tile_uv[:,:,0]+=((tile_uv[:,:,0]<.5)&wraps[:,None])*6
                    self.mesh(name,pos[expanded],np.arange(len(expanded)).reshape(-1,3),material,uv=tile_uv.reshape(-1,2),norm=p['norm'][expanded],j=j[expanded],w=p['w'][expanded])
                else:self.mesh(name,pos,tri,material,uv=uv,norm=p['norm'],j=j,w=p['w'])
        self.bare_leg_source(.352,with_feet=False)
    def outfits(self):
        if self.c['id']>=11:
            from reference_characters import outfits
            outfits(self);return
        for part in self.costume_parts:self.add_costume(part)
        c=self.c;style=c['style'];gold=self.material('Original accessory / gold','#d9b66d',metal=.7);dark=self.material('Original accessory / trim',c['palette'][2]);accent=self.material('Original accessory / accent',c['palette'][1]);white=self.material('Original accessory / pearl','#f9f6ff');pink=self.material('Original accessory / ribbon',c['hair_color'])
        if style=='reference_school':accent=self.material('Sora crystal charm','#91cef0')
        if style=='reaper':self.rose((-.151,self.headpos[1]+.217,.064),.072,self.material('Azure rose petals','#3d78d1'),self.material('Rose leaf','#40639a'))
        if style=='blazer':self.bow('One-side silk hair tie',(-.163,self.headpos[1]+.07,.007),.038,self.material('School hair ribbon','#ac6d92'))
        if style=='reference_school':
            flower_center=np.array([-.155,self.headpos[1]+.23,.080]);blue=self.material('Sora azure flower','#79bae7');petal_white=self.material('Sora flower white edge','#eef7ff')
            for k in range(5):
                angle=2*math.pi*k/5;radial=np.array([math.cos(angle),math.sin(angle),0]);tangent=np.array([-math.sin(angle),math.cos(angle),0])
                points=[];faces=[]
                for ring in range(7):
                    t=ring/6;length=.046*t;width=.014*math.sin(math.pi*t)**.65
                    for edge in range(9):
                        a=2*edge/8-1;points.append(flower_center+radial*length+tangent*width*a+[0,0,.006*math.sin(math.pi*t)*(1-a*a)])
                for ring in range(6):
                    for edge in range(8):a=ring*9+edge;faces.extend([[a,a+9,a+1],[a+1,a+9,a+10]])
                self.mesh('Azure flower pointed petal',points,faces,blue if k%2 else petal_white,'Bip001 Head')
            self.ellipsoid('Flower gold center',flower_center+[0,0,.008],(.006,.006,.004),gold)
            for k in range(8):
                y=self.headpos[1]+.17-k*.014;x=-.151+.006*math.sin(k*math.pi/2)
                self.ellipsoid('Small woven side braid',(x,y,.040),(.009,.011,.009),self.material('Sora braided hair',c['hair_color']),'Bip001 Head',seg=14,rings=8)
        if style=='sprite':
            self.barefoot_source()
            for i in range(8):
                t=math.pi*2*i/8;x=.065*math.sin(t);z=.045*math.cos(t)
                self.patch('Pointed fairy collar leaf',[[x,.61,z],[x*1.45,.565,z*1.35],[x+.017*math.cos(t),.604,z-.015*math.sin(t)]],accent)
        if style=='cat':
            # Wrap the real Kirara spiral buns with small crossing braids; the
            # donor buns and waves remain the main silhouette.
            kirara=self.source('Kirara');kh=next(i for i,n in enumerate(kirara.doc['nodes'])if n.get('name')=='Bip001 Head'and i in kirara.world)
            delta=self.headpos-kirara.world[kh][:3,3];delta[1]+=self.head_adjust
            braid=self.material('Momo woven pink hair','#e59abc');highlight=self.material('Momo braid highlights','#f7c0d8')
            for side in [-1,1]:
                center=np.array([side*.182,.851,-.046])+delta
                for strand in [0,1]:
                    pts=[]
                    for t in np.linspace(0,2*math.pi,65):
                        pts.append(center+[.035*math.cos(t),.036*math.sin(t),.013+.0045*math.sin(5*t+strand*math.pi)])
                    self.tube('Momo braided side bun wrap',pts,[.0045]*len(pts),braid if strand else highlight,'Bip001 Head',8)
                self.bow('Momo small bun ribbon',center+[0,-.035,.018],.014,accent)
        if style=='doll':
            self.tube('Winding key stem',[[0,.51,-.095],[0,.51,-.15]],[.005,.005],gold,'Bip001 Spine')
            for side in [-1,1]:
                pts=[[side*.024+.025*math.cos(t),.526+.018*math.sin(t),-.157]for t in np.linspace(0,2*math.pi,25)];self.tube('Open winding key loop',pts,[.0035]*len(pts),gold,'Bip001 Spine')
        if style=='qipao':
            source=self.source(c['hair']);sh=next(i for i,n in enumerate(source.doc['nodes'])if n.get('name')=='Bip001 Head'and i in source.world)
            delta=self.headpos-source.world[sh][:3,3];delta[1]+=self.head_adjust
            scarlet=self.material('Meilin scarlet silk hair ornament','#b8233b')
            dark_red=self.material('Meilin ornament petal shade','#771e30')
            for side,letter in [(1,'L'),(-1,'R')]:
                name=f'bone_hair_ribbon_{letter}_00'
                si=next(i for i,n in enumerate(source.doc['nodes'])if n.get('name')==name and i in source.world)
                center=source.world[si][:3,3]+delta+[side*.022,.025,.058]
                self.bow('Scarlet twin-tail silk ribbon',center,.046,scarlet)
                self.bow('Twin-tail fine gold knot',center+[0,0,.005],.024,gold)
                for k in range(5):
                    t=k*2*math.pi/5;petal=center+[.018*math.cos(t),.018*math.sin(t),.013]
                    self.ellipsoid('Meilin tie flower petal',petal,(.012,.014,.0045),scarlet if k%2 else dark_red,'Bip001 Head',16,8)
                self.ellipsoid('Meilin tie flower gold center',center+[0,0,.021],(.006,.006,.0035),gold,'Bip001 Head',16,8)
                self.tube('Meilin hanging gold hair cord',[center+[side*.018,-.015,.008],center+[side*.032,-.052,.017],center+[side*.031,-.080,.013]],[.0025,.0025,.0025],gold,'Bip001 Head',10)
                self.ellipsoid('Meilin gold hair pendant',center+[side*.031,-.085,.013],(.007,.011,.004),gold,'Bip001 Head',16,8)
        # Kirara's actual spiral buns are retained rather than covered by spheres.
        if self.c['id']==1:
            from personality_hair import ornaments
            ornaments(self)
        self.accessory(style,gold,dark,accent,white)
    def rose(self,c,size,mat,leaf):
        c=np.array(c)
        for ring,count in [(1,7),(.65,6),(.3,5)]:
            for i in range(count):
                t=2*math.pi*i/count;cc=c+np.array([math.cos(t),math.sin(t),0])*size*ring*.52
                self.ellipsoid('Blue rose layered petal',cc,[size*.35,size*.26,size*.12],mat,seg=16,rings=8)
        self.ellipsoid('Rose curled heart',c+[0,0,.012],[size*.18,size*.18,size*.19],mat)
        self.patch('Rose pointed leaf',[c+[-size,.01,-.009],c+[-size*.5,-size*.45,-.005],c+[-size*.3,0,.004]],leaf,'Bip001 Head')
    def accessory(self,style,gold,dark,accent,white):
        bone='Bip001 R Hand';hand=self.world[self.bone[bone]][:3,3].copy()
        fingers=[self.world[self.bone[n]][:3,3]for n in ['Bip001 R Finger1','Bip001 R Finger2']if n in self.bone]
        if fingers:hand+=.5*(np.mean(fingers,axis=0)-hand)
        x,y,z=hand
        if style=='reaper':
            self.tube('Scythe lacquered haft',[[x,y-.30,z],[x,y+.34,z]],[.009,.011],dark,bone,20)
            self.tube('Scythe engraved collar',[[x,y+.28,z],[x,y+.314,z]],[.016,.017],gold,bone,24)
            def cubic(points,t):return sum(np.array(q)*weight for q,weight in zip(points,[(1-t)**3,3*(1-t)**2*t,3*(1-t)*t*t,t**3]))
            outer=[];inner=[]
            for t in np.linspace(0,1,33):
                outer.append(cubic([[x+.009,y+.323,z],[x-.12,y+.432,z],[x-.32,y+.40,z],[x-.37,y+.17,z]],t))
                inner.append(cubic([[x-.006,y+.30,z],[x-.14,y+.31,z],[x-.28,y+.28,z],[x-.37,y+.17,z]],t))
            vertices=[];faces=[]
            for k,(a,b)in enumerate(zip(outer,inner)):
                depth=.0045*(1-k/32)**.65+.0005
                vertices.extend([a+[0,0,depth],b+[0,0,depth],a-[0,0,depth],b-[0,0,depth]])
            for k in range(32):
                a=k*4;b=a+4;faces.extend([[a,b,a+1],[a+1,b,b+1],[a+2,a+3,b+2],[a+3,b+3,b+2],[a,a+2,b],[a+2,b+2,b],[a+1,b+1,a+3],[a+3,b+1,b+3]])
            self.mesh('Bevelled crescent steel blade',vertices,faces,self.material('Scythe satin steel','#e4eafa',metal=.65),bone)
            self.tube('Crescent azure inlay',outer,[.0025*(1-i/32)+.0005 for i in range(33)],accent,bone,10)
            for h in [-.027,.025]:
                pts=[[x+.0105*math.cos(t),y+h,z+.0105*math.sin(t)]for t in np.linspace(0,2*math.pi,21)];self.tube('Haft grip ring',pts,[.002]*len(pts),gold,bone)
        elif style=='maid':
            self.tube('Ribbon rapier',[[x,y-.035,z],[x,y+.37,z]],[.010,.002],gold,bone,20)
            self.ellipsoid('Rapier spoon guard',(x,y+.02,z),(.034,.01,.023),white,bone)
        elif style=='qipao':
            center=np.array([x,y,z]);verts=[];uv=[];faces=[]
            for k,radius in enumerate([.009,.065,.115,.16]):
                for i in range(33):
                    a=math.pi*(i/32-.5);fold=(1 if i%2 else -1)*radius*.047;verts.append(center+[math.sin(a)*radius,math.cos(a)*radius,fold]);uv.append([.5+math.sin(a)*radius/.32,1-math.cos(a)*radius/.16])
            for k in range(3):
                for i in range(32):a=k*33+i;b=a+33;faces.extend([[a,b,a+1],[a+1,b,b+1]])
            paper=Image.new('RGBA',(512,512),(184,36,61,255));draw=ImageDraw.Draw(paper)
            for cx,cy in [(132,175),(345,120),(255,310)]:
                for t in np.linspace(0,2*math.pi,9)[:-1]:
                    dx,dy=math.cos(t)*15,math.sin(t)*15;draw.ellipse((cx+dx-15,cy+dy-23,cx+dx+15,cy+dy+23),outline=(222,184,109,255),width=2)
                draw.ellipse((cx-7,cy-7,cx+7,cy+7),fill=(227,190,120,255))
            self.mesh('Corrugated embroidered folding fan',verts,faces,self.material('Fan peony paper','#ffffff',paper),bone,uv=uv)
            for i in range(9):a=math.pi*(i/8-.5);self.tube('Fan gold rib',[center,center+[math.sin(a)*.16,math.cos(a)*.16,-.0075]],[.0022,.0016],gold,bone)
            self.ellipsoid('Fan pivot rivet',center,(.005,.005,.004),gold,bone,16,8)
        elif style=='sprite':
            self.tube('Clover wand',[[x,y-.07,z],[x,y+.185,z]],[.006,.004],dark,bone,20)
            for dx,dy in [(-.018,0),(.018,0),(0,.027)]:self.ellipsoid('Clover wand leaf',(x+dx,y+.19+dy,z),(.019,.022,.006),accent,bone)
        elif style!='cat':
            self.ellipsoid('Signature charm',(x,y+.045,z),(.027,.03,.017),accent,bone)
            self.tube('Charm stem',[[x,y-.025,z],[x,y+.06,z]],[.004,.004],gold,bone)
    def finish(self):
        if self.c['id'] == 1:
            self.appearance_fit['garment_mark'] = {'method':'Restored local navy textile across the removed bracket logo', 'source_material':'CH0201_Body', 'atlas_pixels':[429,184,466,225]}
        elif self.c['id'] == 5:
            self.appearance_fit['school_crest'] = {'design':'Rose Academy shield, rose, laurel, open book and star with champagne gold frame', 'source_material':'CH0167_Body', 'method':'Repainted original mirrored badge atlas; original badge geometry and skin preserved'}
        inverse=np.array([np.linalg.inv(self.world[i]).T.reshape(-1)for i in self.joint]);self.doc['skins']=[{'name':'Unified SD character rig','joints':self.joint,'inverseBindMatrices':self.acc(inverse,'MAT4'),'skeleton':0}]
        # Skin accessors currently contain node ids. Convert to final joint slots.
        slots={ni:i for i,ni in enumerate(self.joint)}
        for mesh in self.doc['meshes']:
            for p in mesh['primitives']:
                ai=p['attributes']['JOINTS_0'];a=self.doc['accessors'][ai];v=self.doc['bufferViews'][a['bufferView']];off=v['byteOffset'];arr=np.frombuffer(self.data,dtype='<u2',count=a['count']*4,offset=off).copy();arr=np.array([slots[int(x)]for x in arr],dtype='<u2');self.data[off:off+arr.nbytes]=arr.tobytes()
        from character_animations import add_animations,add_donor_animations
        add_animations(self.doc,self.acc,self.c['id'],self.c['attack'])
        native=(add_donor_animations(self.doc,self.acc,self.src.doc,self.src.acc,self.source_node_map,self.c['id'],self.c['attack'])
                if self.c['id']<11 else {})
        from source_motion_refresh import add_catalog_motions
        native.update(add_catalog_motions(self))
        motion_sources = dict(getattr(self, 'motion_sources', {}))
        for clip_name, source_clip in native.items():
            motion_sources.setdefault(clip_name, {
                'source_file': self.src.name+'.glb', 'source_clip': source_clip,
                'adaptation': ['original costume rig tracks', 'in-place travel removal', 'exact loop closure' if clip_name in ('Idle','Walk','Run') else 'one-shot playback'],
                'description': 'Preserved original costume animation',
            })
        source_roles={'costume_and_rig':self.src.name+'.glb','hair':self.c['hair']+'.glb','face':self.c['face']+'.glb'}
        if self.c['id']==1:source_roles['ahoge']='Erika.glb'
        if self.c['id']==1:source_roles['tail_hair']='Yoshimi.glb'
        if self.c['id']==8:source_roles['hair_coils']='Seia (Swimsuit).glb'
        if self.c['id']==8:source_roles['forehead_curl']='Erika.glb'
        if self.c['id']==3:source_roles['back_hair']='Miyo.glb'
        if self.c['id']==7:source_roles.update(back_hair='Kirara.glb',ears='Kazusa.glb')
        if self.c['id']in(3,6):source_roles['bare_legs_and_feet']='Hina (Swimsuit).glb'
        if self.c['id']>=11:
            source_roles.update(self.c.get('extra_source_roles',{}))
        source_roles.update({'motion_'+name.lower(): record['source_file'] for name,record in motion_sources.items()})
        source_parts=list(dict.fromkeys(source_roles.values()))
        triangles=sum(self.doc['accessors'][p['indices']]['count']//3 for m in self.doc['meshes']for p in m['primitives'])
        created='2026-10-07'if self.c['id']>=11 else'2026-10-06'
        self.doc['extras']={'character':self.c['name'],'design_ko':self.c['design'],'created':created,'modified':'2026-10-09','source_parts':source_parts,'source_roles':source_roles,'original_work':'Original textured donor garment topology, tailored accessories, fitted chin/neck, catalog-selected original motions and attacks with fitted props','head_fit':self.head_fit,'appearance_fit':self.appearance_fit,'native_clips':native,'motion_sources':motion_sources,'revision':6,'triangles':triangles}
        self.doc['buffers']=[{'byteLength':len(self.data)}];js=json.dumps(self.doc,ensure_ascii=False,separators=(',',':')).encode();js+=b' '*((-len(js))%4);binary=bytes(self.data)+b'\0'*((-len(self.data))%4)
        out=ROOT/'characters'/self.c['slug'];out.mkdir(parents=True,exist_ok=True);path=out/(self.c['slug']+'.glb');path.write_bytes(struct.pack('<III',0x46546c67,2,12+8+len(js)+8+len(binary))+struct.pack('<II',len(js),0x4e4f534a)+js+struct.pack('<II',len(binary),0x004e4942)+binary)
        return {'id':self.c['id'],'slug':self.c['slug'],'name':self.c['name'],'name_ko':self.c['name_ko'],'tagline':self.c['tagline'],'palette':self.c['palette'],'design':self.c['design'],'source_parts':source_parts,'source_roles':source_roles,'animations':[a['name']for a in self.doc['animations']],'glb':str(path.relative_to(ROOT)).replace('\\','/'),'sheet':f'characters/{self.c["slug"]}/{self.c["slug"]}_sheet.png','bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'revision':6,'costume_source':self.src.name+'.glb','triangles':triangles,'head_fit':self.head_fit,'appearance_fit':self.appearance_fit,'native_clips':native,'motion_sources':motion_sources}

def main():
    global SOURCE
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=SOURCE);ap.add_argument('--ids',nargs='*',type=int);args=ap.parse_args();SOURCE=args.source
    out=[]
    for c in DESIGNS:
        if args.ids and c['id']not in args.ids:continue
        b=Builder(c);b.head_parts();b.outfits();out.append(b.finish());print('Built',c['slug'],flush=True)
    path=ROOT/'characters'/'manifest.json'
    if args.ids and path.exists():
        old=json.loads(path.read_text(encoding='utf-8'));out=sorted([x for x in old if x['id']not in args.ids]+out,key=lambda x:x['id'])
    path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
