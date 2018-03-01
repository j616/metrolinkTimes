#!/usr/bin/env python3

import json
from metrolinkTimes.tfgmMetrolinksAPI import TFGMMetrolinksAPI
from pick import pick


def genStations(api):
    data = api.getData()

    outData = {}

    stationNum = 0

    for s in data:
        stationNum = stationNum + 1
        if s not in outData:
            outData[s] = {}

        for ac in data[s]:
            if ac not in outData[s]:
                sBefore = []
                selecting = True

                while(selecting):
                    pickStations = sorted(data.keys())
                    pickStations.append("None")
                    inS, index = pick(
                        pickStations,
                        "({}/{}) Select station before {} {} {}".format(
                            stationNum,
                            len(data),
                            s,
                            data[s][ac][0]["Direction"],
                            ac
                            )
                        )

                    if inS == "None":
                        selecting = None
                        break

                    platforms = []

                    for inP in data[inS]:
                        platforms.append("{} {}".format(
                            data[inS][inP][0]["Direction"],
                            inP))

                    if len(platforms) == 1:
                        sBefore.append(inP)
                    elif len(platforms) > 1:
                        selectedInP, index = pick(
                            platforms,
                            "Select platform at {} as in for {} {}".format(
                                inS,
                                s,
                                data[s][ac][0]["Direction"]
                                ))

                        sBefore.append(selectedInP.split(" ")[1])

                    resp, index = pick(
                        ["yes", "no"],
                        "Add another input?"
                        )

                    selecting = (resp == "yes")

                outData[s][ac] = {
                    "line": data[s][ac][0]["Line"],
                    "direction": data[s][ac][0]["Direction"],
                    "tla": data[s][ac][0]["TLAREF"],
                    "stationsBefore": list(set(sBefore)),
                    "map": {
                        "x": -6,
                        "y": -6
                    }
                }

    with open('./stations.json.tmp', 'w') as outfile:
        json.dump(outData, outfile, indent=1)


def main():
    api = TFGMMetrolinksAPI()
    genStations(api)


if __name__ == "__main__":
    main()
