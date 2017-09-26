# owntracks-to-database

## Contents

1. Motivations
2. License
3. Prerequisites
4. How to use

## 1. Motivations
Due to Owntracks recommending that users use their [http://owntracks.org/booklet/guide/clients/#recorder](Recorder) instead of [http://owntracks.org/booklet/guide/clients/#o2s](o2s), and disliking the limitations of the Recorder vs some existing infrastructure available via a relational database, this tool was created.

## 2. License
The python3 flavor unfortunately relies on both LGPL-licensed psycopg2 and EPL-licensed paho-mqtt.

The ruby flavor relies on the 2-clause BSD-licensed 'pg' gem and the MIT-licensed 'ruby-mqtt' gem; According to https://softwareengineering.stackexchange.com/questions/121998/mit-vs-bsd-vs-dual-license this means the ruby flavor is likely to be the same license as Ruby in general.

## 3. Prerequisites

### General
Run the sql in owntracksDB.sql to generate the necessary schema and configure your usernames and passwords in a yaml configuration file that is specified via the `--config` flag. Example configuration:
```
mqtt:
  host: localhost
  port: 1883
  ssl: :TLSv1
  ca: /path/to/mqtt/ca.crt
  ca\_cert: /path/to/mqtt/ca.crt
  username: mqttusername
  password: mqttpassword
database:
  host: localhost
  port: 5432
  username: postgres
  password: postgres
  dbname: locationupdates
```

Alternatively, the script can be configured via environment variables. Specifying these will override any values found in a configuration file. These are the environment variables required:
 * OWNTRACKS2DB\_MQTT\_HOST   
 * OWNTRACKS2DB\_MQTT\_PORT  
 * OWNTRACKS2DB\_MQTT\_SSL  
 * OWNTRACKS2DB\_MQTT\_CA  
 * OWNTRACKS2DB\_MQTT\_USERNAME  
 * OWNTRACKS2DB\_MQTT\_PASSWORD  
 * OWNTRACKS2DB\_DB\_HOST  
 * OWNTRACKS2DB\_DB\_PORT  
 * OWNTRACKS2DB\_DB\_USERNAME  
 * OWNTRACKS2DB\_DB\_PASSWORD  
 * OWNTRACKS2DB\_DB\_NAME  


### ruby
owntracks\_to\_db.rb runs under ruby 1.9.3 and up, with caveats in 1.9.3 as the pg gem is unable to serialize the json into the database so the 'rawdata' column will be empty. This shouldn't be an issue since that column can be generated from the other columns. These gems must be installed
 * logger
 * mqtt
 * pg

### python
owntracks\_to\_db.py runs under python3 (tested with python 3.4). The following packages are required:
 * paho-mqtt
 * psycopg2
 * pyyaml

The recommended way to install the python prerequisites is to `pip install -r requirements.txt` into a fresh virtualenv

## 4. How to use
`nohup ruby owntracks\_to\_db.rb &` will launch the ruby script in the background cleanly. The ruby version handles its own log rotation.

`nohup python owntracks\_to\_db.py &` will launch the python script in the background cleanly. The python version does *not* handle its own log rotation.
