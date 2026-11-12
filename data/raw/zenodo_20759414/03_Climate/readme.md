# Climate

## Device specifications

- HTU21D
  - Supplier: TE Connectivity
  - Storage temperature: -40 to 125 ºC
  - Humidity operating range: 0 to 100%
- SQ-520
  - Supplier: Apogee Instruments, Inc.
  - Serial number: 4951
  - Resolution: 0.1 µmol * m-2 * s-1
  - Measurement range: 0 to 4000 µmol * m-2 * s-1
  - Field of view: 180º

## Directory description

Climate/
├── inside.csv                           # temperature and humidity measurements from the weather stations inside the greenhouse
│   | date | timestamp | temperature (ºC) | humidity (%) | # inside_1.csv file headers
├── outside.csv                           # temperature and humidity measurements from the outside weather station
│   | date | timestamp | temperature (ºC) | humidity (%) | # outside.csv file headers
├── PAR.csv                           # PAR measurements from the inside SQ-520 sensor
│   | date | timestamp | PAR (micromoles * m-2 * s-1) | # PAR.csv file headers
└── readme.md                      # directory description file