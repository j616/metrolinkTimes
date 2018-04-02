#!/usr/bin/env python3

import http.client
import json
import logging
from time import sleep


class TFGMMetrolinksAPI:
    def __init__(self):
        with open("/etc/metrolinkTimes/metrolinkTimes.conf") as conf_file:
            self.conf = json.load(conf_file)

    def getData(self):
        try:
            headers = {
                # Request headers
                "Ocp-Apim-Subscription-Key": self.conf[
                    "Ocp-Apim-Subscription-Key"],
            }
            conn = http.client.HTTPSConnection('api.tfgm.com')
            conn.request("GET", "/odata/Metrolinks", "{body}", headers)
            response = conn.getresponse()
            data = json.loads(response.read().decode("utf-8"))
            conn.close()

            retData = {}
            for platform in data["value"]:
                sl = platform["StationLocation"]
                if sl not in retData:
                    retData[sl] = {}

                ac = platform["AtcoCode"]
                if platform["AtcoCode"] not in retData[sl]:
                    retData[sl][ac] = []

                retData[sl][ac].append(platform)

            return retData

        except Exception as e:
            logging.error("{}".format(e))
            return None


def dataTest(api):
    data = api.getData()

    with open('/tmp/metrolink.json', 'w') as outfile:
        json.dump(data, outfile)

    stations = data.keys()
    print(len(stations))

    # directions = set([s["Direction"] for s in data["value"]])
    # print(directions)

    # updated = set([s["LastUpdated"] for s in data["value"]])
    # print(updated)

    # stat0 = set([s["Status0"] for s in data["value"]])
    # print(stat0)


def printEvents(api):
    data = api.getData()

    print("================")

    for station in data:
        for platform in data[station]:
            pid = data[station][platform][0]
            for tram in [0, 1, 2, 3]:
                if pid["Status{}".format(tram)] not in ["Due", ""]:
                    print("{} to {} {} {}".format(
                        pid["Carriages{}".format(tram)],
                        pid["Dest{}".format(tram)],
                        pid["Status{}".format(tram)],
                        station,
                        ))


def main():
    api = TFGMMetrolinksAPI()
    while True:
        printEvents(api)
        sleep(10)
    # dataTest(api)


if __name__ == "__main__":
    main()
