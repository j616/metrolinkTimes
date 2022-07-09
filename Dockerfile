FROM python:3.7 as base

RUN mkdir pkg

COPY pyproject.toml license README.md ./
COPY metrolinkTimes/*.py metrolinkTimes/
COPY metrolinkTimes/data/stations.json metrolinkTimes/data/

RUN --mount=type=cache,target=/root/.cache/pip --mount=source=.git,target=.git,type=bind pip wheel --wheel-dir=/wheeley .

FROM python:3.7-slim
EXPOSE 5000
WORKDIR /app

COPY --from=base /wheeley /wheeley

RUN --mount=type=cache,target=/root/.cache/pip pip3 install --find-links=/wheeley metrolinkTimes

ENTRYPOINT ["python3", "-m", "metrolinkTimes"]