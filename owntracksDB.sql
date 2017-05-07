-- create table for location updates
create table locationupdates(
  acc integer,
  alt integer,
  batt integer,
  cog integer,
  lat float,
  lon float,
  radius integer,
  t char(1),
  tid varchar(16),
  tst timestamp,
  vac integer,
  vel integer,
  p integer,
  conn char(1),
  rawdata json,
  userid varchar(64),
  device varchar(64)
)
