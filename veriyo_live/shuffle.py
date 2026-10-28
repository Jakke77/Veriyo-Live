"""Background identities and random selection; never changes desktop settings."""
from dataclasses import replace
import random
from .scenes import SCENES
from .ubuntu_pack import catalog

INTERVALS=((60,'1 minuutti'),(300,'5 minuuttia'),(900,'15 minuuttia'),(1560,'26 minuuttia'),(3600,'1 tunti'))


def background_options():
    return [('otava','Veriyö · Otava ja järvi'),('hiillos','Veriyö · Hiillos'),
            *((key,name) for key,(name,_) in SCENES.items()),
            *(('ubuntu:'+row['version'],f'Ubuntu {row["version"]} · {row["name"]}') for row in reversed(catalog()))]


def background_key(settings):
    return 'ubuntu:'+settings.ubuntu_version if settings.theme=='ubuntu' else settings.theme


def with_background(settings,key):
    if key not in dict(background_options()):raise ValueError('Tuntematon satunnaistausta.')
    if key.startswith('ubuntu:'):
        return replace(settings,theme='ubuntu',ubuntu_version=key.split(':',1)[1]).validate()
    return replace(settings,theme=key).validate()


def eligible_options(settings,pack_installed):
    result=[]
    for key,name in background_options():
        if key.startswith('ubuntu:') and not pack_installed:continue
        try:with_background(settings,key)
        except ValueError:continue
        result.append((key,name))
    return result


def choose_next(options,current,selected=(),rng=None):
    candidates=[key for key,_ in options if key!=current and (not selected or key in selected)]
    return (rng or random.SystemRandom()).choice(candidates) if candidates else None
