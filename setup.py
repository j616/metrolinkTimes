#!/usr/bin/env python3
from pathlib import Path
from distutils.core import setup

dataFiles = [
    ('lib/systemd/system', ['lib/systemd/system/metrolinkTimes.service']),
    ]

if not Path('/etc/metrolinkTimes/metrolinkTimes.conf').exists():
    dataFiles.append(('/etc/metrolinkTimes/', ['config/metrolinkTimes.conf']))

setup(name='metrolinkTimes',
      version='1.0',
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
