#!/usr/bin/env python3
"""Optional MP4 preview, using the same quiet frame blends as the application."""
import argparse
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PyQt6.QtWidgets import QApplication
from veriyo_live.ubuntu_pack import PackLibrary,render_motion


def export(directory,version,target):
    app=QApplication.instance() or QApplication([])
    entry=PackLibrary(directory).entry(version)
    process=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','bgra',
                              '-s','1280x720','-r','15','-i','-','-an','-c:v','libx264','-preset','fast',
                              '-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(target)],stdin=subprocess.PIPE)
    try:
        for frame in range(round(entry.period*15)):
            image=render_motion(entry,frame/15,1280,720)
            process.stdin.write(image.constBits().asstring(image.sizeInBytes()))
        process.stdin.close()
        if process.wait()!=0:raise RuntimeError('Video encoding failed')
    except Exception:
        process.kill();process.wait();raise
    print(target)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',required=True,type=Path)
    parser.add_argument('--version',default='22.04')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();export(args.data,args.version,args.output)
