"""Independent lunar references, sky orientation, visible motion and native plans."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from PyQt6.QtGui import QImage
from veriyo_live.app import Window
from veriyo_live.calendar import ZONE
from veriyo_live.celestial import (blood_progress, equatorial_stars, local_day_bounds,
                                   moon_at, moon_day, moon_horizontal, stars_at)
from veriyo_live.engine import Engine
from veriyo_live.render import render
from veriyo_live.scenes import PERIOD, SCENES, SceneEntry, render_scene, sky_point
from veriyo_live.settings import Settings
from test_live import FakeBackend, spin_until, APP
from test_windows_lock import FakeWindowsBackend

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026,10,28,19,tzinfo=timezone.utc)


class CelestialTests(unittest.TestCase):
    def test_north_view_cardinals_and_zenith_are_not_mirrored(self):
        north=sky_point(0,0,100,200,10)
        west=sky_point(0,270,100,200,10)
        east=sky_point(0,90,100,200,10)
        zenith=sky_point(90,0,100,200,10)
        self.assertAlmostEqual(north.x(),100);self.assertAlmostEqual(north.y(),200)
        self.assertAlmostEqual(west.x(),80);self.assertAlmostEqual(west.y(),200)
        self.assertAlmostEqual(east.x(),120);self.assertAlmostEqual(east.y(),200)
        self.assertAlmostEqual(zenith.x(),100);self.assertAlmostEqual(zenith.y(),180)

    def test_screenshot_evening_otava_is_below_and_west_of_polaris(self):
        moment=datetime(2026,10,28,20,24,tzinfo=ZONE)
        stars={hip:(alt,az) for hip,_,alt,az,_ in stars_at(int(moment.timestamp()),65.071562,25.507046)}
        pole=sky_point(*stars[11767],0,0,1)
        for hip in (54061,53910,58001,59774,62956,65378,67301):
            point=sky_point(*stars[hip],0,0,1)
            self.assertIsNotNone(point)
            self.assertGreater(point.y(),pole.y())
        tail=sky_point(*stars[67301],0,0,1)
        self.assertLess(tail.x(),pole.x())

    def test_star_projection_matches_independent_reference_directions(self):
        # Reference fixtures were computed independently with Astropy/ERFA.
        fixture=json.loads((ROOT/'tests/otava-astropy.json').read_text())
        from veriyo_live.sky import sky_at
        for case in fixture['fixtures']:
            moment=datetime.fromisoformat(case['utc'])
            for star,expected in zip(sky_at(moment,fixture['latitude'],fixture['longitude']),case['stars']):
                actual=sky_point(star.altitude,star.azimuth,0,0,1)
                reference=sky_point(expected['altitude'],expected['azimuth'],0,0,1)
                self.assertEqual(actual is None,reference is None)
                if actual is not None:
                    self.assertAlmostEqual(actual.x(),reference.x(),delta=.005)
                    self.assertAlmostEqual(actual.y(),reference.y(),delta=.005)

    def test_back_sky_and_below_horizon_do_not_fold_into_north_view(self):
        self.assertIsNone(sky_point(0,180,0,0,1))
        self.assertIsNone(sky_point(45,180,0,0,1))
        self.assertIsNone(sky_point(-10,0,0,0,1))
        self.assertIsNone(sky_point(10,170,0,0,1))

    def test_moon_matches_independent_astropy_topocentric_reference(self):
        cases=json.loads((ROOT/'tests/moon-astropy.json').read_text())['cases']
        for case in cases:
            with self.subTest(utc=case['utc'],latitude=case['latitude']):
                result=moon_at(datetime.fromisoformat(case['utc']),case['latitude'],case['longitude'])
                self.assertAlmostEqual(result.altitude,case['altitude'],delta=.025)
                self.assertLess(abs((result.azimuth-case['azimuth']+180)%360-180),.025)
                self.assertAlmostEqual(result.illumination,case['illumination'],delta=.006)

    def test_new_catalog_matches_independent_otava_reference(self):
        fixture=json.loads((ROOT/'tests/otava-astropy.json').read_text())
        names=dict(zip(('Dubhe','Merak','Phecda','Megrez','Alioth','Mizar','Alkaid'),
                       (54061,53910,58001,59774,62956,65378,67301)))
        for case in fixture['fixtures']:
            moment=datetime.fromisoformat(case['utc'])
            result={s[0]:s for s in stars_at(int(moment.timestamp()),fixture['latitude'],fixture['longitude'])}
            for expected in case['stars']:
                actual=result[names[expected['name']]]
                self.assertAlmostEqual(actual[2],expected['altitude'],delta=.025)
                self.assertLess(abs((actual[3]-expected['azimuth']+180)%360-180),.15)

    def test_polaris_stays_near_true_north_and_below_southern_horizon(self):
        polaris=next(s for s in equatorial_stars(NOW.date()) if s[0]==11767)
        self.assertGreater(polaris[3],89)
        for hour in range(0,24,3):
            moment=NOW+timedelta(hours=hour)
            north=next(s for s in stars_at(int(moment.timestamp()),65.071562,25.507046) if s[0]==11767)
            self.assertAlmostEqual(north[2],65.071562,delta=.75)
            self.assertLess(abs((north[3]+180)%360-180),2)
            south=next(s for s in stars_at(int(moment.timestamp()),-33.8688,151.2093) if s[0]==11767)
            self.assertLess(south[2],0)

    def test_day_bounds_respect_23_and_25_hour_dst_days(self):
        for day,hours in ((date(2026,3,29),23),(date(2026,10,25),25)):
            a,b=local_day_bounds(day,'Europe/Helsinki')
            self.assertEqual((b-a).total_seconds(),hours*3600)

    def test_moon_events_really_cross_the_chosen_horizon_in_the_local_day(self):
        day=date(2026,11,5);zone='Australia/Sydney';lat,lon=-33.8688,151.2093
        samples,events=moon_day(day,lat,lon,zone)
        self.assertGreaterEqual(len(events),1)
        for kind,moment in events:
            self.assertEqual(moment.astimezone(ZoneInfo(zone)).date(),day)
            before=moon_horizontal(moment-timedelta(minutes=2),lat,lon)[0]+.833
            after=moon_horizontal(moment+timedelta(minutes=2),lat,lon)[0]+.833
            self.assertLess(before*after,0)
            self.assertEqual(kind=='Nousu',after>before)

    def test_lunar_phase_has_correct_full_new_and_waxing_states(self):
        new=moon_at(datetime(2026,11,9,12,tzinfo=timezone.utc),65,25)
        full=moon_at(datetime(2026,11,24,12,tzinfo=timezone.utc),65,25)
        waxing=moon_at(datetime(2026,10,18,12,tzinfo=timezone.utc),65,25)
        self.assertLess(new.illumination,.015)
        self.assertGreater(full.illumination,.98)
        self.assertTrue(waxing.waxing)
        self.assertFalse(moon_at(NOW,65,25).waxing)

    def test_blood_year_progress_and_dst_cutover(self):
        epoch=datetime(2026,6,26,1,7,7,tzinfo=ZONE)
        self.assertEqual(blood_progress(epoch),(0,0,0))
        self.assertEqual(blood_progress(epoch+timedelta(days=777)),(777,0,0))
        a=datetime(2026,10,25,1,7,7,tzinfo=ZONE).astimezone(timezone.utc)
        b=datetime(2026,10,26,1,7,7,tzinfo=ZONE).astimezone(timezone.utc)
        self.assertAlmostEqual(blood_progress(a+(b-a)/2)[1],.5)


class SceneTests(unittest.TestCase):
    def test_both_sky_scenes_draw_otava_at_north_facing_screen_positions(self):
        from veriyo_live.render import project
        moment=datetime(2026,10,28,20,24,tzinfo=ZONE)
        stars={hip:(alt,az) for hip,_,alt,az,_ in stars_at(int(moment.timestamp()),65.071562,25.507046)}
        for theme in ('polaris','moon'):
            image=render_scene(moment,Settings(theme=theme,date_mode='none'),1920,1080,0)
            for hip in (11767,67301):
                x,y=project(*stars[hip])
                px=round(1920*.35+x*min(1920*.145,1080*.31))
                py=round(1080*.76+y*min(1920*.145,1080*.31))
                self.assertGreater(max(image.pixelColor(xx,yy).blue()
                    for xx in range(px-2,px+3) for yy in range(py-2,py+3)),180,(theme,hip))

    def test_moon_outside_north_view_has_explicit_notice_even_without_guides(self):
        import veriyo_live.scenes as scenes
        moon=replace(moon_at(NOW,65,25),altitude=45,azimuth=180)
        with patch.object(scenes,'moon_at',return_value=moon),patch.object(scenes,'label',wraps=scenes.label) as labels:
            render_scene(NOW,Settings(theme='moon',guides=False,date_mode='none'),640,360,0)
        values=[call.args[2] for call in labels.call_args_list]
        self.assertIn('Kuu on pohjoisnäkymän ulkopuolella',values)
        self.assertNotIn('Kuu on horisontin alapuolella',values)

    def test_settings_migrate_and_allow_global_new_sky_locations(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json';path.write_text('{"theme":"otava"}')
            self.assertEqual(Settings.load(path).timezone,'Europe/Helsinki')
            for theme in SCENES:
                value=Settings(theme=theme,latitude=-33.8688,longitude=151.2093,timezone='Australia/Sydney')
                value.save(path);self.assertEqual(Settings.load(path),value)
            with self.assertRaises(ValueError):Settings(latitude=-33).validate()
            with self.assertRaises(ValueError):Settings(timezone='../invalid').validate()

    def test_every_scene_has_observable_motion_without_changing_astronomical_time(self):
        for theme in SCENES:
            with self.subTest(theme=theme):
                settings=Settings(theme=theme,date_mode='none')
                a=render_scene(NOW,settings,640,360,0)
                b=render_scene(NOW,settings,640,360,8)
                changed=sum(x!=y for x,y in zip(a.constBits().asstring(a.sizeInBytes()),b.constBits().asstring(b.sizeInBytes())))
                self.assertGreater(changed,1000)
                self.assertEqual(a,render_scene(NOW,settings,640,360,PERIOD))

    def test_all_scenes_render_portrait_and_southern_sky_without_extra_pack(self):
        for theme in SCENES:
            image=render(NOW,Settings(theme=theme,latitude=-33.8,longitude=151.2,timezone='Australia/Sydney'),480,720)
            self.assertFalse(image.isNull())
            self.assertEqual((image.width(),image.height()),(480,720))

    def test_windows_scene_survives_lock_rejection_updates_and_restores(self):
        with tempfile.TemporaryDirectory() as folder:
            adapter=FakeWindowsBackend();adapter.lock_error='rejected'
            engine=Engine(folder,adapter_factory=lambda:adapter);engine.timer.stop()
            try:
                engine.start(Settings(theme='deep_space',lock_screen=True),640,360)
                spin_until(lambda:not engine.busy)
                first=engine.motion_entry
                self.assertTrue(engine.running);self.assertIsInstance(first,SceneEntry)
                engine.last_update-=61;engine.last_wall_time-=61;engine.tick()
                spin_until(lambda:not engine.busy)
                self.assertIs(engine.motion_entry,first)
                engine.set_date_mode('none');spin_until(lambda:not engine.busy)
                self.assertEqual(engine.motion_entry.settings.date_mode,'none')
                self.assertEqual(adapter.lock_calls,['Backup','Set'])
                engine.stop();spin_until(lambda:not engine.busy)
                self.assertIsNone(engine.motion_entry)
                self.assertFalse(QImage(str(Path(folder)/'scene-paused.jpg')).isNull())
                engine.restore();spin_until(lambda:not engine.busy)
                self.assertEqual(adapter.current,'original-desktop')
                self.assertEqual(adapter.lock_image,b'original-lock')
            finally:
                if engine.busy:spin_until(lambda:not engine.busy)
                engine.deleteLater()

    def test_gnome_scene_uses_bounded_real_frames_native_xml_and_safe_restore(self):
        class Gnome(FakeBackend):
            kind='gnome'
            def apply_paths(self,desktop,lock,journal):
                self.current=str(Path(desktop).resolve())
        with tempfile.TemporaryDirectory() as folder:
            adapter=Gnome();engine=Engine(folder,adapter_factory=lambda:adapter);engine.timer.stop()
            try:
                engine.start(Settings(theme='bloodwork'),640,360);spin_until(lambda:not engine.busy)
                for _ in range(2):
                    engine.last_update-=61;engine.last_wall_time-=61;engine.tick();spin_until(lambda:not engine.busy)
                root=ET.parse(adapter.current).getroot()
                self.assertEqual(len(root.findall('static')),16)
                total=sum(float(x.findtext('duration')) for x in root if x.tag in ('static','transition'))
                self.assertAlmostEqual(total,PERIOD)
                for entry in root.findall('static'):
                    self.assertFalse(QImage(entry.findtext('file')).isNull())
                self.assertEqual(len(list(Path(folder).glob('scene-*/*.jpg'))),32)
                journal=json.loads((Path(folder)/'wallpaper-backup.json').read_text())
                self.assertLessEqual(len(journal['frames']),4)
                engine.stop();spin_until(lambda:not engine.busy)
                engine.restore();spin_until(lambda:not engine.busy)
                self.assertEqual(adapter.current,'original')
            finally:
                if engine.busy:spin_until(lambda:not engine.busy)
                engine.deleteLater()

    def test_four_theme_choices_and_timezone_are_available_and_persist(self):
        with tempfile.TemporaryDirectory() as folder:
            window=Window(Settings(),folder);window.engine.timer.stop();window.preview_timer.stop()
            try:
                for theme in SCENES:
                    index=window.theme.findData(theme);self.assertGreaterEqual(index,0)
                    window.theme.setCurrentIndex(index)
                    self.assertFalse(window.timezone.isHidden())
                window.theme.setCurrentIndex(window.theme.findData('moon'))
                window.latitude.setValue(-33.8688);window.longitude.setValue(151.2093)
                window.timezone.setCurrentText('Australia/Sydney')
                with patch('veriyo_live.app.set_autostart'):self.assertTrue(window.save())
                saved=Settings.load(Path(folder)/'settings.json')
                self.assertEqual(saved.timezone,'Australia/Sydney')
                self.assertEqual(saved.theme,'moon')
                window.theme.setCurrentIndex(window.theme.findData('otava'))
                self.assertGreaterEqual(window.latitude.value(),60)
            finally:
                window.allow_quit=True;window.close()
