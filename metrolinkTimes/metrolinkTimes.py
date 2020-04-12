#!/usr/bin/python3
import asyncio
import json
from datetime import datetime, timedelta
from sys import exit
import logging

import tornado.web
from tornado.web import RequestHandler
from tornado import escape
from tornado.httpserver import HTTPServer

from metrolinkTimes.tfgmMetrolinksAPI import TFGMMetrolinksAPI
from metrolinkTimes.tramGraph import TramGraph

logging.basicConfig(filename='/var/log/metrolinkTimes/metrolinkTimes.log',
                    format='%(asctime)s %(levelname)s %(pathname)s %(lineno)s '
                           '%(message)s',
                    level=logging.ERROR)


def dt_handler(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, timedelta):
        return obj.total_seconds()

    raise TypeError


def json_encode(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=dt_handler)


escape.json_encode = json_encode


class GraphUpdater:
    def __init__(self, graph):
        self.api = TFGMMetrolinksAPI()
        self.graph = graph
        self.stationMappings = {
            "Ashton-under-Lyne": "Ashton-Under-Lyne",
            "Deansgate Castlefield": "Deansgate - Castlefield",
            "Deansgate": "Deansgate - Castlefield",
            "Ashton": "Ashton-Under-Lyne",
            "MCUK": "MediaCityUK",
            "Newton Heath": "Newton Heath and Moston",
            "Victoria Millgate Siding": "Victoria",
            "Rochdale Stn": "Rochdale Railway Station",
            "Trafford Centre": "intu Trafford Centre"
        }

    def update(self):
        data = self.api.getData()

        if data is None:
            # Internet down?
            return

        tramsVia = []

        for station in data:
            for platform in data[station]:
                nodeID = "{}_{}".format(station, platform)
                if nodeID not in self.graph.getNodes():
                    logging.error("ERROR: Unknown platfrom {}".format(nodeID))
                    continue

                pidTramData = []
                message = None
                updateTime = None

                apiPID = data[station][platform][0]
                if not (apiPID["MessageBoard"].startswith("^F0")
                        or (apiPID["MessageBoard"] == "<no message>")):
                    message = apiPID["MessageBoard"]

                # This seems to be how flashing is encoded. We'll get rid of it
                if message is not None:
                    message = message.replace("^$", "")

                updateTime = datetime.strptime(
                    apiPID["LastUpdated"],
                    "%Y-%m-%dT%H:%M:%SZ")

                if self.graph.getLastUpdateTime(nodeID) == updateTime:
                    return

                for i in range(4):
                    if apiPID["Dest{}".format(i)] != "":
                        stationName = apiPID["Dest{}".format(i)]
                        # TODO: Shift this & station mappings to tramGraph
                        validDests = (list(self.graph.getStations())
                                      + [
                                            "Terminates Here",
                                            "See Tram Front",
                                            "Not in Service"])
                        viaName = None

                        if " via " in stationName:
                            splitName = stationName.split(" via ")
                            stationName = splitName[0]
                            viaName = splitName[1]
                        if stationName in self.stationMappings:
                            stationName = self.stationMappings[stationName]
                        if viaName in self.stationMappings:
                            viaName = self.stationMappings[viaName]
                            if viaName not in tramsVia:
                                tramsVia.append(viaName)
                        if stationName not in validDests:
                            logging.error(
                                "Unknown station {}".format(stationName))
                            continue
                        if (viaName is not None) and (
                          viaName not in validDests):
                            logging.error("Unknown station {}".format(viaName))
                            viaName = None

                        pidTramData.append({
                            "dest": stationName,
                            "via": viaName,
                            "carriages": apiPID["Carriages{}".format(i)],
                            "status": apiPID["Status{}".format(i)],
                            "wait": int(apiPID["Wait{}".format(i)])
                        })

                self.graph.updatePlatformPID(
                    nodeID,
                    pidTramData,
                    message,
                    updateTime)

        self.graph.decodePIDs()
        self.graph.clearOldDeparted()
        self.graph.locateDepartingTrams()
        self.graph.locateTramsAt()
        self.graph.clearNodePredictions()

        # We need to predict trams at definitively known locations first
        # so we can use these predictions to verify if trams are actually
        # starting at other stops
        self.graph.predictTramTimes(["tramsHere", "tramsDeparted"])

        self.graph.debounceNew()

        self.graph.gatherTramPredictions(["tramsHere", "tramsDeparted"])

        self.graph.locateApproachingTrams()
        self.graph.predictTramTimes(["tramsApproaching"])
        self.graph.gatherTramPredictions(["tramsApproaching"])
        self.graph.locateApproachingTrams()

        self.graph.clearNodePredictions()
        self.graph.gatherTramPredictions(["tramsHere",
                                          "tramsDeparted",
                                          "tramsApproaching"])

        # This might not be needed. Could just look like doubling up because of
        # routes being run on day of testing
        self.graph.finalisePredictions()

        self.graph.setLocalUpdateTime(datetime.now())

        tramsAts = self.graph.getTramsHeres()
        tramsAt = 0

        tramsDeparteds = self.graph.getTramsDeparteds()
        tramsDeparted = 0

        tramsStartings = self.graph.getTramsStarting()
        tramsStarting = 0
        platformsStarting = 0
        stationsStarting = set()

        for node in tramsAts:
            tramsAt = tramsAt + len(tramsAts[node])

        for node in tramsDeparteds:
            tramsDeparted = tramsDeparted + len(tramsDeparteds[node])

        for node in tramsStartings:
            tramsStarting = tramsStarting + len(tramsStartings[node])
            if len(tramsStartings[node]):
                platformsStarting += 1
                stationsStarting.add(self.graph.DG.nodes[node]["stationName"])

        logging.info("Len nodes without average: {}".format(
            len(self.graph.nodesNoAvDwell())))
        logging.info("Len edges without average: {}".format(
            len(self.graph.edgesNoAvTrans())))
        logging.info("trams at stations: {}".format(tramsAt))
        logging.info("trams departed stations: {}".format(tramsDeparted))
        logging.info("trams yet to start at stations: {}".format(
            tramsStarting))
        logging.info("platforms with trams starting: {}/{}".format(
            platformsStarting,
            len(self.graph.getNodes())))
        logging.info("stations with trams starting ({}/{}): {}".format(
            len(stationsStarting),
            len(self.graph.getStations()),
            stationsStarting))
        logging.info("trams are going via {}".format(tramsVia))

    async def updateLoop(self):
        while True:
            self.update()
            await asyncio.sleep(1)


class BaseHandler(RequestHandler):
    def initialize(self, graph):
        self.graph = graph

    def set_default_headers(self, *args, **kwargs):
        origin = "*"
        with open("/etc/metrolinkTimes/metrolinkTimes.conf") as conf_file:
            origin = json.load(conf_file)["Access-Control-Allow-Origin"]
        self.set_header("Access-Control-Allow-Origin", origin)
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header("Access-Control-Allow-Methods", "GET, OPTIONS")


class MainHandler(BaseHandler):
    def get(self):
        self.write({"paths": [
            "debug/",
            "health/",
            "station/"
        ]})


class DebugHandler(BaseHandler):
    def get(self):
        here = self.graph.getTramsHeres()
        dep = self.graph.getTramsDeparteds()
        start = self.graph.getTramsStarting()
        ret = {
            "missingAverages": {
                "platforms": self.graph.nodesNoAvDwell(),
                "edges": self.graph.edgesNoAvTrans()
            },
            "trams": {
                "here": {k: here[k] for k in here if here[k] != []},
                "departed": {k: dep[k] for k in dep if dep[k] != []},
                "starting": {k: start[k] for k in start if start[k] != []}
            }
        }

        self.write(ret)


class StationHandler(BaseHandler):
    def get(self):
        ret = ["{}/".format(station) for station in self.graph.getStations()]
        self.write({"stations": ret})


class StationNameHandler(BaseHandler):
    def get(self, stationName):
        def getArg(name, default):
            arg = self.get_query_arguments(name)
            if arg == []:
                arg = default
            else:
                arg = arg[0]

            return arg

        if stationName not in self.graph.getStations():
            raise tornado.web.HTTPError(404)

        ret = {}

        if getArg("verbose", "false").lower() != "true":
            stationPlatforms = self.graph.getStationPlatforms(stationName)
            ret["platforms"] = [
                "{}/".format(platID) for platID in stationPlatforms]
        else:
            ret["platforms"] = {}
            for platID in self.graph.getStationPlatforms(stationName):
                nodeID = "{}_{}".format(stationName, platID)
                ret["platforms"][platID] = {
                    "updateTime": self.graph.getLastUpdateTime(nodeID),
                }

                if getArg("predictions", "true").lower() == "true":
                    predictions = self.graph.getNodePredictions()[nodeID]
                    if getArg("tramPredictions", "true").lower() == "false":
                        for tram in predictions:
                            del(tram["predictions"])
                    ret["platforms"][platID]["predictions"] = predictions
                    ret["platforms"][platID]["here"] = (
                        self.graph.getTramsHeres()[nodeID])

                if getArg("message", "true").lower() == "true":
                    ret["platforms"][platID]["message"] = (
                        self.graph.getMessage(nodeID))

                if getArg("meta", "false").lower() == "true":
                    dwellTimes = self.graph.getDwellTimes()[nodeID]
                    averageDwell = timedelta()
                    for dwellTime in dwellTimes:
                        averageDwell = averageDwell + dwellTime
                    if len(dwellTimes) > 0:
                        averageDwell = averageDwell/len(dwellTimes)
                    else:
                        averageDwell = None

                    pred = {}
                    for pNodeID in self.graph.getNodePreds(nodeID):
                        pred[pNodeID] = {
                            "transitTimes": self.graph.getTransit(
                                pNodeID, nodeID)
                            }

                        (pred[pNodeID]["averageTransitTime"],
                            isDirectAverage) = self.graph.getAverageTransit(
                                pNodeID,
                                nodeID)

                    ret["platforms"][platID]["mapPos"] = {
                        "x": self.graph.getMapPos(nodeID)[0],
                        "y": self.graph.getMapPos(nodeID)[1]
                        }
                    ret["platforms"][platID]["dwellTimes"] = dwellTimes
                    ret["platforms"][platID]["averageDwellTime"] = averageDwell
                    ret["platforms"][platID]["predecessors"] = pred

            if getArg("departed", "false").lower() == "true":
                ret["platforms"][platID]["departed"] = (
                    self.graph.getTramsDeparteds()[nodeID])

        self.write(ret)


class StationNamePlatHandler(BaseHandler):
    def get(self, stationName, platID):
        def getArg(name, default):
            arg = self.get_query_arguments(name)
            if arg == []:
                arg = default
            else:
                arg = arg[0]

            return arg

        nodeID = "{}_{}".format(stationName, platID)
        if nodeID not in self.graph.getNodes():
            raise tornado.web.HTTPError(404)

        ret = {
            "updateTime": self.graph.getLastUpdateTime(nodeID),
        }

        if getArg("predictions", "true").lower() == "true":
            predictions = self.graph.getNodePredictions()[nodeID]
            if getArg("tramPredictions", "true").lower() == "false":
                for tram in predictions:
                    del(tram["predictions"])
            ret["predictions"] = predictions
            ret["here"] = self.graph.getTramsHeres()[nodeID]

        if getArg("message", "true").lower() == "true":
            ret["message"] = self.graph.getMessage(nodeID)

        if getArg("meta", "false").lower() == "true":
            dwellTimes = self.graph.getDwellTimes()[nodeID]
            averageDwell = timedelta()
            for dwellTime in dwellTimes:
                averageDwell = averageDwell + dwellTime
            if len(dwellTimes) > 0:
                averageDwell = averageDwell/len(dwellTimes)
            else:
                averageDwell = None

            pred = {}
            for pNodeID in self.graph.getNodePreds(nodeID):
                pred[pNodeID] = {
                    "transitTimes": self.graph.getTransit(pNodeID, nodeID)
                    }

                (pred[pNodeID]["averageTransitTime"],
                    isDirectAverage) = self.graph.getAverageTransit(
                        pNodeID, nodeID)

            ret["mapPos"] = {
                "x": self.graph.getMapPos(nodeID)[0],
                "y": self.graph.getMapPos(nodeID)[1]
                }
            ret["dwellTimes"] = dwellTimes
            ret["averageDwellTime"] = averageDwell
            ret["predecessors"] = pred

        if getArg("departed", "false").lower() == "true":
            ret["departed"] = self.graph.getTramsDeparteds()[nodeID]

        self.write(ret)


class HealthHandler(BaseHandler):
    def get(self):
        now = datetime.now()
        lastUpdated = self.graph.getLocalUpdateTime()
        updateDelta = now - lastUpdated

        logging.debug("DEBUG: update delta {}".format(updateDelta))

        if updateDelta > timedelta(seconds=30):
            exit(1)

        self.write("ok")


class Application():
    async def run():
        graph = TramGraph()
        gu = GraphUpdater(graph)
        loop = asyncio.get_event_loop()
        ul = loop.create_task(gu.updateLoop())

        handlerArgs = {"graph": graph}

        application = tornado.web.Application([
           (r"/", MainHandler, handlerArgs),
           (r"/debug/?", DebugHandler, handlerArgs),
           (r"/health/?", HealthHandler, handlerArgs),
           (r"/station/?", StationHandler, handlerArgs),
           (r"/station/([^/]*)/?", StationNameHandler, handlerArgs),
           (r"/station/([^/]*)/([^/]*)/?", StationNamePlatHandler, handlerArgs
            ),
        ])

        port = 5000

        server = HTTPServer(application)
        server.listen(port)

        await ul
