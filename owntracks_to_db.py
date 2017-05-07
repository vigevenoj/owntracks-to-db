#! /usr/bin/env python
"""
Store owntracks location updates in a database
"""
import json
import paho.mqtt.client as mqtt
import ssl
import sys
import yaml


class Dumper():
    def __init__(self, config='./.owntrackstodb.yaml'):
        try:
            with open(config, 'r') as f:
                configs = yaml.load(f.read())
                self._client = mqtt.Client(client_id="")
                try:
                    self._client.tls_set(ca_certs=configs['mqtt']['ca'],
                                         cert_reqs=ssl.CERT_REQUIRED,
                                         tls_version=ssl.PROTOCOL_TLSv1)
                except IOError as e:
                    print("Something went wrong while setting up mqtt. {0}"
                          .format(e))
                self._client.username_pw_set(configs['mqtt']['username'],
                                             configs['mqtt']['password'])
                self._client.will_set("/lwt/o2db",
                                      payload="o2db script offline")
        except IOError as e:
            print("Unable to load configuration. {0}".format(e))
            sys.exit(1)

    def run(self):
        pass

if __name__ == '__main__':
    dumper = Dumper()
    dumper.run()
