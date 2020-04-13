# Metrolink Times

Metrolink Times provides an API that serves estimates for tram arrival times on the Manchester Metrolink network. Estimates use a rolling average for transit times between stops and dwell times at stops to provide reasonably accurate estimates that should addapt to traffic, changes in speed limits, heavy crowds etc.

## Installation

### Install from source

The following is used to install install in a venv for testing.

Install pyenv
```bash
curl https://pyenv.run | bash
```

Install Python 3.7
```bash
pyenv install 3.7.7
```
After installing, it may suggest to add initialization code to `~/.bashrc`. Do that.

Install Poetry
```bash
pip3 install --user poetry
```

Configure and install the environment used for this project.
__Run in the root of the cloned brewblox-tilt directory__
```bash
pyenv local 3.7.7
poetry install
```

During development, you need to have your environment activated. When it is activated, your terminal prompt is prefixed with (.venv).

Visual Studio code with suggested settings does this automatically whenever you open a .py file. If you prefer using a different editor, you can do it manually by running:
```bash
poetry shell
```

### Install using docker

A docker image for this package is available on [Docker Hub](https://hub.docker.com/r/j616s/metrolinktimes).

### Configure

Copy the [example config](https://github.com/j616/metrolinkTimes/blob/master/config/metrolinkTimes.conf) to `/etc/metrolinkTimes/metrolinkTimes.conf`. OR if you're using docker, mount it at that location in the container. Edit the config to include your API Key for the [TfGM API](https://developer.tfgm.com/) and if you want to change the CORS Access Control Origin settings from allow all. The API **will not work** if you do not add a key for the TfGM API. If you want to change the default port the API is served on from 5000, add a `"port": <portNum>` line to the config.

## Usage

The API will present itself on port on port 5000 by default. If you're installing from source, run metrolinkTimes from the command line in the repo directory. Logs are placed in `/var/log/metrolinkTimes.log` if running locally or are available through `docker logs` in docker.

### /

Returns

```
{
    "paths": ["debug/", "station/"]
}
```

### /debug/

Returns

```
{
  "missingAverages": {
    "edges": [
      <edges without average transit times>
    ],
    "platforms": [
      <platforms without average dwell times>
    ]
  },
  "trams": {
    "departed": {
      <platform name>: [
        {
          "arriveTime": <time arrived at platform>,
          "averageDwell": <average dwell time at platform>,
          "carriages": <Single|Double>,
          "departTime": <time departed platform>,
          "dest": <destination station>,
          "dwellTime": <this trams dwell time at platform>,
          "predictions": {
            <platform name>: <predicted arrival time>
            },
          "via": <station TfGM data says this tram is going via>
        }
      ]
    },
    "here": {
      <platform name>: [
        {
          "arriveTime": <time arrived at platform>,
          "carriages": <Single|Double>,
          "dest": <destination station>,
          "via": <station TfGM data says this tram is going via>,
          "predictions": {
            <platform name>: <predicted arrival time>
            }
        }
      ]
    }
```

Platforms are identified as `<station name>_<platform atco code>`. Trams 'departing' have left the station and are in transet to to the next. Trams 'here' are either arriving at a station (As shown by flashing 'Arriving' on the displays at stations) or are at the platform. Unfortunately, the TfGM data doesn't provide seperate states for these. They do provide an 'arrived' and 'departing' state but the difference between these isn't clear and may be based on timetabled departure times.

### /station/

Returns

```
{
    "stations": ["<station names>/"]
}
```

### /station/\<station name>/

Returns

```
{
    "platforms": ["<platform atco codes>/"]
}
```

Setting `verbose=true` in the query string will return a dict of platforms with the data for each. You can also use the platform quer strings for this data.

### /station/\<station name>/\<platform atco code>/

Returns

```
{
  "averageDwellTime": <average dwell time in secs>,
  "dwellTimes": [
    <5 most recent dwell times in secs>
  ],
  "mapPos": {
    "x": <a vaguely sensible map x co-ordinate>,
    "y": <a vaguely sensible map y co-ordinate>
  },
  "predecessors": {
    <platform that can reach this platform>: {
      "averageTransitTime": <average transit time from predecessor platform to this in secs>,
      "transitTimes": [
        <5 most recent transit times from predecessor platform to this in secs>
      ]
    }
  },
  "message": <message displayed at the bottom of platform displays>,
  "predictions": [
    {
      "carriages": <Single|Double>,
      "curLoc": {
        "platform": <platform name>,
        "status": <dueStartsHere|here|departed>
      },
      "dest": <destination station>,
      "predictedArriveTime": <predicted arrival time>,
      "predictions": {
        <platform name>: <predicted arrival time>
      },
      "via": <station TfGM data says this tram is going via>
    }
  ],
  "here": [
    {
      "arriveTime": <time arrived at platform>,
      "carriages": <Single|Double>,
      "dest": <destination station>,
      "predictions": {
        <platform name>: <predicted arrival time>
      },
      "via": <station TfGM data says this tram is going via>
    }
  ],
  "departed": [
    {
      "arriveTime": <time tram arrived at platform>,
      "averageDwell": <average dwell at platform in secs>,
      "carriages": <Single|Double>,
      "departTime": <time tram departed platform>,
      "dest": <destination station>,
      "dwellTime": <dwell time of this tram at platform>,
      "predictions": {
        <platform name>: <predicted arrival time>
      },
      "via": <station TfGM data says this tram is going via>
    }
  ],
  "updateTime": <time TfGM data says this data was updated>
}
```

The following query strings can be set to `true` or `false` to enable/disable some data items in the returned json.

| parameter       | default | data items this affects                            |
| --------------- | ------- | -------------------------------------------------- |
| pedictions      | true    | predictions, here                                  |
| tramPredictions | true    | predictions within tram's data                     |
| message         | true    | message                                            |
| meta            | false   | mapPos, dwellTimes, averageDwellTime, predecessors |
| departed        | false   | departed                                           |

## Random scripts

### tramGraph.py

Running this on its own will bring up a render of the platforms and their connections to each other

### genStations.py

This is the script that was used to generate stations.json. It requires manually selection which stations feed into others among other things. It's slow, tedious, and almost certainly the wrong way to go about it. Some of the data in stations.json was added manually after using this script. Mainly because once I generated it, I didn't want to face using the script again....
