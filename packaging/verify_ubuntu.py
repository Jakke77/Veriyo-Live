#!/usr/bin/env python3
"""Compare source, ZIP and installed deb, then exercise the extracted runtime."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from veriyo_live import VERSION


def verify(output):
    output=Path(output).resolve()
    with tempfile.TemporaryDirectory(prefix='veriyo-verify-') as temporary:
        directory=Path(temporary)
        deb=directory/'deb'
        subprocess.run(['dpkg-deb','--extract',str(output/f'veriyo-live_{VERSION}_all.deb'),str(deb)],check=True)
        share=deb/'usr/share/veriyo-live'
        source=directory/'source'
        source.mkdir()
        count=0
        with ZipFile(output/f'Veriyo-Live-{VERSION}-lahdekoodi.zip') as archive:
            for member in archive.infolist():
                path=Path(member.filename)
                if path.is_absolute() or not (source/path).resolve().is_relative_to(source.resolve()):
                    raise ValueError('Unsafe source ZIP member')
                if not member.is_dir():
                    relative=Path(*path.parts[1:])
                    content=archive.read(member)
                    assert content==(ROOT/relative).read_bytes(),str(relative)
                    assert content==(share/relative).read_bytes(),str(relative)
                    count+=1
            archive.extractall(source)
        for path in deb.rglob('*'):
            assert path.stat().st_mode & 4,str(path)
            if path.is_dir() or path==deb/'usr/bin/veriyo-live':
                assert path.stat().st_mode & 1,str(path)
        environment=dict(os.environ,QT_QPA_PLATFORM='offscreen')
        for index,staged in enumerate((share,next(source.iterdir()))):
            subprocess.run([sys.executable,str(staged/'main.py'),'--self-test'],cwd=directory,env=environment,check=True)
            subprocess.run([sys.executable,str(staged/'main.py'),'--export',str(directory/f'check-{index}.png'),
                            '--at','2026-10-27T21:00:00+02:00'],cwd=directory,env=environment,check=True)
        print(f'PASS: {count} source/ZIP/deb files identical; permissions, extracted self-tests and PNG exports')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('output',type=Path)
    verify(parser.parse_args().output)
