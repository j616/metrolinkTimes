#!/usr/bin/env python3
from pathlib import Path
from distutils.core import setup
import os
from pwd import getpwnam

dataFiles = [
    ('lib/systemd/system', ['lib/systemd/system/metrolinkTimes.service']),
    ]

if not Path('/etc/metrolinkTimes/metrolinkTimes.conf').exists():
    dataFiles.append(('/etc/metrolinkTimes/', ['config/metrolinkTimes.conf']))

logPath = '/var/log/metrolinkTimes/'
if not Path(logPath).exists():

    os.mkdir(logPath)
    getpwnam('mltimes').pw_uid
    os.chown(logPath, getpwnam('mltimes').pw_uid, getpwnam('mltimes').pw_gid)

setup(name='metrolinkTimes',
      version='1.3',
      description=('Track trams on the metrolink network & estimate their due '
                   'times'),
      author='James Sandford',
      author_email='metrolinktimes@j616s.co.uk',
      license=('Creative Commons Attribution-NonCommercial-ShareAlike 4.0 '
               'International License'),
      url='https://www.python.org/sigs/distutils-sig/',
      packages=['metrolinkTimes'],
      package_dir={'metrolinkTimes': 'src/metrolinkTimes'},
      package_data={'metrolinkTimes': ['data/stations.json']},
      scripts=['bin/metrolinkTimes'],
      data_files=dataFiles
      )
