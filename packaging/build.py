#!/usr/bin/env python3
"""Build self-contained source ZIP, Ubuntu deb, or verified portable Windows ZIP."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from veriyo_live import VERSION


def copy_tree(source, target):
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'),dirs_exist_ok=True)


def stage_source(target):
    target.mkdir(parents=True,exist_ok=False)
    for folder in ('veriyo_live','tests','packaging','docs','screenshots'):
        copy_tree(ROOT/folder,target/folder)
    for name in ('main.py','README.md','LICENSE','THIRD_PARTY_NOTICES.md','requirements.txt'):
        shutil.copyfile(ROOT/name,target/name)
    vendor=ROOT/'vendor'
    if not (vendor/'pymeeus').is_dir():
        vendor=ROOT.parent/'vendor'
    for folder in ('pymeeus','pymeeus-0.5.12.dist-info'):
        copy_tree(vendor/folder,target/'vendor'/folder)
    # Normalise restrictive managed-workspace permissions for real user installs.
    for path in [target,*target.rglob('*')]:
        path.chmod(0o755 if path.is_dir() else 0o644)


def archive_tree(source, archive):
    with ZipFile(archive,'w',ZIP_DEFLATED,compresslevel=6) as stream:
        for path in sorted(source.rglob('*')):
            if path.is_file():
                stream.write(path,Path(source.name)/path.relative_to(source))


def write_sums(output):
    files=sorted([*output.glob('*.deb'),*output.glob('*.zip')])
    (output/'SHA256SUMS').write_text(''.join(sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files),encoding='ascii')


def ubuntu(output):
    source=output/f'Veriyo-Live-{VERSION}-lahdekoodi'
    stage_source(source)
    archive_tree(source,output/(source.name+'.zip'))
    stage=output/'deb-root'
    share=stage/'usr/share/veriyo-live'
    copy_tree(source,share)
    bindir=stage/'usr/bin'
    bindir.mkdir(parents=True)
    launcher=bindir/'veriyo-live'
    launcher.write_text('#!/bin/sh\nexec /usr/bin/python3 /usr/share/veriyo-live/main.py "$@"\n')
    launcher.chmod(0o755)
    apps=stage/'usr/share/applications'
    apps.mkdir(parents=True)
    (apps/'veriyo-live.desktop').write_text('[Desktop Entry]\nType=Application\nName=Veriyö Live\nComment=Otavan oikea taivas ja Veri Ajan taustakuva\nExec=veriyo-live\nIcon=veriyo-live\nTerminal=false\nCategories=Utility;Astronomy;\nStartupNotify=true\n')
    icons=stage/'usr/share/icons/hicolor/scalable/apps'
    icons.mkdir(parents=True)
    shutil.copyfile(ROOT/'veriyo_live/assets/icon.svg',icons/'veriyo-live.svg')
    control=stage/'DEBIAN'
    control.mkdir()
    (control/'control').write_text(f'Package: veriyo-live\nVersion: {VERSION}\nSection: utils\nPriority: optional\nArchitecture: all\nMaintainer: Jakke77\nDepends: python3 (>= 3.10), python3-pyqt6, gsettings-desktop-schemas, libglib2.0-bin, tzdata\nDescription: Veriyö Live - Otavan oikea taustakuva ja Veri Aika\n Paikallisesti laskettu GNOME-taustakuva ja erillinen esikatselu.\n')
    for path in [stage,*stage.rglob('*')]:
        path.chmod(0o755 if path.is_dir() or path==launcher else 0o644)
    target=output/f'veriyo-live_{VERSION}_all.deb'
    subprocess.run(['dpkg-deb','--root-owner-group','--build',str(stage),str(target)],check=True)
    write_sums(output)
    return target


def windows(output, cache, zig):
    manifest=json.loads((ROOT/'packaging/downloads.json').read_text(encoding='utf-8'))
    archives=[]
    for record in manifest['files']:
        path=cache/record['name']
        if sha256(path.read_bytes()).hexdigest()!=record['sha256']:
            raise ValueError('Latauksen tarkiste ei täsmää: '+path.name)
        archives.append(path)
    target=output/f'Veriyo-Live-{VERSION}-Windows-x64'
    stage_source(target)
    runtime=target/'runtime'
    packages=runtime/'Lib/site-packages'
    packages.mkdir(parents=True)
    for path in archives:
        destination=packages if path.suffix=='.whl' else runtime
        with ZipFile(path) as stream:
            for member in stream.infolist():
                if not (destination/member.filename).resolve().is_relative_to(destination.resolve()):
                    raise ValueError('Latauksen polku poistuu kohdekansiosta.')
            stream.extractall(destination)
    (runtime/'python312._pth').write_text('python312.zip\n.\nLib/site-packages\n..\n../vendor\nimport site\n',encoding='utf-8')
    shutil.copyfile(ROOT/'packaging/downloads.json',target/'DEPENDENCIES.json')
    resource=output/'launcher.res'
    subprocess.run([str(zig),'rc','/fo',str(resource),'launcher.rc'],cwd=ROOT/'packaging',check=True)
    subprocess.run([str(zig),'cc','-target','x86_64-windows-gnu','-Os','-s','-municode','-Wl,--subsystem,windows',
                    str(ROOT/'packaging/launcher.c'),str(resource),'-o',str(target/'Veriyo-Live.exe'),'-luser32'],check=True)
    resource.unlink()
    for name,command in {
        'Tarkista-toiminta.cmd':'"%~dp0runtime\\python.exe" "%~dp0main.py" --self-test\r\npause',
        'Luo-pikakuvakkeet.cmd':'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Luo-pikakuvakkeet.ps1"\r\npause',
    }.items():
        (target/name).write_bytes(('@echo off\r\n'+command+'\r\n').encode('utf-8'))
    shutil.copyfile(ROOT/'packaging/Luo-pikakuvakkeet.ps1',target/'Luo-pikakuvakkeet.ps1')
    (target/'LUEMINUT.txt').write_text((ROOT/'README.md').read_text(encoding='utf-8'),encoding='utf-8-sig')
    archive=output/(target.name+'.zip')
    archive_tree(target,archive)
    write_sums(output)
    return target


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('platform',choices=['ubuntu','windows'])
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--cache',type=Path)
    parser.add_argument('--zig',type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    if args.platform=='ubuntu':
        print(ubuntu(args.output.resolve()))
    else:
        print(windows(args.output.resolve(),args.cache.resolve(),args.zig.resolve()))
