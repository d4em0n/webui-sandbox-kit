FROM node@sha256:e9f565d32859f0cbfb52125eafe8be39390f24dac302dc3cdf566e8ba3ab21ee AS frontier
WORKDIR /build
COPY frontier/frontier_ui.py /frontier_ui.py
COPY frontier/mcp-apps/package*.json ./
RUN npm ci --ignore-scripts
COPY frontier/mcp-apps/ ./
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/* \
    && python3 build.py && node build.mjs

FROM node@sha256:e9f565d32859f0cbfb52125eafe8be39390f24dac302dc3cdf566e8ba3ab21ee AS document-preview
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY versions.lock.json ./
COPY scripts/fetch_assets.py scripts/build_document_preview.py scripts/
COPY document-preview/ document-preview/
RUN python3 scripts/build_document_preview.py

FROM ubuntu@sha256:2198e4c65076e9cb0b3d695219df667c0e3b0072da64ca3c2648aca17dcecaf5 AS assets
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY versions.lock.json ./
COPY scripts/fetch_assets.py scripts/fetch_assets.py
RUN python3 scripts/fetch_assets.py /assets

FROM ubuntu@sha256:2198e4c65076e9cb0b3d695219df667c0e3b0072da64ca3c2648aca17dcecaf5
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates libgcc-s1 \
    && rm -rf /var/lib/apt/lists/* && python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:/opt/microsandbox/bin:/opt/craft/bin:$PATH \
    MSB_HOME=/data/runtime LD_LIBRARY_PATH=/opt/microsandbox/lib \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 KIT_DATA=/data
WORKDIR /opt/kit
COPY controller/requirements.lock /opt/kit/controller/requirements.lock
RUN pip install --no-cache-dir -r controller/requirements.lock
COPY --from=assets /assets/ /opt/
COPY . /opt/kit/
COPY --from=frontier /build/dist/frontier.html /opt/kit/frontier/mcp-apps/dist/frontier.html
COPY --from=document-preview /build/document-preview/dist /opt/kit/document-preview/dist
RUN find /opt/kit -type d -exec chmod 755 {} + && find /opt/kit -type f -exec chmod a+r {} +
USER 1000:1000
EXPOSE 3000
ENTRYPOINT ["python", "-m", "controller.main"]
