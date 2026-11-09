FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --gid 10001 pipeline && useradd --uid 10001 --gid 10001 --no-create-home pipeline
COPY automation /app/automation
COPY keywords/politics.json /app/keywords/politics.json
COPY extension/keywords.json /app/extension/keywords.json
USER 10001:10001
ENTRYPOINT ["python", "-m", "automation.pipeline", "--data", "/data"]
CMD ["collect", "--limit", "12"]
