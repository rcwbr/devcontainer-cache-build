FROM base_context

# TODO remove custom python-on-whales install
ADD https://github.com/rcwbr/python-on-whales.git#0.1.5 /tmp/python-on-whales
RUN pip install /tmp/python-on-whales

RUN --mount=type=bind,src=requirements.txt,dst=/tmp/requirements.txt \
  pip install -r /tmp/requirements.txt

COPY devcontainer-cache-build-initialize.py /devcontainer-cache-build-initialize.py
ENTRYPOINT [ "python", "/devcontainer-cache-build-initialize.py" ]
