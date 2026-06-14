# syntax=docker/dockerfile:1
FROM python:3.11-slim-buster

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
RUN pip3 install gunicorn
COPY . .

EXPOSE 8081

CMD ["gunicorn"  , "-b", "0.0.0.0:8081", "app:app"]
