#! /usr/bin/env python
"""
Store owntracks location updates in a database
"""
from datetime import datetime, timezone
import json
import logging
import paho.mqtt.client as mqtt
import psycopg2
import ssl
import sys
import time
import yaml


class Dumper():
    def __init__(self, config='./.owntrackstodb.yaml'):
        try:
            with open(config, 'r') as f:
                configs = yaml.load(f.read())

                dbhost = configs['database']['host']
                dbport = configs['database']['port']
                dbuser = configs['database']['username']
                dbpass = configs['database']['password']
                dbname = configs['database']['dbname']

                self._conn = psycopg2.connect(host=dbhost, port=dbport,
                                              user=dbuser, password=dbpass,
                                              dbname=dbname)

                # Handle mqtt messages from the channels we subscribe to
                def handle_message(client, userdata, message):
                    j = json.loads(str(message.payload, encoding="ascii"))
                    if(message.topic.startswith("owntracks")):
                        # If message format is 'owntracks/user/device'
                        # then we should try to parse out userid/deviceid
                        # and handle this message as a location update
                        if(j['_type'] == 'location'):
                            userid = message.topic.split('/')[1]
                            device = message.topic.split('/')[2]
                            logging.info("{0} {1} posted an update: {2}"
                                          .format(userid, device, j))
                            self.handle_location_update(userid, device, j)

                self._client = mqtt.Client(client_id="")
                try:
                    self._client.tls_set(ca_certs=configs['mqtt']['ca'],
                                         cert_reqs=ssl.CERT_REQUIRED,
                                         tls_version=ssl.PROTOCOL_TLSv1)
                except IOError as e:
                    logging.error("Something went wrong setting up mqtt. {0}"
                                  .format(e))
                self._client.username_pw_set(configs['mqtt']['username'],
                                             configs['mqtt']['password'])
                self._client.will_set("/lwt/o2db",
                                      payload="o2db script offline")
                mqtt_host = configs['mqtt']['host']
                mqtt_port = configs['mqtt']['port']
                self._client.on_message = handle_message
                logging.warn("Connecting to mqtt broker...")
                self._client.connect(mqtt_host, mqtt_port)
        except IOError as e:
            logging.error("Unable to load configuration. {0}".format(e))
            sys.exit(1)

    def handle_location_update(self, user, device, rawdata):
        acc = rawdata.get('acc')  # accuracy in meters
        alt = rawdata.get('alt')  # altitude above sea level
        batt = rawdata.get('batt')  # battery percentage
        cog = rawdata.get('cog')  # course over ground
        lat = rawdata['lat']  # latitude
        lon = rawdata['lon']  # longitude
        rad = rawdata.get('rad')  # radius around region
        t = rawdata.get('t')  # p, c, b, r, u, t; see booklet
        tid = rawdata.get('tid')  # tracker ID
        tst = datetime.fromtimestamp(rawdata['tst'], timezone.utc)  # Timestamp
        vac = rawdata.get('vac')  # vertical accuracy
        vel = rawdata.get('vel')  # velocity, kmh
        pressure = rawdata.get('p')  # barometric pressure in kPa (float)
        connection_status = rawdata.get('conn')  # connection status: w, o, m

        # execute prepared statement
        cur = self._conn.cursor()
        cur.execute(
            """insert into locationupdates (acc, alt, batt, cog, lat, lon,
            radius, t, tid, tst, vac, vel, p, conn, rawdata, userid, device)
            values (%(acc)s, %(alt)s, %(batt)s, %(cog)s, %(lat)s, %(lon)s,
            %(rad)s, %(t)s, %(tid)s, %(tst)s, %(vac)s, %(vel)s, %(p)s,
            %(conn)s, %(rawdata)s, %(userid)s, %(device)s);""",
            {'acc': acc, 'alt': alt, 'batt': batt, 'cog': cog, 'lat': lat,
             'lon': lon, 'rad': rad, 't': t, 'tid': tid, 'tst': tst,
             'vac': vac, 'vel': vel, 'p': pressure, 'conn': connection_status,
             'rawdata': json.dumps(rawdata), 'userid': user, 'device': device})
        self._conn.commit()

    def run(self):
        self._client.subscribe([("owntracks/#", 0)])
        logging.warn("subscribed to 'owntracks/#'")
        self._client.loop_forever()
        try:
            while True:
                time.sleep(2)
        except (KeyboardInterrupt, SystemExit):
            self._client.disconnect()

if __name__ == '__main__':
    dumper = Dumper()
    dumper.run()
