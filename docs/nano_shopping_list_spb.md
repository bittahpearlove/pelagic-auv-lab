# Nano AUV shopping list — Saint Petersburg

Checked 19 October 2026. Controller: existing classic 5 V ATmega328P Nano.
Goal: three-thruster shallow-pool temperature profiler.

This is an electrical interface selection, not a claim that a complete vehicle
has been assembled and tested. Real drivers must be added to the uploaded starter
firmware. No orders or supplier messages have been sent.

## Electronics: exact purchase references

| Qty | Part | Supplier/product link | Nano connection / procurement status |
| --- | --- | --- | --- |
| 1 | Sealed DS18B20, AMP-X145 | [Amperka](https://amperka.ru/product/sealed-temperature-sensor-ds18b20) | D4, externally powered at 5 V, 4.7 kΩ pull-up; local first-temperature-driver option, not the final fast scientific probe |
| 1 | Troyka SD module | [Amperka](https://amperka.ru/product/troyka-sd) | SPI D10–D13, power/logic compatible with a 5 V host; includes voltage regulation and signal translation |
| 1 | 8–32 GB microSDHC card, FAT32 | Same electronics retailer or established local computer retailer | Avoid exFAT for the initial Arduino SD integration |
| 1 | Four-channel bidirectional 5 V/3.3 V logic converter | [duino.ru](https://duino.ru/preobrazovatel-logicheskikh-urovney/) | Two channels for I2C SDA/SCL; requires both voltage reference rails |
| 1 | Adafruit BNO055 breakout #2472 | [Adafruit exact model](https://www.adafruit.com/product/2472) | I2C A4/A5, onboard 5 V interface support, fusion offloaded from Nano; delivery to Russia NOT verified |
| 1 | Bar02 pressure/depth sensor, MS5837-02BA bulkhead assembly | [Blue Robotics](https://bluerobotics.com/store/sensors-cameras/sensors/bar-depth-pressure-sensor/) | A4/A5 THROUGH level converter; shallow-pool choice; delivery to Russia NOT verified |
| 1 | Celsius fast-response probe | [Blue Robotics](https://bluerobotics.com/store/sensors-cameras/sensors/celsius-sensor-r1/) | I2C THROUGH level converter; scientific temperature candidate; confirm shipped TSYS01/TMP119 revision and sealed mounting; delivery NOT verified |
| 1 | SOS Leak Sensor with probes | [Blue Robotics](https://bluerobotics.com/store/sensors-cameras/leak-sensor/sos-leak-sensor/) | 5 V, signal to D2; high means wet, so logic polarity matches base; test disconnected/power-loss behavior and interface before relying on it; delivery NOT verified |
| 1 | ACS72981LLRATR-100B5 LARGE carrier, Pololu #5274 | [Pololu](https://www.pololu.com/product/5274) | 5 V supply, analog output to A1; ±100 A measuring range, current-path wiring/thermal rating must be checked; delivery NOT verified |
| 1 | XL4015 adjustable buck module | [duino.ru](https://duino.ru/dc-dc-step-down-5a-xl4015/) | Battery to regulated 5 V electronics rail; set and measure 5.0 V before connection; validate actual load and cooling, do not assume 5 A continuous in sealed housing |
| 1 | Dedicated regulated 3.3 V breakout | [Amperka Troyka LDO documentation](https://wiki.amperka.ru/продукты:troyka-ldo) | Feed from 5 V; use 3.3 V configuration for sensor rail/level-shifter reference; ask Amperka for the current matching module |
| 1 set | 1% resistors: 33 kΩ, 10 kΩ; 100 nF ADC filter capacitor | Amperka / Amperkot / Chip Dip | Battery divider to A0; at 16.8 V gives approximately 3.91 V; verify ADC limits/reference and calibrate before use |
| 2 | Maintained SPST switches | Amperka / Amperkot / Chip Dip | D7 arm permit and dry-loop bench test; these are logic switches, not motor-power isolation |
| 1 set | Breadboard, jumper leads, headers, 4.7 kΩ resistors | [Amperka](https://amperka.ru/) / [Amperkot](https://amperkot.ru/) | Bench logic wiring only |

A local BNO055 lead exists at [Amperkot, GY-955](https://amperkot.ru/products/modul_opredeleniya_prostranstvennogo_polozheniya__giroskop_gy955_ahrs_bno055/25207738.html),
but the listing requests a stock/price enquiry. It is NOT the same verified
breakout as Adafruit #2472. Confirm its protocol, schematic and signal voltage
before substituting it; some AHRS modules expose a processed UART interface.
Buy a breakout board, not the loose BNO055 LGA chip.

Likewise, this [Russian MS5837-02BA listing](https://bmtop.ru/product/elektrotekhnicheskie_tovary/avtomatizatsiya_i_upravlenie/datchiki/ms5837_02ba_i2c_vysokotochnyy_datchik_davleniya_tsifrovoy_barometr/)
is only a procurement lead. The available listing does not establish a sealed
bulkhead package, so do not treat it as a drop-in underwater Bar02 replacement.

## Propulsion and power reference set

Choose ONE matched propulsion route. Do not mix an unspecified motor and ESC.

**Documented electrical reference:**
- 3 × [Blue Robotics T200](https://bluerobotics.com/store/thrusters/t100-t200-thrusters/t200-thruster-r2-rp/).
- 3 × matching Basic ESC, available as a T200 option; official
  [ESC specifications](https://bluerobotics.com/learn/technical-reference/).
  Nano D3/D5/D6 provide servo pulses; Basic ESC accepts 3.3–5 V signal logic,
  with 1500 µs neutral and 1100–1900 µs range. Separate 5 V regulation is required.
- Appropriate mounting brackets, guards and matching cable penetrators.
- Manufacturer store links above are specifications/order references; shipment
  to Saint Petersburg has NOT been verified. Request an institutional quotation
  that explicitly confirms delivery, payment, lead time and exact revision.

**Domestic quotation lead:** [Smelcom Robotics thrusters](https://smelcom.ru/equipment/thrusters).
Request 3 × СКР-2001 compact 2.7 kgf thrusters (listed as 12–24 V, 150 W), plus
3 × supplier-matched reversible ESCs. Specify classic Nano 5 V servo-PWM control,
1500 µs neutral, both directions, signal-loss stop and the required frame/power
limits. Electrical compatibility is CONDITIONAL on the supplier's ESC datasheet;
no verified PWM specification was found for this route. Ask for a matched quote,
not permission to assume the existing firmware will drive them unchanged.

Power components:
- 1 × 4S 14.8 V LiPo, initially around 5000 mAh, with XT90 connector: a listed
  [B&C 5000 mAh 4S 90C XT90 option at RC-Russia](https://www.rc-russia.ru/catalog/akkumulyatory-li-pol/4s).
  Capacity is a starting candidate, not a runtime guarantee; check mass, size,
  continuous current and connector rating against the selected propulsion route.
- 1 × genuine balance charger supporting 4S LiPo, with AC supply and the correct
  XT90 charging lead plus balance connection. Ask the battery supplier to quote
  charger and pack together; a specific stocked charger was not verified.
- 1 × accessible motor-power isolator, 1 × main fuse/holder, branch protection,
  suitable power distribution and correctly rated cable/connectors. Ratings are
  selected from cable limits and actual motor load, not from Nano compatibility.
- Spare power connector pairs, solder terminals, strain relief, protective covers.
- Separate USB/external-power arrangement to avoid backfeeding the computer when
  supplying the Nano 5 V pin. Confirm the particular clone's power circuit first.

A T200 can draw 24 A at 16 V, so three can approach 72 A before the logic supply.
Full-charge 4S voltage is 16.8 V; size using the motor curves at that voltage.
Battery C-rating marketing alone does not validate wiring, connectors or cooling.
The current Nano firmware's 10 A and 10.5 V thresholds must be replaced for this
reference system before enabling propulsion. Do not change them blindly.

## Housing, frame and test equipment

| Qty | Requirement | Source / selection condition |
| --- | --- | --- |
| 1 complete | Watertight tube enclosure, end caps, flanges and O-rings | [Blue Robotics enclosure configurator](https://bluerobotics.com/store/watertight-enclosures/wte-vp/), or a university-machined pressure-reviewed design; import delivery unverified |
| As required | Cable penetrators and plugs | Match enclosure holes AND measured cable diameters; include every motor/sensor cable in the port plan |
| 1 set | Vacuum/leak-test fittings and pump | Match enclosure manufacturer's test arrangement; borrow from faculty if possible |
| 1 | Frame and electronics tray | Faculty workshop: HDPE/acetal or reviewed corrosion-compatible metal structure |
| 3 | Thruster mounts | Match the chosen thruster; verify thrust line and propeller clearance |
| 1 set | Suitable buoyancy, adjustable ballast | Size from total wet mass/displacement; target slight positive buoyancy |
| 1 | Temperature-probe mount and sealed probe arrangement | Bulkhead probes need a sealed backside; an exposed extension lead is insufficient |
| 1 set | Fasteners, clamps, cable ties, O-ring spares and approved lubricant | Workshop / electronics/mechanical supplier |
| 1 | Retrieval attachment and supervised recovery line where permitted | Faculty pool arrangement; manage snag risk |
| 1 each | Multimeter, soldering tools, heat-shrink and wire tools | [Amperkot](https://amperkot.ru/) / [Chip Dip](https://www.chipdip.ru/) |
| Borrow | Calibrated reference thermometer and test column | Faculty measurement lab; independent reference for calibration and experiments |

Housing diameter/length, end-cap drilling, fuse size and wire gauge are intentionally
not assigned arbitrary values. They require the component layout and load budget.

## Procurement instructions for the faculty

Local electronics can be ordered from the linked Russian listings subject to the
seller confirming current stock and invoice terms. Imported items are quote lines,
not confirmed deliverable purchases. Ask suppliers for an invoice to the university,
exact manufacturer part numbers, datasheets, mating connectors, delivery to Saint
Petersburg and lead times. No unverified substitute should be purchased merely
because its title mentions Arduino.

Reference bus plan: Nano A4/A5 on 5 V side; pressure and scientific temperature
on translated 3.3 V side; Adafruit #2472 on 5 V side. Expected addresses for the
currently described sensor versions: Bar02 0x76, TSYS01 Celsius 0x77, BNO055 0x28.
Confirm new Celsius revision/address and all pull-ups before wiring. Keep I2C
runs short and validate bus timing. MicroSD uses D10–D13, so remove status LED
writes to D13 in firmware when SD is added. IMU must be mounted away from motors
and high-current wiring and calibrated with the completed vehicle.
