FROM python:3.10

WORKDIR /app

COPY requirements.txt /app/

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . /app/

EXPOSE 8000

CMD ["gunicorn", "finsmart.wsgi:application", "--bind", "0.0.0.0:8000"]