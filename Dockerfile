FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY clinical_trial_matcher/ ./clinical_trial_matcher/

COPY model.joblib .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "clinical_trial_matcher.main:app", "--host", "0.0.0.0", "--port", "8000"]

