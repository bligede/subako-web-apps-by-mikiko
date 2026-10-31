FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/apps/api
WORKDIR /app/apps/api
COPY apps/api/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock && useradd --create-home --uid 10001 subako
COPY apps/api/ /app/apps/api/
COPY tools/container.py /app/tools/container.py
# Entry point reads root-only secret mounts then drops to uid/gid 10001.
EXPOSE 8000
CMD ["python", "/app/tools/container.py", "serve"]
