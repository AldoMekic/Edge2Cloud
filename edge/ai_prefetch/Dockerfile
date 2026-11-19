
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY train_model.py .
COPY app.py .

# Train the initial synthetic-data model inside
# the image during the Docker build.
RUN python train_model.py

EXPOSE 8000

CMD ["python", "-u", "app.py"]
