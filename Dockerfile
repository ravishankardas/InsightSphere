FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# install OS libs needed by OpenCV (libGL) + cleanup
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      libgl1 \
      libglib2.0-0 \
      libsm6 \
      libxrender1 \
      libxext6 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml poetry.lock* /app/
# or requirements.txt, etc.
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . /app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
