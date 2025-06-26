# ha-optimization

A small poc to optimize energy usage using batteries for the swedish market conditions

This takes some inspiration from:

- <https://medium.com/@yeap0022/basic-build-optimization-model-to-schedule-batterys-operation-in-power-grid-systems-51a8c04b3a0e>
- <https://github.com/davidusb-geek/emhass>

## Todo

- [x] Get sample data for production
  -- production per 5min?
  -- Cloud coverage
  -- Make prediction model
- [ ] Test API for production forecast
  -- <https://openweathermap.org/api/solar-panels-and-energy-prediction>
  -- Compare with cloud coverage

- [ ] Create better mocks for production / consumption
- [ ] Create code to set the battery mode
- [ ] Test with a running home assistant - docker
- [ ] Test run on a Rpi
