# hadolint ignore=DL3006
FROM base_context

RUN --mount=type=bind,src=requirements.txt,dst=/tmp/requirements.txt \
  pip install --no-cache-dir -r /tmp/requirements.txt

COPY devcontainer-cache-build-initialize.py /devcontainer-cache-build-initialize.py
ENTRYPOINT [ "python", "/devcontainer-cache-build-initialize.py" ]
