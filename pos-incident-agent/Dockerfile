FROM docker.io/library/python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOME=/tmp
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt && python -m pip check
COPY pos_incident_agent.py guardrails.py web_app.py chat.html demo_questions.md settings.json alerts.json system_inventory.csv ./
USER 10001:10001
EXPOSE 8080
CMD ["python", "web_app.py"]
