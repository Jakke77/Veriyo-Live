#!/usr/bin/env python3
"""Create calm local deformations of the original Ubuntu artwork, without AI repainting."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import math
from pathlib import Path
import shutil
import urllib.request
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import numpy as np
from PIL import Image, ImageOps

ROOT=Path(__file__).resolve().parents[1]
PACK_VERSION='1.0.0'
WIDTH,HEIGHT=1920,1080


def ensure_source(entry, cache):
    target=cache/entry['original_file']
    if not target.exists():
        request=urllib.request.Request(entry['source_url'],headers={'User-Agent':'VeriyoLiveUbuntuPack/1.0 (offline artwork pack builder)'})
        with urllib.request.urlopen(request,timeout=90) as response:
            content=response.read(80*1024*1024+1)
        if len(content)>80*1024*1024: raise ValueError('Original image is too large')
        temporary=target.with_suffix('.part')
        temporary.write_bytes(content)
        temporary.replace(target)
    if sha256(target.read_bytes()).hexdigest()!=entry['sha256']:
        raise ValueError('Original image checksum differs: '+entry['id'])
    return target


def load_source(entry, cache):
    with Image.open(ensure_source(entry,cache)) as image:
        return ImageOps.fit(image.convert('RGB'),(WIDTH,HEIGHT),method=Image.Resampling.LANCZOS)


def mesh_for(entry, phase):
    step=40
    xs=np.unique(np.append(np.arange(0,WIDTH,step,dtype=np.float64),WIDTH))
    ys=np.unique(np.append(np.arange(0,HEIGHT,step,dtype=np.float64),HEIGHT))
    xx,yy=np.meshgrid(xs,ys)
    x,y=xx/WIDTH,yy/HEIGHT
    dx,dy=np.zeros_like(x),np.zeros_like(y)
    t=2*math.pi*phase
    for index,zone in enumerate(entry['motion']['zones']):
        cx,cy,rx,ry,tx,ty,rotation,breathing=zone
        radius=((x-cx)/rx)**2+((y-cy)/ry)**2
        weight=np.maximum(0,1-radius)**3
        angle=t+entry['motion']['phase']+index*1.2
        tilt=rotation*math.sin(angle)
        pulse=breathing*math.sin(angle+.7)
        dx+=weight*(tx*math.sin(angle)-tilt*(y-cy)*HEIGHT+pulse*(x-cx)*WIDTH)
        dy+=weight*(ty*math.cos(angle)+tilt*(x-cx)*WIDTH+pulse*(y-cy)*HEIGHT)
    sx,sy=np.clip(xx+dx,0,WIDTH),np.clip(yy+dy,0,HEIGHT)
    mesh=[]
    for row in range(len(ys)-1):
        for col in range(len(xs)-1):
            box=tuple(map(int,(xs[col],ys[row],xs[col+1],ys[row+1])))
            quad=(sx[row,col],sy[row,col],sx[row+1,col],sy[row+1,col],
                  sx[row+1,col+1],sy[row+1,col+1],sx[row,col+1],sy[row,col+1])
            mesh.append((box,quad))
    return mesh


def build(output, cache, jobs=3):
    output.mkdir(parents=True,exist_ok=True)
    cache.mkdir(parents=True,exist_ok=True)
    stage=output/'Ubuntu-Live-Pack-1.0.0'
    if stage.exists():raise ValueError('Output directory already exists: '+str(stage))
    stage.mkdir()
    catalog=json.loads((ROOT/'veriyo_live/assets/ubuntu_catalog.json').read_text(encoding='utf-8'))['releases']
    unique={entry['original_file']:entry for entry in catalog}
    list(ThreadPoolExecutor(max_workers=jobs).map(lambda entry:ensure_source(entry,cache),unique.values()))
    def render(entry):
        original=load_source(entry,cache)
        target=stage/entry['id'];target.mkdir()
        frames=[]
        for number in range(entry['motion']['frames']):
            phase=number/entry['motion']['frames']
            image=original.transform((WIDTH,HEIGHT),Image.Transform.MESH,mesh_for(entry,phase),Image.Resampling.BICUBIC)
            path=target/f'{number:02d}.jpg'
            image.save(path,quality=95,subsampling=0,optimize=True)
            frames.append({'file':path.relative_to(stage).as_posix(),'sha256':sha256(path.read_bytes()).hexdigest()})
        print(entry['version']+' '+entry['name'],flush=True)
        return {'version':entry['version'],'id':entry['id'],'name':entry['name'],'period':entry['motion']['period'],
                'motion_label':entry['motion_label'],'source_url':entry['source_url'],'source_sha256':entry['sha256'],
                'credit':entry['credit'],'frames':frames,'size':[WIDTH,HEIGHT]}
    # Each worker decodes one original once; no full movie frame stream is stored.
    rendered=list(ThreadPoolExecutor(max_workers=jobs).map(render,catalog))
    shutil.copytree(ROOT/'ubuntu-pack/LICENSES',stage/'LICENSES')
    shutil.copyfile(ROOT/'ubuntu-pack/README.md',stage/'README.md')
    (stage/'pack.json').write_text(json.dumps({'format':'veriyo-ubuntu-live','version':PACK_VERSION,'releases':rendered},indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    archive=output/'Ubuntu-Live-Pack-1.0.0.zip'
    with ZipFile(archive,'w',ZIP_DEFLATED,compresslevel=6) as stream:
        for path in sorted(stage.rglob('*')):
            if path.is_file():stream.write(path,path.relative_to(stage))
    originals=output/'Ubuntu-Live-Originals-1.0.0.zip'
    with ZipFile(originals,'w',ZIP_DEFLATED,compresslevel=6) as stream:
        for name in sorted({e['original_file'] for e in catalog}):stream.write(cache/name,name,compress_type=ZIP_STORED)
        stream.writestr('sources.json',json.dumps(catalog,ensure_ascii=False,indent=2))
        for path in (ROOT/'ubuntu-pack/LICENSES').iterdir():stream.write(path,'LICENSES/'+path.name)
    (output/'SHA256SUMS').write_text(''.join(sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in (archive,originals)))
    print(archive,flush=True)
    return archive


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--cache',type=Path,default=Path('downloads/ubuntu-originals'))
    parser.add_argument('--jobs',type=int,default=3)
    args=parser.parse_args()
    build(args.output.resolve(),args.cache.resolve(),max(1,min(5,args.jobs)))
