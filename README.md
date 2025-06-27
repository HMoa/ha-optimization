# ha-optimization

A small poc to optimize energy usage using batteries for the swedish market conditions

This takes some inspiration from:

- <https://medium.com/@yeap0022/basic-build-optimization-model-to-schedule-batterys-operation-in-power-grid-systems-51a8c04b3a0e>
- <https://github.com/davidusb-geek/emhass>

## Todo

- [x] Cloud coverage in model (failed, it sucked)
- [x] Make prediction model
- [x] Create better mocks for production / consumption
- [ ] Improve consumption model (prev values? other features?)
- [ ] Test API for production forecast
  -- <https://openweathermap.org/api/solar-panels-and-energy-prediction>
- [ ] Compare with cloud coverage
- [ ] Split up tasks: fetch data, generate models, generate schedule

## Operational stuff

- [ ] Node-red: Create code to set the battery mode
- [ ] Node-red: Fetch current schedule item mode
- [ ] Test with a running home assistant - docker on machine?
- [ ] Test run on a Rpi (check speed of solver)
