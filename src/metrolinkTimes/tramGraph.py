#!/usr/bin/env python3

import json
import operator
import networkx as nx
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import logging
import os


class TramGraph:
    def __init__(self):
        self.DG = nx.DiGraph()
        self.pos = {}
        self.stations = []
        self.firstRun = True

        data = json.load(open("{}/data/stations.json".format(
            os.path.dirname(__file__))))
        self.stations = data.keys()
        for s in data:
            for p in data[s]:
                nodeID = "{}_{}".format(s, p)
                self.DG.add_node(nodeID)
                self.DG.nodes[nodeID]["stationName"] = s
                self.DG.nodes[nodeID]["platformID"] = p
                self.DG.nodes[nodeID]["pidTrams"] = []
                self.DG.nodes[nodeID]["tramsAt"] = []
                self.DG.nodes[nodeID]["tramsArriving"] = []
                self.DG.nodes[nodeID]["tramsApproaching"] = []
                self.DG.nodes[nodeID]["prevTramsApproaching"] = []
                self.DG.nodes[nodeID]["tramsHere"] = []
                self.DG.nodes[nodeID]["tramsDeparted"] = []
                self.DG.nodes[nodeID]["predictedArrivals"] = []
                self.DG.nodes[nodeID]["dwellTimes"] = []
                self.DG.nodes[nodeID]["message"] = None
                self.DG.nodes[nodeID]["updateTime"] = datetime.min

                self.pos[nodeID] = [
                    data[s][p]["map"]["x"], data[s][p]["map"]["y"]]

                for inSP in data[s][p]["stationsBefore"]:
                    inS = None

                    for thisInS in data:
                        if inSP in data[thisInS]:
                            inS = thisInS

                    self.DG.add_edge("{}_{}".format(inS, inSP), nodeID)
                    self.DG.edges[
                        "{}_{}".format(inS, inSP), nodeID]["transitTimes"] = []

                    if data[s][p].get("terminating", False):
                        self.DG.edges[
                            "{}_{}".format(inS, inSP), nodeID]["weight"] = 2
                    else:
                        self.DG.edges[
                            "{}_{}".format(inS, inSP), nodeID]["weight"] = 1

    def updatePlatformPID(self, nodeID, PIDTramData, message, updateTime):
        self.DG.nodes[nodeID]["pidTrams"] = PIDTramData
        self.DG.nodes[nodeID]["message"] = message
        self.DG.nodes[nodeID]["updateTime"] = updateTime

    def decodePID(self, node):
        # Locate trams & seperate by PID state
        self.DG.nodes[node]["tramsAt"] = []
        self.DG.nodes[node]["tramsArriving"] = []
        self.DG.nodes[node]["prevTramsApproaching"] = self.DG.nodes[node][
            "tramsApproaching"]
        self.DG.nodes[node]["tramsApproaching"] = []
        for tram in self.DG.nodes[node]["pidTrams"]:
            tramHere = True
            if tram["dest"] in [
              "Terminates Here",
              "See Tram Front",
              "Not in Service"]:
                continue

            for pNode in self.DG.pred[node]:
                for pTram in self.DG.nodes[pNode]["pidTrams"]:
                    if (
                        (tram["dest"] == pTram["dest"]) and
                        (tram["carriages"] == pTram["carriages"]) and
                        (tram["wait"] > pTram["wait"])
                      ):
                        tramHere = False
            if tramHere:
                status = tram["status"]
                del(tram["status"])
                # We'll remove duplicates at the same time here
                # Can happen on stops with multiple PIDs or with bugs in the
                # data
                if status == "Departing":
                    if tram not in self.DG.nodes[node]["tramsAt"]:
                        self.DG.nodes[node]["tramsAt"].append(tram)
                elif status == "Arrived":
                    if tram not in self.DG.nodes[node]["tramsArriving"]:
                        self.DG.nodes[node]["tramsArriving"].append(tram)
                elif status == "Due":
                    if tram not in self.DG.nodes[node]["tramsApproaching"]:
                        self.DG.nodes[node]["tramsApproaching"].append(tram)
                else:
                    logging.error("Unknown tram status: {}".format(status))

        # Find doubles with a second entry as a single and remove the single
        # This gets around a bug in the TFGM data
        tramsAtArr = (self.DG.nodes[node]["tramsAt"]
                      + self.DG.nodes[node]["tramsArriving"]
                      + self.DG.nodes[node]["tramsApproaching"])

        for tram in tramsAtArr:
            if tram["carriages"] == "Double":
                for tram2 in tramsAtArr:
                    if ((tram["dest"] == tram2["dest"])
                       and (tram["wait"] == tram2["wait"])
                       and (tram2["carriages"] == "Single")):
                        if tram2 in self.DG.nodes[node]["tramsAt"]:
                            self.DG.nodes[node]["tramsAt"].remove(tram2)
                        elif tram2 in self.DG.nodes[node]["tramsArriving"]:
                            self.DG.nodes[node]["tramsArriving"].remove(tram2)
                        elif tram2 in self.DG.nodes[node]["tramsApproaching"]:
                            self.DG.nodes[node]["tramsApproaching"].remove(
                                tram2)

    def calcTramDwell(self, tramsDeparted, node):
        # Calculate dwell times for departed trams & place departed tram in
        # "tramsDeparted" array
        if tramsDeparted != []:
            for tram in tramsDeparted:
                if "status" in tram:
                    del(tram["status"])
                if "wait" in tram:
                    del(tram["wait"])
                tram["departTime"] = self.DG.nodes[node]["updateTime"]

                if tram["arriveTime"] is None:
                    tram["dwellTime"] = None
                else:
                    tram["dwellTime"] = tram["departTime"] - tram["arriveTime"]
                    if tram["dwellTime"] != timedelta():
                        self.DG.nodes[node]["dwellTimes"].append(
                            tram["dwellTime"])
                        # Only keep track of 5 most recent dwell times
                        self.DG.nodes[node]["dwellTimes"] = self.DG.nodes[
                            node]["dwellTimes"][-5:]

                destIsNext = False
                for successor in self.DG.succ[node]:
                    if self.DG.nodes[successor]["stationName"] == tram["dest"]:
                        destIsNext = True

                if not destIsNext:
                    self.DG.nodes[node]["tramsDeparted"].append(tram)

            averageDwell = self.getAverageDwell(node)
            for tram in tramsDeparted:
                tram["averageDwell"] = averageDwell

            # print("Trams departed {}: {}".format(node, tramsDeparted))

    def locateDeparting(self, node):
        # Locate departing trams
        tramsAtArr = self.DG.nodes[node]["tramsAt"] + self.DG.nodes[node][
            "tramsArriving"]
        tramsDeparted = []

        # Reverse to make sure newer trams matched first
        for tramHere in reversed(self.DG.nodes[node]["tramsHere"]):
            tramFound = False
            for tram in tramsAtArr:
                if ((tramHere["dest"] == tram["dest"])
                   and (tramHere["carriages"] == tram["carriages"])
                   and "matched" not in tram):
                    tramFound = True
                    tram["matched"] = True
                    break
            if not tramFound:
                tramsDeparted.append(tramHere)

        for tram in tramsAtArr:
            if "matched" in tram:
                del(tram["matched"])

        # Locate trams departing initial stop
        tramsExApproaching = []
        for pTram in self.DG.nodes[node]["prevTramsApproaching"]:
            tramFound = False
            for tram in self.DG.nodes[node]["tramsApproaching"]:
                # pTram found but with lower wait time
                if ((pTram["dest"] == tram["dest"])
                   and (pTram["carriages"] == tram["carriages"])
                   and (pTram["wait"] >= tram["wait"])):
                    tramFound = True
                    break

                # pTram probably dropped off because of order changing
                if (((pTram["dest"] != tram["dest"])
                   or (pTram["carriages"] != tram["carriages"]))
                   and (pTram["wait"] >= tram["wait"])):
                    tramFound = True
                    break

            if not tramFound:
                tramsExApproaching.append(pTram)

        for pTram in tramsExApproaching:
            tramFound = False
            for tram in tramsAtArr:
                if ((pTram["dest"] == tram["dest"])
                   and (pTram["carriages"] == tram["carriages"])
                   and "matched" not in tram):
                    tramFound = True
                    tram["matched"] = True
                    break

        self.calcTramDwell(tramsDeparted, node)

    def calcTramTransit(self, node, tram):
        for pNode in self.DG.pred[node]:
            foundPTram = None
            for i in range(len(self.DG.nodes[pNode]["tramsDeparted"])):
                pTram = self.DG.nodes[pNode]["tramsDeparted"][i]
                if ((pTram["dest"] == tram["dest"])
                   and (pTram["carriages"] == tram["carriages"])):
                    foundPTram = i

                    timeBetweenStops = tram["arriveTime"] - pTram["departTime"]
                    if timeBetweenStops != timedelta():
                        self.DG.edges[pNode, node]["transitTimes"].append(
                            timeBetweenStops)
                        self.DG.edges[pNode, node][
                            "transitTimes"] = self.DG.edges[pNode, node][
                                "transitTimes"][-5:]

                        (averageTransitTime,
                            isDirectAverage) = self.getAverageTransit(
                            pNode, node)

                        logging.info("Time between stops {} and {} {}".format(
                            pNode, node, timeBetweenStops))
                        logging.info(
                            "Average time between stops {} and {} {}".format(
                                pNode, node, averageTransitTime))
                    break

            if foundPTram is not None:
                # Delete found tram and any before it. Trams can't overtake so
                # we'll assume it doesn't actually exist here
                for i in range(foundPTram+1):
                    self.DG.nodes[pNode]["tramsDeparted"].pop(0)
                    if i != foundPTram:
                        logging.warning("Deleting overtaken tram from {} "
                                        "departed trams".format(pNode))
                break
        else:
            logging.warning("No matching departed tram for tram arrived at "
                            "{}".format(node))

    def locateHere(self, node):
        # Locate arriving trams & update "tramsHere" array and transit times
        tramsAtArr = self.DG.nodes[node]["tramsAt"] + self.DG.nodes[node][
            "tramsArriving"]
        newTramsHere = []

        for tram in tramsAtArr:
            tramFound = False
            for tramHere in self.DG.nodes[node]["tramsHere"]:
                if ((tramHere["dest"] == tram["dest"])
                   and (tramHere["carriages"] == tram["carriages"])
                   and ("matched" not in tramHere)):
                    tramFound = True
                    newTramsHere.append(tramHere)
                    tramHere["matched"] = True
                    break
            if not tramFound:
                if self.firstRun:
                    tram["arriveTime"] = None
                else:
                    tram["arriveTime"] = self.DG.nodes[node]["updateTime"]
                    self.calcTramTransit(node, tram)

                newTramsHere.append(tram)

        for tram in newTramsHere:
            if "matched" in tram:
                del(tram["matched"])

        self.DG.nodes[node]["tramsHere"] = newTramsHere

    def locateTrams(self):
        for node in nx.nodes(self.DG):
            self.decodePID(node)

        for node in nx.nodes(self.DG):
            self.locateDeparting(node)

        for node in nx.nodes(self.DG):
            self.locateHere(node)

        self.firstRun = False

    def getAverageDwell(self, platform):
        dwellTimes = self.DG.nodes[platform]["dwellTimes"]
        if len(dwellTimes) > 0:
            return sum(dwellTimes, timedelta())/len(dwellTimes)
        return None

    def getAverageTransit(self, start, end):

        def getTransit(_start, _end):
            transitTimes = self.DG.edges[_start, _end]["transitTimes"]
            if len(transitTimes) > 0:
                return sum(transitTimes, timedelta())/len(transitTimes)
            else:
                return None

        transitTime = getTransit(start, end)
        if transitTime is not None:
            return transitTime, True
        else:
            startStation = self.DG.nodes[start]["stationName"]
            endStation = self.DG.nodes[end]["stationName"]

            startNodes = []
            endNodes = []
            for node in nx.nodes(self.DG):
                if node in [start, end]:
                    continue
                if self.DG.nodes[node]["stationName"] == startStation:
                    startNodes.append(node)
                elif self.DG.nodes[node]["stationName"] == endStation:
                    endNodes.append(node)

            for startNode in startNodes:
                for endNode in endNodes + [end]:
                    if self.DG.has_edge(startNode, endNode):
                        transitTime = getTransit(startNode, endNode)
                        if transitTime is not None:
                            return transitTime, False

            for endNode in endNodes + [end]:
                for startNode in startNodes + [start]:
                    if self.DG.has_edge(endNode, startNode):
                        transitTime = getTransit(endNode, startNode)
                        if transitTime is not None:
                            return transitTime, False

        return None, False

    def predictTram(self, start, end, startDepartTime):
        predictions = {}
        # TODO: Use function to get weight accounting for terminating
        # stop/pass through
        path = nx.astar_path(self.DG, source=start, target=end)

        if len(path) < 2:
            return predictions, True

        if ((self.DG.nodes[start]["stationName"] != "Exchange Square")
           and (start != "St Peters Square_9400ZZMASTP2")
           and (self.DG.nodes[end]["stationName"] != "Exchange Square")
           and (end != "St Peters Square_9400ZZMASTP3")):
            for platform in path:
                if self.DG.nodes[platform]["stationName"] == "Exchange Square":
                    if ((self.DG.nodes[start][
                        "stationName"] == "Market Street")
                       or (self.DG.nodes[end][
                            "stationName"] == "Market Street")):
                        logging.error("When finding shortest path start was {}"
                                      ", end was {}, and path passed through "
                                      "Exchange Square".format(start, end))
                        return {}, False
                    destFound = False
                    endStaName = self.DG.nodes[end]["stationName"]
                    for tram in self.DG.nodes[platform]["pidTrams"]:
                        if tram["dest"] == endStaName:
                            destFound = True

                    if not destFound:
                        marketSt = self.getDestPlatform(start, "Market Street")
                        predicted, cont = self.predictTram(
                            start, marketSt, startDepartTime)
                        predictions.update(predicted)
                        if cont:
                            arriveMarketSt = max(predictions.values())

                            averageDwell = self.getAverageDwell(marketSt)
                            if averageDwell is None:
                                return predictions, False

                            leaveMarketSt = arriveMarketSt + averageDwell
                            predicted, cont = self.predictTram(
                                marketSt, end, leaveMarketSt)
                            predictions.update(predicted)
                        return predictions, cont

                    break

        workingTramTime = startDepartTime

        for platformNum in range(len(path) - 1):
            prevPlat = path[platformNum]
            curPlat = path[platformNum+1]

            (averageTransitTime, isDirectAverage) = self.getAverageTransit(
                prevPlat, curPlat)
            if averageTransitTime is None:
                return predictions, False

            workingTramTime = workingTramTime + averageTransitTime

            # If next stop's predicted arrival is < now, base later "
            # predictions off of now
            if ((platformNum == 0)
               and (workingTramTime < self.DG.nodes[curPlat]["updateTime"])):
                workingTramTime = self.DG.nodes[curPlat]["updateTime"]
            predictions[curPlat] = workingTramTime

            averageDwell = self.getAverageDwell(curPlat)
            if averageDwell is None:
                return predictions, False

            workingTramTime = workingTramTime + averageDwell
        return predictions, True

    def getDestPlatform(self, startPlatform, dest):
        closestPlatform = None
        distance = None
        destPlatforms = []

        for node in nx.nodes(self.DG):
            if self.DG.nodes[node]['stationName'] == dest:
                destPlatforms.append(node)

        for platformID in destPlatforms:
            try:
                # TODO: Use function to get weight accounting for terminating "
                # stop/pass through
                length = nx.astar_path_length(
                    self.DG, source=startPlatform, target=platformID)
                if ((distance is None) or length < distance):
                    closestPlatform = platformID
                    distance = length
            except nx.NetworkXNoPath:
                pass

        return closestPlatform

    def predictTramTimes(self):
        def getTramPredictions(startPlatform, departTime, tram):
            destPlatform = self.getDestPlatform(startPlatform, tram["dest"])
            predicted = None
            if tram["via"] is not None:
                viaPlatform = self.getDestPlatform(startPlatform, tram["via"])
                predicted, cont = self.predictTram(
                    startPlatform, viaPlatform, departTime)
                if cont:
                    averageDwell = self.getAverageDwell(viaPlatform)
                    if averageDwell is None:
                        averageDwell = timedelta()

                    departVia = predicted[viaPlatform] + averageDwell
                    predicted.update(self.predictTram(
                        viaPlatform, destPlatform, departVia)[0])
            else:
                try:
                    predicted = self.predictTram(
                        startPlatform, destPlatform, departTime)[0]
                except RecursionError:
                    logging.error("Max recursion {}, dest: {}".format(
                        startPlatform, destPlatform))
                    return None

            return predicted

        for node in nx.nodes(self.DG):
            averageDwell = self.getAverageDwell(node)
            if averageDwell is not None:
                for tram in self.DG.nodes[node]["tramsHere"]:
                    if tram["arriveTime"] is not None:
                        tram["predictions"] = getTramPredictions(
                            node, tram["arriveTime"] + averageDwell, tram)

            for tram in self.DG.nodes[node]["tramsDeparted"]:
                tram["predictions"] = getTramPredictions(
                    node, tram["departTime"], tram)

            for tram in self.DG.nodes[node]["tramsApproaching"]:
                tramStartsHere = True
                for pNode in self.DG.pred[node]:
                    for pTram in self.DG.nodes[pNode]["tramsDeparted"]:
                        if (
                           (tram["dest"] == pTram["dest"])
                           and (tram["carriages"] == pTram["carriages"])):
                            tramStartsHere = False
                if tramStartsHere:
                    departTime = (self.DG.nodes[node]["updateTime"] +
                                  timedelta(minutes=tram["wait"]))
                    tram["predictions"] = getTramPredictions(
                        node, departTime, tram)
                    tram["predictions"][node] = departTime

    def gatherTramPredictions(self):
        for node in nx.nodes(self.DG):
            for status in ["tramsHere", "tramsDeparted", "tramsApproaching"]:
                trams = self.DG.nodes[node][status]

                shortStatus = "here"
                if status == "tramsDeparted":
                    shortStatus = "departed"
                elif status == "tramsApproaching":
                    shortStatus = "dueStartsHere"

                for tram in trams:
                    if "predictions" not in tram:
                        continue
                    seenVia = False
                    for plat, time in sorted(
                       tram["predictions"].items(),
                       key=operator.itemgetter(1)):
                        if tram["via"] == self.DG.nodes[plat]["stationName"]:
                            seenVia = True
                        via = tram["via"]
                        if seenVia:
                            via = None
                        if tram["dest"] != self.DG.nodes[plat]["stationName"]:
                            self.DG.nodes[plat]["predictedArrivals"].append({
                                "dest": tram["dest"],
                                "via": via,
                                "carriages": tram["carriages"],
                                "curLoc": {
                                    "platform": node,
                                    "status": shortStatus,
                                    },
                                "predictedArriveTime": time,
                                "predictions": tram["predictions"]
                                })

    def clearOldDeparted(self):
        # Attempt at fixing ghost trams hanging around in departed lists
        for node in nx.nodes(self.DG):
            delTrams = []
            for i in range(len(self.DG.nodes[node]["tramsDeparted"])):
                tram = self.DG.nodes[node]["tramsDeparted"][i]
                maxTransit = timedelta(minutes=6)
                if ((tram["departTime"] + maxTransit)
                   < self.DG.nodes[node]["updateTime"]):
                    delTrams.append(i)

            offset = 0
            for delTram in delTrams:
                logging.warning(
                    "Deleting stale tram from {} departed trams".format(node))
                del(self.DG.nodes[node]["tramsDeparted"][delTram - offset])
                offset = offset + 1

    def clearNodePredictions(self):
        for node in nx.nodes(self.DG):
            self.DG.nodes[node]["predictedArrivals"].clear()

    def getPIDs(self):
        return nx.get_node_attributes(self.DG, "pidTrams")

    def getLastUpdateTime(self, nodeID):
        return self.DG.nodes[nodeID].get("updateTime", datetime.min)

    def getMessage(self, nodeID):
        return self.DG.nodes[nodeID].get("message")

    def getTramsAts(self):
        return nx.get_node_attributes(self.DG, "tramsAt")

    def getTramsArrivings(self):
        return nx.get_node_attributes(self.DG, "tramsArriving")

    def getTramsApproachings(self):
        return nx.get_node_attributes(self.DG, "tramsApproaching")

    def getTramsHeres(self):
        tramsHere = nx.get_node_attributes(self.DG, "tramsHere")
        for node in tramsHere:
            for tram in tramsHere[node]:
                if "wait" in tram:
                    del(tram["wait"])
        return tramsHere

    def getTramsDeparteds(self):
        return nx.get_node_attributes(self.DG, "tramsDeparted")

    def getNodePredictions(self):
        return nx.get_node_attributes(self.DG, "predictedArrivals")

    def getDwellTimes(self):
        return nx.get_node_attributes(self.DG, "dwellTimes")

    def getNodes(self):
        return nx.nodes(self.DG)

    def getStations(self):
        return self.stations

    def getStationPlatforms(self, statName):
        platIDs = []
        for node in nx.nodes(self.DG):
            if self.DG.nodes[node]["stationName"] == statName:
                platIDs.append(self.DG.nodes[node]["platformID"])
        return platIDs

    def getNodePreds(self, node):
        return self.DG.pred[node]

    def getTransit(self, inNode, outNode):
        return self.DG.edges[inNode, outNode]["transitTimes"]

    def getMapPos(self, node):
        return self.pos[node]

    def nodesNoAvDwell(self):
        nodes = []
        for node in nx.nodes(self.DG):
            if len(self.DG.nodes[node]["dwellTimes"]) == 0:
                nodes.append(node)
        return nodes

    def edgesNoAvTrans(self):
        edges = []
        for edge in self.DG.edges:
            if len(self.DG.edges[edge]["transitTimes"]) == 0:
                edges.append(edge)
        return edges


def main():
    graph = TramGraph()
    plt.subplot(121)
    nx.draw_networkx(
        graph.DG, pos=graph.pos, with_labels=True, node_size=20, font_size=6)

    plt.show()


if __name__ == "__main__":
    main()