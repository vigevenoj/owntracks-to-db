FROM python:3

WORKDIR /owntracks2db

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ./owntracks_to_db.py ./
COPY ./config.yaml ./config/config.yaml

# Prometheus metrics
EXPOSE 8000

# A CA certificate is required 
VOLUME /owntracks2db/config
VOLUME /owntracks2db/certificates

# Run the script
# The config file isn't necessary
CMD [ "python", "./owntracks_to_db.py" ]

