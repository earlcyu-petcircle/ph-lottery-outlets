[out:json][timeout:240];
area["ISO3166-1"="PH"][admin_level=2]->.ph;
(
  nwr["shop"="lottery"](area.ph);
  nwr["lottery"](area.ph);
  nwr["shop"="bookmaker"](area.ph);
  nwr["name"~"lotto|PCSO|Lottery",i]["shop"](area.ph);
);
out center tags;
