# BoreWise Turns Every Pump Cycle Into an Aquifer Test

BoreWise can be built, and the physics favours it, but only if the team changes several parts of its earlier plan. A ₹2–2.5k ESP32 + MEMS-mic + class-D-amp device can time an echo down a 25–32 mm sounding tube to 100–150 m. To do that it must transmit a **low-frequency chirp (core band ~60–250 Hz, at most ~500 Hz)**, not a kHz chirp. It must correct for temperature (about 0.17 %/°C) and for **tube-diameter dispersion (−0.3 to −0.8 %)**, and it must measure only with the pump off. Deep Deccan-basalt borewells in Pune tap a fractured Aquifer-II at 48–175 m that sustains pumping for only **0.5–3 hours** ([CGWB NAQUIM Pune](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf)). That short sustain time is BoreWise's opening: every routine on/off cycle is a drawdown-and-recovery test that yields transmissivity, specific-capacity drift and a dry-up forecast. The commercial need is documented. Pune's private tanker prices roughly doubled to about ₹2,000 a load in summer 2026, and single societies spent ₹7.5–8 lakh in a season or a month ([The Bridge Chronicle](https://www.thebridgechronicle.com/pune/pune-water-crisis-tanker-costs-housing-society-maintenance-bills-rise-agn97); [NeeRain/TOI](https://neerain.com/taps-and-borewell-dry-up-its-the-return-of-water-tanker-raj/)). None of the competitors found combines cheap continuous level sensing, a dry-up forecast and pump protection. On AWS, a serverless stack of IoT Core, Lambda, DynamoDB, S3/Athena, SNS and a Strands agent fits inside the free tier and the $100–200 new-account credits. The plan needs rework in a few places: Timestream for LiveAnalytics is closed to new customers, LocalStack Community has been retired, SMS to India needs DLT registration, public well data is only quarterly, and GRACE-FO is too coarse for anything but regional context. This report gives the corrected design, a master parameter table to build the simulator from, a failure-mode catalogue, reconciled statistics, and a ranked roadmap.

**How to read this report.** Statements with an inline citation are sourced facts. Values marked **(computed)** were derived from cited formulas by the research team. Statements marked **(inference)** or **(assumption)** are engineering judgement and should be validated or presented as design choices, not facts.

## Ten corrections to the earlier plan, before any code is written

The research turned up several assumptions in the team's earlier plan that are physically or commercially wrong. The table lists them with the fix and the evidence, ordered roughly by how much they would hurt the demo if left uncorrected.

| # | Earlier assumption | Correction | Evidence |
|---|---|---|---|
| 1 | kHz-range chirp for echo ranging | Use **~60–250 Hz core band** (extend to 500 Hz only for shallow wells < ~50 m). In a 25 mm tube, smooth-wall loss is ~0.20 dB/m at 100 Hz vs ~0.65 dB/m at 1 kHz, so a 150 m round trip costs ~61 dB vs ~193 dB **(computed)**. In 150 mm casing, non-planar modes switch on above ~1.34 kHz **(computed)**. | Kirchhoff duct attenuation ([arXiv 1812.11063](https://arxiv.org/pdf/1812.11063)); commercial meters use "low frequency" pulses ([Fondriest/Eno](https://www.fondriest.com/news/eno-scientific-well-sounder-the-power-of-sound-echoes-surface-water-measurements.htm)); Judd patent resonance range 1–500 Hz ([US10787899B2](https://patents.google.com/patent/US10787899)) |
| 2 | JSN-SR04T ultrasonic as a fallback borewell sensor | **Cannot work.** Its range is 25–450 cm, and its 40 kHz carrier sits far above the tube cutoff, where wall loss is very high. Use it only for open dug wells or overhead tanks. | [Components101](https://components101.com/node/1522) |
| 3 | Sound speed from air temperature only | Add a **tube-diameter dispersion correction**. The effective speed drops by −0.82 % at 250 Hz in a 25 mm tube and −0.64 % in a 32 mm tube **(computed)**. Solinst's "Drop Tube Dia" setting exists for exactly this reason. | [Solinst 104 instructions](https://mail.solinst.com/products/level-measurement-devices/104-sonic-water-level-meter/instructions/sonic-water-level-meter-instructions/sonic-water-level-meter-instructions.php) |
| 4 | A single surface temperature reading is enough | Use the **mean of surface and downhole temperature**, as Eno and Solinst do. A 5.6 °C error gives about 1 % depth error. | [Solinst](https://mail.solinst.com/products/level-measurement-devices/104-sonic-water-level-meter/instructions/sonic-water-level-meter-instructions/sonic-water-level-meter-instructions.php); [Fondriest/Eno](https://www.fondriest.com/news/eno-scientific-well-sounder-the-power-of-sound-echoes-surface-water-measurements.htm) |
| 5 | Amazon Timestream as the time-series store | **Timestream for LiveAnalytics closed to new customers on 20 Jun 2025.** Use DynamoDB (PK well_id, SK ts, with TTL) plus S3 Parquet queried with Athena. | [AWS docs](https://docs.aws.amazon.com/timestream/latest/developerguide/AmazonTimestreamForLiveAnalytics-availability-change.html) |
| 6 | LocalStack Community for free local emulation | **The Community image was retired on 23 Mar 2026.** The remaining image needs an account and auth token, and its free tier covers non-commercial use only. `sam local` stays free. | [LocalStack blog](https://blog.localstack.cloud/2026-upcoming-pricing-changes/) |
| 7 | SNS SMS alerts to Indian phones | Local routes need **TRAI DLT registration** (Entity ID plus Template ID; organisation PAN, TAN, GSTIN and CIN). Without it, messages go over costlier international (ILDO) routes. The SNS free tier excludes SMS. For the demo, use email, push or a WhatsApp test number. | [AWS India sender ID docs](https://docs.aws.amazon.com/sms-voice/latest/userguide/registrations-sms-senderid-india.md); [SNS free tier](https://aws.amazon.com/free/serverless) |
| 8 | Train the daily forecaster on open Indian well data | CGWB/India-WRIS data is **quarterly** (22,965 wells, 2013–2022). Use it to calibrate seasonal amplitude and trend. Daily dynamics must come from the physics simulator. | [India Data Portal](https://ckandev.indiadataportal.com/dataset/groundwater/resource/580a8f6e-3d86-4ca7-ac7d-cd5df12b443c) |
| 9 | GRACE-FO as a per-site signal | Native resolution is **3° mascons, monthly**, so one or two pixels cover western Maharashtra. Use it only for regional context. | [Earth Engine catalog](https://developers.google.com/earth-engine/datasets/catalog/NASA_GRACE_MASS_GRIDS_V04_MASCON) |
| 10 | Measure the level whenever convenient | **Gate every reading to pump OFF**, then wait 30–60 s **(inference)**. Pump tones at 100 Hz (electromagnetic) and ~48 Hz (rotation) fall inside the sounding band **(inference)**. | Solinst notes cascading water and noise ([Solinst](https://mail.solinst.com/products/level-measurement-devices/104-sonic-water-level-meter/instructions/sonic-water-level-meter-instructions/sonic-water-level-meter-instructions.php)) |

A few smaller corrections also matter.

**ESP32 deep sleep on a dev board.** An ESP32 DevKit draws **5–20 mA in deep sleep, not the 10 µA in the datasheet**, because the LDO and USB bridge dominate ([Hubble guide](https://hubble.com/community/guides/esp32-power-modes-explained-what-the-datasheet-tells-you-and-what-it-doesn-t/)). This matters for any battery or solar variant.

**DynamoDB free tier.** The always-free 25 WCU/RCU applies to provisioned capacity, not on-demand ([AWS serverless free tier](https://aws.amazon.com/free/serverless)).

**Bedrock AgentCore.** AgentCore is **Paid-plan only**, so a team on the Free plan must host the Strands agent on Lambda ([AWS Free Tier](https://aws.amazon.com/free/)).

**Wall-loss figure.** One intermediate figure in the research, 0.72 dB/m at 40 Hz for a 42 mm tube, came from an arithmetic error. The correct value is about 0.078 dB/m. Do not use 0.72 dB/m.

## Low frequencies, matched filtering and two corrections make 150 m ranging feasible

### Sound speed is a temperature problem first, a humidity problem second

Sound speed in air is **331.3 m/s at 0 °C and rises about 0.6 m/s per °C** (343.21 m/s at 20 °C, 349.02 m/s at 30 °C). Humidity adds only about 0.1–0.6 %, and pressure is negligible ([Wikipedia: Speed of sound](https://en.wikipedia.org/wiki/Speed_of_sound)). For the simulator, the Cramer (1993) polynomial gives the full dependence on temperature, humidity, pressure and CO₂. The coefficients are listed in the parameter table ([Cramer implementation](https://gsd.ime.usp.br/yili/SpeedOfSound/Speed.html)). At 20 °C the polynomial gives 343.36 m/s at 0 % RH and 344.61 m/s at 100 % RH. The sensitivities are about +0.0125 m/s per %RH and +0.62 m/s per °C ([same](https://gsd.ime.usp.br/yili/SpeedOfSound/Speed.html)).

Temperature gives a fractional sensitivity of **dc/c ≈ 0.168 %/°C at 25 °C (computed)**. At 100 m, each 1 °C of error in the mean air-column temperature costs about 17 cm.

The borewell air column is not isothermal **(inference)**. In a Pune summer, the top metres follow surface air at 35–45 °C, and lower down the column approaches groundwater temperature. The simulator should integrate t = 2∫dz/c(z), and the device should use the mean of the surface DS18B20 reading and an entered or assumed water temperature. A Telangana hard-rock study logged borewell temperature profiles and found the deeper temperatures unaffected by surface variation ([NGRI](https://www.ngri.res.in/research-news/water-flux-granitic-aquifer.php)). However, **no measured air-column temperature profile for a Deccan borewell was found**, and the commonly assumed groundwater temperature of 25–30 °C is unsourced.

Air just above the water is probably near saturation **(inference)**. Using 100 % instead of 50 % RH shifts c by about 0.18 %, about 18 cm at 100 m.

### Wall loss sets the band and the tube diameter sets the range

In a tube, sound travels as a guided plane wave, so spherical spreading does not apply. Loss comes from viscothermal friction at the wall (Kirchhoff), which scales as **√f divided by the tube radius**: α ≈ (1/(a·c))·√(ων/2)·(1 + (γ−1)/√Pr) ([arXiv 1812.11063](https://arxiv.org/pdf/1812.11063)). Measurements by Fay (1940) confirmed the Kirchhoff wall effect but found an extra loss proportional to f, so real pipes lose more than smooth-wall theory predicts ([Fay 1940](https://sonicfield.org/library/attenuation-of-sound-in-tubes-1940)). The computed smooth-wall values below should therefore be treated as a best case.

| Inner diameter | First non-planar mode | 50 Hz | 100 Hz | 250 Hz | 500 Hz | 1 kHz | 2 kHz |
|---|---|---|---|---|---|---|---|
| 25 mm | ≈ 8.0 kHz | 0.14 dB/m | 0.20 | 0.32 | 0.46 | 0.65 | 0.92 |
| 32 mm | ≈ 6.3 kHz | 0.11 | 0.16 | 0.25 | 0.36 | 0.51 | 0.72 |
| 100 mm | ≈ 2.0 kHz | — | 0.05 | 0.08 | 0.12 | 0.16 | 0.23 |
| 150 mm (6" casing) | ≈ 1.34 kHz | 0.024 | 0.034 | 0.054 | 0.076 | 0.11 | 0.15 |

All values are **(computed)**, smooth-wall, c = 343–346 m/s. The cutoff is f_c = 1.8412·c/(2πa).

Round-trip wall loss in a 25 mm tube at 100 Hz is **about 12 dB to 30 m, 41 dB to 100 m and 61 dB to 150 m**. At 1 kHz the same depths cost 39, 129 and 193 dB. A 32 mm tube at 100 Hz costs 10, 32 and 48 dB **(computed)**. These numbers agree with Solinst's empirical maximum ranges by drop-tube diameter: **½" → 120 m, ¾" → 180 m, 1" → 300 m, 2" → 600 m** ([Solinst](https://mail.solinst.com/products/level-measurement-devices/104-sonic-water-level-meter/instructions/sonic-water-level-meter-instructions/sonic-water-level-meter-instructions.php)). Eno says tubes of 0.5–2 in give the cleanest signal and that a bare casing must be no wider than 12 in ([Fondriest/Eno](https://www.fondriest.com/news/eno-scientific-well-sounder-the-power-of-sound-echoes-surface-water-measurements.htm)).

Bare 150 mm casing has lower loss, but it contains the riser pipe, cable and rope, which produce clutter. Above about 1.3 kHz it also becomes multimodal **(inference)**. The design choice is therefore a **dedicated 25–32 mm PVC sounding tube** where one can be installed, with bare-casing operation below 1 kHz as the fallback.

Narrow tubes also slow the sound. The phase-velocity reduction is c_eff/c − 1 ≈ −(1 + (γ−1)/√Pr)/(√2·s). For a 25 mm tube that is **−0.82 % at 250 Hz and −0.41 % at 1 kHz** **(computed)**. This error is as large as a 2–5 °C temperature error, and it varies across the chirp band. The device must therefore correct it with a lookup by tube ID or calibrate it against a reflector at a known depth.

### Signal design: log chirp, loopback reference, coherent averaging

**Pulse.** Use a logarithmic or linear chirp over ~60–250 Hz (extend to 500 Hz for shallow wells), lasting 0.2–1 s. Process it with a matched filter against a loopback recording of the direct speaker-to-mic arrival, and coherently average N shots. Matched-filter gain is about 10·log₁₀(B·T): **about 20 dB for B = 400 Hz, T = 0.25 s, and 26 dB for T = 1 s**. Averaging adds 10·log₁₀N: **+10 dB for 10 shots and +15 dB for 32** **(computed)**.

**Resolution.** Range resolution c/(2B) is 35 cm at B = 500 Hz. Peak interpolation gives precision far finer than that. At 16 kHz sampling, one sample is 10.8 mm of depth; at 48 kHz it is 3.6 mm **(computed)**.

**Record window.** Time of flight is **58 ms at 10 m, 578 ms at 100 m and 867 ms at 150 m**, so the record window must be at least chirp length + 0.9 s. At 16 kHz that is about 24k samples (~96 kB as int32), which fits in the ESP32's 520 KB SRAM **(computed)**.

**Practical tricks.** Echometers sample 1 s of background noise before each shot to set gain ([SWPSC ppdl/1363](https://www.swpshortcourse.org/ppdl/1363)). Using the direct arrival as t = 0 removes I2S and DMA latency jitter **(inference)**. Subtracting a stored baseline impulse response removes fixed clutter, because joints stay put while the water echo moves. This is the same principle as Wellintel's pump-event logic, which treats an echo that does not move after pumping as an obstruction ([US20140009302A1](https://patents.google.com/patent/US20140009302A1/en)).

**Link budget.** At the deep end the budget is marginal **(inference)**. A 25 mm tube at 150 m and 100–250 Hz loses 60–100 dB round trip, against roughly 30–40 dB of combined processing gain and an estimated 80–90 dB of mic dynamic range. Ranging is comfortable to about 80–100 m. A 32 mm tube and a lower band help the most at depth. **No published SNR measurement of a MEMS-mic and small-speaker system in a 100 m+ tube exists**, so this link budget is theoretical and is the first thing to bench-test.

### Clutter, reflections and pump noise

**Water surface.** Water reflects almost perfectly. Air impedance is ~413 Pa·s/m at 20 °C ([Wikipedia: Acoustic impedance](https://en.wikipedia.org/wiki/Acoustic_impedance)), so the pressure reflection coefficient is R ≈ +0.9994, with no phase inversion **(computed)**.

**Area changes.** Every area change also reflects. In echometer practice, a liquid level or restriction gives a reflection of opposite polarity to an enlargement ([SWPSC ppdl/1363](https://www.swpshortcourse.org/ppdl/1363)). That polarity can separate casing steps from the water surface.

**Clutter strengths (all computed from R = (S₁−S₂)/(S₁+S₂), not measured).**
- A coupling lip in a 25 mm tube: R ≈ 0.08–0.15.
- A 6" → 4.5" casing step: R ≈ 0.3.
- The top of a riser pipe inside 150 mm casing: R ≈ 0.03–0.06.

**Commercial mitigations.** Commercial units handle clutter with min/max range gates and strongest-echo acceptance ([Solinst](https://mail.solinst.com/products/level-measurement-devices/104-sonic-water-level-meter/instructions/sonic-water-level-meter-instructions/sonic-water-level-meter-instructions.php); [Fondriest/Eno](https://www.fondriest.com/news/eno-scientific-well-sounder-the-power-of-sound-echoes-surface-water-measurements.htm)). Oil-field echometers calibrate velocity by counting the regular reflections from tubing collars ([SWPSC 2233](https://www.swpshortcourse.org/ppdl/2233)). BoreWise can do the same with the joint comb from 3 m pipe sections, if they turn out to be regular. The 3 m joint spacing is an **assumption** with no Indian source.

**Pump noise (inference; no measured Indian submersible spectrum was found).** A 50 Hz two-pole submersible runs at about 2,850–2,900 rpm. That should produce tones at ~48 Hz (rotation), 100 Hz (electromagnetic) and vane-pass harmonics, plus broadband cascading-water noise, all inside the sounding band.

### Resonance as a cross-check, and the accuracy target

A water-terminated column with an open top resonates at f_n = (2n−1)·c/(4(L + 0.6a)). The mode spacing is Δf = c/(2L): **about 1.7 Hz at 100 m and 6–17 Hz at 10–30 m** **(computed)**. The Judd patent uses resonance end corrections of L + 0.8d (open–open) and L + 0.4d (closed–open) ([US10787899B2](https://patents.google.com/patent/US10787899)). Resonance is therefore a useful independent check for shallow levels and a poor primary method for deep ones.

Both commercial benchmarks, the **Eno Well Sounder 2010 Pro and the Solinst 104, quote ±3 cm accuracy and 1 cm resolution** ([The Solar Store/Eno](https://thesolarstore.com/products/eno-scientific-well-sounder-2010-pro-portable-sonic-water-level-meter); [Solinst specs](https://solinst.com/products/level-measurement-devices/104-sonic-water-level-meter/datasheet/features-advantages-specs.php)). A realistic uncalibrated target for BoreWise is **±0.5–1 % of depth (±0.5–1.5 m at 100–150 m)**, and better with a known-depth reference **(inference)**. That is adequate for trend, recovery-curve and dry-up forecasting, where the slope matters more than the absolute value. An electric dipper, with roughly 1 cm accuracy ([India Water Portal](https://oldiwp.indiawaterportal.org/questions/need-quote-2-portable-water-level-indicators-dippers-100m-each-accuracy-1-cm)), is the field reference for validation.

## A ₹2k bill of materials covers acoustics, temperature and pump state

The sourced part prices add up to **₹1,461**:

| Part | Price | Source |
|---|---|---|
| ESP32-WROOM-32 dev board | ₹449 | [Robu.in](https://robu.in/product/esp32-38pin-development-board-wifibluetooth-ultra-low-power-consumption-dual-core/) |
| INMP441 microphone | ₹149 | [Robu.in](https://robu.in/product/inmp441-mems-high-precision-omnidirectional-microphone-module-i2s) |
| MAX98357A amplifier | ~₹469 | [price-history.in](https://price-history.in/product/max98357a-i2s-3w-class-d-amplifier-8KrHoqG5) |
| SCT-013-010 current transformer | ₹394 incl. GST | [Zbotic](https://zbotic.in/product/sct-013-010-non-invasive-split-core-current-transformer-ac-current-sensor-10a/) |

Adding a DS18B20 probe, a 2–3 inch speaker, PVC tube and fittings, an enclosure and a power supply (none of these prices were sourced) brings the total to **about ₹1.8–2.5k (inference)**. That is consistent with the ₹2–3k target and inside the ₹800–4,900 price band of the dry-run protectors and GSM starters BoreWise competes with ([Zbotic](https://zbotic.in/water-pump-dry-run-protection-float-and-current-sensor/); [IndiaMART IKON](https://m.indiamart.com/proddetail/mobile-motor-controller-with-float-sensor-dry-run-2856956086248.html?pos=1)).

**Microphone.** The INMP441 sets the low end of the band. It is flat from **60 Hz to 15 kHz (−3 dB at both ends)**, with 61 dBA SNR, 33 dBA SPL equivalent input noise, a 120 dB SPL acoustic overload point, and 7.8–50 kHz sampling at 24 bits ([INMP441 datasheet](https://microcontroller-course.web.cern.ch/Project_Material/resources/INMP441.pdf)).

**Amplifier.** The MAX98357A delivers **3.2 W into 4 Ω at 5 V** and accepts 8–96 kHz input ([Analog Devices](https://www.analog.com/en/products/max98357a.html)). A small speaker produces little output below ~150–200 Hz **(inference)**. The cheapest build therefore has an effective band of about 100–500 Hz, and a 40–50 mm+ woofer-type driver is the most valuable upgrade for deep wells. In a sealed coupler, the pressure may exceed the mic's 120 dB SPL overload point. Offset the mic or reduce drive for the direct path **(inference)**.

**Temperature and pump-state sensors.**
- **DS18B20:** ±0.5 °C from −10 to +85 °C, 12-bit conversion in 750 ms ([DS18B20 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/DS18B20.pdf)).
- **SCT-013-010:** clip-on, ±3 % non-linearity ([Zbotic](https://zbotic.in/product/sct-013-010-non-invasive-split-core-current-transformer-ac-current-sensor-10a/)). It gives pump on/off, run duration and the current signature without touching mains wiring.
- **INA219:** covers DC solar-pump variants (0–26 V, 0.5 % gain error) ([TI](https://www.ti.com/product/INA219)).

**Power.** The ESP32 draws 160–260 mA with Wi-Fi active ([Hubble](https://hubble.com/community/guides/esp32-power-modes-explained-what-the-datasheet-tells-you-and-what-it-doesn-t/)). A reading takes about 2–5 s of audio at ~150 mA plus 1–3 s of Wi-Fi at ~200 mA, so four readings a day cost about 1 mAh **(computed)**. Sleep current dominates: a bare module or a low-Iq regulator is mandatory for battery operation, and mains power from the pump panel is the simpler hackathon assumption.

## Deccan basalt borewells run dry in hours, which makes every cycle a pump test

### A two-tier aquifer with a hard-to-recharge lower tier

**Structure.** Basalt covers more than 95 % of Pune district, laid down as lava flows 7–45 m thick. Each flow has a massive base and a vesicular top a few metres to 10 m thick, and weathering reaches about 20 m ([CGWB Pune 2013](https://cgwb.gov.in/sites/default/files/2022-10/pune.pdf)).

**Two aquifers.** NAQUIM mapping describes **Aquifer-I**, weathered and fractured basalt at 9–30 m bgl with fractures at 5–22 m, and **Aquifer-II**, jointed and fractured basalt at 48–175 m, tapped by borewells of 50–180 m ([CGWB NAQUIM Pune](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf)).

**Recharge.** ACWADAM's Pune mapping found that **effective recharge reaches only 15–20 m below surface**. Borewells draw from confined aquifers in compact basalt that recharge effectively only where the confining layer ends ([India Water Portal/ACWADAM](https://www.indiawaterportal.org/amp/story/agriculture/farm/mapping-punes-aquifers)). The flows are nearly horizontal, so a shallow aquifer downslope can be a confined aquifer upslope, and pumping in one aquifer affects others ([ACWADAM 2009](https://admin.indiawaterportal.org/sites/default/files/iwp2/Hydrogeological_studies_for_improved_groundwater_management_strategies_in_the_dryland_areas_underlain_by_Deccan_Basalts_Purandar_ACWADAM_2009.pdf)).

**Modelling consequence (inference).** A borewell is a mixed-head well: its open hole connects several vesicular units, so the observed level is a weighted head. A two-layer simulator is the minimum faithful model.

### The numbers that matter for a simulated well

**Water levels.** In the deep aquifer, the static water level is **9–70 m bgl pre-monsoon and 1.5–45 m post-monsoon** ([CGWB NAQUIM Pune](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf)).

**Yield.** Aquifer-II yields **up to 2.5 L/s (~150 LPM), sustainable for only 0.5–3 h**. Aquifer-I yields 10–100 m³/day for 1–3 h ([same](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf)). The single most important fact for BoreWise is this: a 50–150 LPM pump draws a deep basalt bore down to its intake within hours. Every timed society pumping cycle is therefore a natural drawdown-and-recovery test **(inference)**.

**Long-term decline.** Over 2008–17, pre-monsoon levels declined at 58 of 202 stations, at **0.012–0.42 m/yr**. Decline covered about 65 % of the district's area, and more than 0.20 m/yr covered 21 % ([CGWB NAQUIM Pune](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf)).

**Drilling practice.** Pune rigs drill to an average of 200–300 ft (61–91 m). An estimated **5,000+ new bores a year** are drilled in PMC limits without permission, on top of 4,730 borewells inventoried in 2007–08 ([SANDRP 2016](https://sandrp.in/2016/07/04/groundwater-of-pune-an-over-exploited-and-ungoverned-lifeline/)).

**Pumps.** A Kirloskar 1 HP, 10-stage, 100 mm submersible delivers **15–105 LPM over 8–76 m head** ([Shakedeal](https://marketplace.shakedeal.com/kirloskar-bigflow-1010a-1-hp-100-mm-borewell-water-filled-submersible-pump-dp1)). A 1.5 HP, 21-stage unit covers 76–135 m head ([ShakeDeal](https://marketplace.shakedeal.com/kirloskar-kp4-0321s-1-5hp-oil-filled-borewell-submersible-pump-with-control-panel-dp1)).

**Unsourced construction details.** Casing diameter (6–7 inch through 6–20 m of overburden), intake depth and the HP mix in housing societies rest on anecdote. They are simulator assumptions, not facts.

### Pump-test equations BoreWise runs on every cycle

**Pumping and recovery.** Theis drawdown is s = (Q/4πT)·W(u), with u = r²S/(4Tt). Cooper-Jacob, valid for u ≤ 0.01, gives T = 2.30Q/(4πΔs) per log cycle ([ASBOG guide](https://open-exam-prep.com/study-guides/asbog/hydrogeology/well-hydraulics-aquifer-testing); [CZU recovery paper](https://home.czu.cz/storage/575/52485_Recovery.pdf)). The **Theis recovery method** plots residual drawdown against log((t′+t_p)/t′): s′ ≈ (Q/4πT)·ln((t′+t_p)/t′). It needs only Q, the pumping duration and the slope, and it is insensitive to rate fluctuations during pumping ([CZU](https://home.czu.cz/storage/575/52485_Recovery.pdf)). That makes it the right automatic per-cycle estimator.

**Well health.** Step-drawdown analysis, s_w = BQ + CQ² (Jacob) or BQ + CQᵖ (Rorabaugh), separates aquifer loss from well loss. Well efficiency is BQ/s_w ([MDPI Water 2019](https://www.mdpi.com/2073-4441/11/9/1784/htm)). **Walton's thresholds for C** (in s²/m⁵) are below 1,800 for a well-developed well, 1,800–3,600 for mild deterioration and above 3,600 for severe clogging ([same](https://www.mdpi.com/2073-4441/11/9/1784/htm)).

**Three cautions.**
1. **Wellbore storage.** Early-time data in a large-diameter well is distorted by water stored in the casing (Papadopulos & Cooper 1967) ([ANSDIMAT](https://ansdimat.com/help/source/quick_wellstorage.htm)). The textbook criterion t < 25·r_c²/T gives **~20 min for r_c = 0.075 m and T = 10 m²/d (computed; criterion not verified against Kruseman & de Ridder)**. In low-T basalt, much of a short cycle may therefore be storage-dominated.
2. **Storativity.** S from a single pumped well is unreliable because the effective radius and skin are unknown. Report T and a lumped "effective storage" only **(inference)**.
3. **Fractured-rock behaviour.** Fractured aquifers often depart from Theis. The derivative ds/d(ln t) flags dual-porosity, linear-flow or bounded responses **(inference)**.

### Seasonal model: a bucket with low specific yield

**Recharge factors.** The GEC norms put recharge at **4–10 % of rainfall for weathered basalt and 10–15 % for vesicular/jointed basalt**, with basalt specific yield of 1–3 %. GEC requires recharge estimated by water-table fluctuation to be reconciled with the infiltration estimate to within ±20 % ([GEC-1997](https://cgwb.gov.in/sites/default/files/inline-files/GEC97.pdf)). Tritium tracing in coastal basalt measured **4.0–9.6 % of rainfall (mean ~6.5 %)**, limited by "rejected recharge" when a shallow water table leaves no room to store more ([Rangarajan & Andrade](https://www.gondwanags.org.in/wp-content/uploads/2022/12/9-Full-Text-Rangarajan-and-Andrade.pdf)).

**Rainfall.** Normal annual rainfall in Pune district ranges from **468 mm (Daund) to 4,659 mm (Khandala)**. District totals swung between 540 and 1,648 mm over 2003–12 ([CGWB Pune 2013](https://cgwb.gov.in/sites/default/files/2022-10/pune.pdf)).

**Bucket model (inference).** Sy·dh/dt = f·P − Q_pump/A − (h − h_base)/τ, with f = 0.04–0.15, Sy = 0.01–0.03, and the monsoon rise capped near the surface. A 10 m rise at Sy = 0.02 needs 200 mm of net recharge. That is 20–40 % of 550 mm, which is why the eastern rain-shadow talukas cannot refill in weak years. The simulator needs two regional profiles:
- **East:** Baramati/Purandar/Daund, 470–550 mm rain, high extraction.
- **West/urban:** Pune city/Haveli, 700+ mm rain, dense bores and interference.

## Failure modes leave distinct fingerprints in level, recovery and current

The diagnostic engine compares three per-cycle quantities: the pre-pump static level h₀, the drawdown at a given Q and run time, and the recovery-derived T. The pump-current trace adds a fourth channel. The evidence column grades each entry:
- **A:** measured in Maharashtra or in a published test.
- **B:** a literature analogue or established theory applied here.
- **C:** physical inference that BoreWise must validate.

| Failure | Physical cause | Signature in the data | How BoreWise detects it | Recommended user action | Evidence |
|---|---|---|---|---|---|
| Seasonal depletion | Dry-season drainage of low-Sy aquifer; no recharge | h₀ declines smoothly over weeks; recovery-T constant; recovery complete but to lower h₀ | Trend fit on h₀; forecast day when h₀ + cycle drawdown reaches intake depth (P10/P50/P90) | Plan rationing and pre-book tankers before the P50 date | A. Purandar: 9 % of 74 dug wells dry by end-March, 33 % by end-May ([ACWADAM 2009](https://admin.indiawaterportal.org/sites/default/files/iwp2/Hydrogeological_studies_for_improved_groundwater_management_strategies_in_the_dryland_areas_underlain_by_Deccan_Basalts_Purandar_ACWADAM_2009.pdf)) |
| Weak monsoon | Rainfall deficit; rejected recharge | Post-monsoon h₀ peak below prior years; rise smaller than f·P/Sy predicts | Compare observed rise with IMD-driven bucket prediction | Issue an early-season warning; trigger recharge works | A. Tekawadi: 31 % → 69 % dry by May after two low-rain years ([ACWADAM 2009](https://admin.indiawaterportal.org/sites/default/files/iwp2/Hydrogeological_studies_for_improved_groundwater_management_strategies_in_the_dryland_areas_underlain_by_Deccan_Basalts_Purandar_ACWADAM_2009.pdf)) |
| Over-pumping / incomplete recovery | Off-time shorter than recovery time | Residual drawdown at next start > 0, ratcheting across cycles | Ratio of next-start level to 24 h maximum; recovery fraction per cycle | Lengthen off-time (e.g., "run 40 min, rest 2 h") | C (follows from Theis superposition, [CZU](https://home.czu.cz/storage/575/52485_Recovery.pdf)) |
| Fracture dewatering | Dynamic level falls below a major water-bearing fracture | Abrupt jump in ds/dt and step drop in apparent T at a recurring depth; recovery slope change at same depth | Change-point detection on ds/dt vs depth, repeated across cycles | Raise the pump-off threshold above the fracture depth; shorten cycles | B. Discrete strikes at 48–175 m and 0.5–3 h sustainability ([NAQUIM](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf)); USGS fractured-rock drops of up to 247 ft with temporary well failures ([USGS SIR 2010-5219](https://pubs.usgs.gov/sir/2010/5219)). No quantified Deccan step data found |
| Interference from neighbours | Overlapping cones of depression | h₀ dips or recovery distorted while own pump is OFF; time-of-day periodicity matching neighbours' schedules | Residual seasonality at pump-off times; cross-well correlation in a fleet | Coordinate pumping schedules across societies | B. Superposition theory ([CZU](https://home.czu.cz/storage/575/52485_Recovery.pdf)); tier interconnection observed in Tekawadi ([ACWADAM](https://admin.indiawaterportal.org/sites/default/files/iwp2/Hydrogeological_studies_for_improved_groundwater_management_strategies_in_the_dryland_areas_underlain_by_Deccan_Basalts_Purandar_ACWADAM_2009.pdf)) |
| Clogging / encrustation / skin | Well-loss term grows (deposits, fines) | Drawdown at same Q rises over months while recovery-T is stable; specific capacity Q/s falls; fast early recovery jump then normal slope | Track fitted C against Walton thresholds (1,800 / 3,600 s²/m⁵) | Schedule well rehabilitation or flushing | B. Walton thresholds ([MDPI Water 2019](https://www.mdpi.com/2073-4441/11/9/1784/htm)) |
| Pump wear / efficiency loss | Impeller wear lowers Q | Smaller drawdown for same ON time, unchanged recovery-T and h₀ (opposite sign to clogging); current drift | Drawdown-volume vs recovery-volume ratio; current trend | Pump service before failure | C |
| Dry running | Level reaches intake | Level plateaus at intake depth with pump ON; current drops (vendor guidance: 20–40 % lower; trip at 80 % of normal) | Current threshold plus level at intake | Automatic relay cut-off; extend rest time | C/weak. Vendor blog, internally inconsistent ([Zbotic](https://zbotic.in/water-pump-dry-run-protection-float-and-current-sensor/)) |
| Single-phasing / supply fault | Phase loss or voltage problem | Current anomaly with no level change | Current waveform rules | Electrician call; phase-failure relay | C/weak ([Zbotic](https://zbotic.in/water-pump-dry-run-protection-float-and-current-sensor/)) |
| False echo (acoustic) | Joint, casing step, riser top, cable bundle | Echo fixed in time across pump on/off; may have opposite polarity to water | Baseline subtraction; Wellintel-style "did it move after pumping" test; range gates | None (handled automatically); re-learn baseline after maintenance | B ([US20140009302A1](https://patents.google.com/patent/US20140009302A1/en); [SWPSC 1363](https://www.swpshortcourse.org/ppdl/1363)) |
| Pump-noise contamination (acoustic) | Motor tones and cascading water in band | Elevated noise floor; tonal lines at ~48/100 Hz | Pre-shot 1 s noise sample; gate to pump OFF + 30–60 s | None (automatic) | C (noise-sample practice from [SWPSC 1363](https://www.swpshortcourse.org/ppdl/1363)) |
| Temperature or dispersion bias (acoustic) | Wrong c(z) or uncorrected tube ID | Diurnal pseudo-oscillation in level correlated with surface temperature; constant % offset vs dipper | Regress level residuals on DS18B20 temperature; dipper calibration | Enter tube ID; one-time dipper calibration | B ([Solinst](https://mail.solinst.com/products/level-measurement-devices/104-sonic-water-level-meter/instructions/sonic-water-level-meter-instructions/sonic-water-level-meter-instructions.php)) |
| Stuck / flatline sensor | Firmware hang, mic failure | Zero variance over N hours while pump cycles | Variance-collapse rule vs pump state | Device restart / replace | B ([Leigh et al.](https://arxiv.org/pdf/1810.13076)) |
| Spike / glitch | Spurious echo pick | Rate of change faster than aquifer allows | Forecast prediction-interval test (ARIMA-style 99 % PI) | None (auto-flag) | B (>0.80 accuracy for spikes/shifts, [Leigh et al.](https://arxiv.org/pdf/1810.13076)) |
| Step offset | Tube or sensor re-hung | Permanent level shift not matched in recovery-T or in neighbours | Change-point (PELT/BOCPD) plus cross-well coherence | Recalibrate against dipper | B ([Leigh et al.](https://arxiv.org/pdf/1810.13076); [BOCPD](https://arxiv.org/abs/0710.3742)) |
| Drift | Transducer ageing, tube fouling | Slow divergence from physics model, incoherent with neighbours | CUSUM on forecast residuals | Recalibrate | B |
| Dropout / out-of-range | Connectivity loss; level above ground or below well depth | Missing data; impossible values | Rules (caught with no false positives in Leigh et al.) | Check power and network | A ([Leigh et al.](https://arxiv.org/pdf/1810.13076)) |
| Water-quality degradation (secondary) | Sewage mixing, geogenic fluoride | Not visible acoustically | Out of scope; flag as roadmap sensor | Lab test | A. Nitrate >45 mg/L in 18 of 102 deep samples ([NAQUIM](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf)) |

Distinguishing a sensor fault from a real event depends on context. A real event matches pump state and rainfall and appears in neighbouring wells. A fault appears in one device and breaks physical consistency **(inference)**. Layered detection follows from Leigh et al.'s finding that **rules catch every impossible, out-of-range and missing value with zero false positives**, while forecast-interval tests handle spikes and shifts, and that no single method suits every anomaly type ([arXiv 1810.13076](https://arxiv.org/pdf/1810.13076)).

## Quarterly public data calibrates the seasons while physics supplies the daily dynamics

### What open data exists and what it can and cannot do

**CGWB / India-WRIS wells.** The best open well dataset is the CGWB/India-WRIS "Changes in Depth to Water Level" CSV: **22,965 wells in 568 districts, 2013–2022, measured quarterly** (January, pre-monsoon, August, November). It is 75 MiB, licensed ODC-By ([India Data Portal](https://ckandev.indiadataportal.com/dataset/groundwater/resource/580a8f6e-3d86-4ca7-ac7d-cd5df12b443c)). The craigdsouza/cgwb repository documents routes to 1996–2017 quarterly data and a station shapefile via WFS ([GitHub](https://github.com/craigdsouza/cgwb)).

**Rainfall driver.** IMD gridded rainfall via `imdlib` provides **0.25° daily data from 1901** plus real-time feeds ([imdlib docs](https://imdlib.readthedocs.io/en/latest/Usage.html)). The Pune cells sit around 18.5°N, 73.75–74°E.

**Satellite and reanalysis.** GRACE/GRACE-FO JPL RL06.3 mascons are monthly 3° solutions served at a 55.66 km pixel ([Earth Engine](https://developers.google.com/earth-engine/datasets/catalog/NASA_GRACE_MASS_GRIDS_V04_MASCON); [PO.DAAC](https://podaac.jpl.nasa.gov/announcements/2024-09-12-Release-of-GRACE-FO-JPL-RL06.3-for-L2-3-and-MASCON-Data-Sets)). ERA5-Land latency is reportedly more than 5 days ([ECMWF forum](https://forum.ecmwf.int/t/latency-of-era5-land-data/11181)).

**What is missing.** **No public bulk DWLR (hourly or daily) download was found.** No open GSDA well series exists. The Atal Jal monitoring SOP measures monthly, but there is no public bulk export ([Atal Jal SOP](https://ataljal.hid.gov.in/MIS/data/WebContent/Document/Report_638495585728219016.pdf)). CGWB's gwdata portal was in maintenance mode during research, so the Maharashtra yearbook figures could not be checked.

**Implications (inference).**
- **CGWB quarterly data** should fit the simulator's pre/post-monsoon distributions, seasonal amplitude and inter-annual trend for Pune and its neighbouring districts. It cannot train a daily or per-cycle model.
- **Sim-to-real caveat.** Many CGWB observation wells are dug wells or shallow piezometers. The open data may therefore under-represent deep-borewell behaviour, and the pitch should say so.
- **GRACE** becomes a single regional-storage slide.
- **Missing dataset.** No public dataset of borewell dry-ups or failures exists. BoreWise telemetry would create the first one, which is a credible novelty claim.

### Model ladder: baselines first, quantiles always

**Evidence that simple models compete.** On 17 German wells, **NARX beat LSTM and 1D-CNN on average when training data was small**. Median NSE was at least 0.5 and the best wells reached 0.8–0.9 ([Wunsch et al. 2021, HESS](https://hess.copernicus.org/articles/25/1671/2021/)).

**Evidence for hybrids.** Using ML to correct MODFLOW, an LSTM with extraction and recharge features reached NSE 0.89. RF and XGBoost reached 0.87–0.88, but they could not correct steady trends while the LSTM could, and the LSTM cut RMSE by 0.17–1.59 m per well ([Shuai et al. 2024](https://www.mdpi.com/2071-1050/16/2/653/html)).

**Uncertainty.** LSTM-based Lower Upper Bound Estimation produced about 25 % narrower interval-width scores than a feed-forward network ([Nourani et al. 2022](https://agris.fao.org/search/en/providers/122535/records/65df307863b8185d9cab83f7)).

**Recommended ladder (inference).**
1. Climatology, linear recession and the bucket model as baselines.
2. LightGBM/XGBoost with quantile objectives (P10/P50/P90) on lagged level, 30/60/90-day IMD rainfall, pump hours and day-of-year features.
3. A global LSTM or TFT across simulated wells, only if time allows.
4. Throughout, train ML on the residual of the physics model, as in Shuai et al.

**Dry-up date (inference).** Read it as the first crossing of the intake depth in each forecast quantile, cross-checked with survival models (Cox or random survival forest, with non-drying wells right-censored) and with analog-year Monte Carlo rollouts. **No paper reports MAE-in-days for groundwater time-to-threshold forecasting, and no Indian borewell dry-up survival study was found.** BoreWise defines this metric itself and should say so.

### Validation plan that judges will trust

**Domain randomization.** This is the canonical sim-to-real method: train on many randomised simulators so that reality looks like one more variant ([Tobin et al. 2017](https://arxiv.org/pdf/1703.06907)).

**Plan (assembled from general practice; no published standard exists for simulation-only groundwater forecasters).**
1. **Check the simulator against reality.** Compare simulated and CGWB-Pune distributions of seasonal depth and amplitude with KS tests and Q–Q plots.
2. **Randomise and hold out.** Randomise T, S, depth, pump rate and schedule, recharge factor, neighbour count and sensor noise. Hold out whole parameter regions (for example the lowest-S decile and the deepest wells) and drought years (2015 and 2018 IMD analogs). Never use random row splits.
3. **Test on real wells.** Check that forecast trajectories pass through real quarterly CGWB points, using rolling-origin evaluation.
4. **Run Monte Carlo.** Simulate at least 1,000 society-years per monsoon scenario and report 95 % bootstrap confidence intervals.
5. **Report these metrics:**
   - level MAE/RMSE at 7, 30 and 90 days, and NSE versus climatology
   - dry-up P50 MAE in days, lead-time distribution, and Brier score for "dry within 30 days"
   - P10–P90 coverage (target 80 %), PIT histograms, CRPS and pinball loss, with conformal recalibration if coverage misses
   - per-class fault F1, alarms per sensor-month, and time-to-detect
6. **Stress-test.** Run ablations and inject faults and noise beyond the training range.
7. **State the limits in the pitch.** Hardware is simulated, and real-data validation is quarterly only.

## A serverless AWS stack runs the full demo for near zero cost

### Architecture

**Data flow.**
1. **Ingest.** Simulated ESP32s publish over MQTT with X.509 certificates to AWS IoT Core's **Basic Ingest** topic (`$aws/rules/borewise_ingest`). Basic Ingest carries no messaging charge; only rules and actions are billed ([IoT Core pricing](https://aws.amazon.com/iot-core/pricing/)).
2. **Process.** An IoT Rule sends readings through SQS to a processing Lambda. The Lambda computes echo-to-depth with temperature and dispersion corrections, detects pump state from current, and fits the recovery curve with numpy/scipy.
3. **Store.** Results go to DynamoDB: `WellReadings` (PK well_id, SK ts, TTL 30–90 days) and `WellState` (latest state). Raw data lands in S3 as Parquet for Athena and training **(inference: recommended design)**.
4. **Forecast and validate.** EventBridge Scheduler runs nightly forecasts. A single batch Lambda or a Step Functions Distributed Map runs the 500-well validation. SNS fans out alerts.

**Fallback ingest.** For a pure simulator, API Gateway HTTP API at about $1 per million requests, or a Lambda function URL, is simpler ([API Gateway pricing](https://aws.amazon.com/api-gateway/pricing/)).

**Open-source AWS tools for the track requirement.**
- **Strands Agents** (`pip install strands-agents`, Python 3.10+). Bedrock is the default provider, with Anthropic, OpenAI, Ollama, LiteLLM and others supported. Plain Python functions become tools with `@tool` ([Strands quickstart](https://strandsagents.com/docs/user-guide/quickstart/python/index.md)). The Lambda deployment guide uses an ARM64 Python 3.12 layer and a 128 MB, 30 s example, needs `bedrock:InvokeModel` permissions, and does not stream ([Strands Lambda guide](https://strandsagents.com/docs/user-guide/deploy/deploy_to_aws_lambda/index.md)). Set **60–120 s and 512 MB–1 GB** for multi-tool turns **(inference)**.
- **Cedar** (open-source policy language; Rust core) enforces rules such as "farmers see only their own wells; ward officers see ward aggregates" ([AWS Open Source Blog](https://aws.amazon.com/blogs/opensource/using-open-source-cedar-to-write-and-enforce-custom-authorization-policies/)). Amazon Verified Permissions is the managed version at **$5 per million requests** ([What's New](https://aws.amazon.com/about-aws/whats-new/2025/06/amazon-verified-permissions-reduces-price/)).
- **Finch** builds the Lambda container images ([Introducing Finch](https://aws.amazon.com/blogs/opensource/introducing-finch-an-open-source-client-for-container-development)).
- **SAM CLI** `sam local` handles local testing.

Using all four shows the "AWS open-source tool" requirement several times over.

### Costs and limits

**Credits.** Accounts created on or after **15 Jul 2025 get $100 in credits at sign-up plus up to $100 more** at $20 each for five starter activities. Two of those activities, a Lambda function URL app and an AWS Budgets alert, are things BoreWise does anyway. The **Free plan** lasts 6 months, or until credits run out, and some services are unavailable on it ([AWS News Blog](https://aws.amazon.com/blogs/aws/aws-free-tier-update-new-customers-can-get-started-and-explore-aws-with-up-to-200-in-credits)).

| Component | Free allowance | Beyond free | Demo implication |
|---|---|---|---|
| Lambda | 1M requests + 400k GB-s/month, always free ([pricing](https://aws.amazon.com/lambda/pricing/)) | $0.20 per 1M requests | 500 wells × 15 min = 1.44M msgs/month **(computed)**. Batch 10–50 per invocation to stay under 1M |
| DynamoDB | 25 GB, 25 WCU, 25 RCU provisioned, always free ([free tier](https://aws.amazon.com/free/serverless)) | On-demand not covered | Use small provisioned capacity |
| IoT Core | 12 months: 500k msgs, 2.25M connection-min, 250k rules ([pricing](https://aws.amazon.com/iot-core/pricing/)) | ~$1 per 1M msgs (5 KB units) | Basic Ingest avoids the messaging charge |
| API Gateway | 12 months: 1M HTTP + 1M REST calls ([pricing](https://aws.amazon.com/api-gateway/pricing/)) | HTTP ~$1, REST ~$3.50 per 1M | HTTP API for the dashboard |
| SNS | 1M publishes, 100k HTTP, 1k email, always free; **no SMS** ([free tier](https://aws.amazon.com/free/serverless)) | — | Email/push in the demo |
| SQS / Step Functions | 1M requests; 4,000 state transitions/month ([free tier](https://aws.amazon.com/free/serverless)) | — | ~500 wells × 7 states once a month uses the allowance; prefer a batch Lambda |
| Amplify Hosting | 12 months: 1,000 build-min, 15 GB served ([pricing](https://aws.amazon.com/amplify/pricing/)) | $0.15/GB served | Host the dashboard |
| SageMaker | Serverless inference 150k s/month for 2 months; notebooks 250 h ml.t3.medium ([pricing](https://aws.amazon.com/sagemaker-ai/pricing/)) | Real-time endpoints are always-on | Train only; serve from a Lambda container |
| WhatsApp (End User Messaging Social) | — | AWS fee $0.002 per India utility msg + Meta fee ([pricing](https://aws.amazon.com/end-user-messaging/pricing)) | Production channel for Marathi alerts |
| Cognito / CloudWatch | 10k MAU; 10 metrics, 10 alarms (secondary source, unverified) ([agentdeals.dev](https://agentdeals.dev/aws-free-tier-2026)) | — | Dashboard login |

**Real cost risks.** The real risks are Bedrock token spend, SMS to India, and anything always-on: SageMaker real-time endpoints, Fargate, Timestream for InfluxDB. Develop the agent locally against Ollama and switch to Bedrock for the demo **(inference)**.

**Alert templates.** Write alert templates in DLT-ready form from day one, for example "BoreWise: Well {#var#} level {#var#} m; pump {#var#}. Advice: {#var#}", to show judges a production path. **Not retrieved:** the exact India SMS per-message rate, Meta's India utility fee, and Mumbai-region SageMaker rates. Confirm all three in the AWS Pricing Calculator for ap-south-1.

## Societies spend lakhs reacting to failures nobody forecasts

### Demand evidence from Pune

**Tanker prices.** In April 2026, south Pune paid **₹666 per 10,000 L for a PMC tanker versus ₹1,500–1,700 for a private one** ([Free Press Journal](https://www.freepressjournal.in/amp/pune/residents-staged-a-protest-against-tanker-mafia-demand-permanent-water-supply-in-south-pune)).

**Society spending.** By June 2026, per-tanker cost had risen from about ₹1,000 to nearly ₹2,000. Sun Exotica in Yewalewadi spent **about ₹7.5 lakh from March to June at roughly 100 tankers a month**. Venkatesh Puram in Ambegaon (142 members) saw maintenance rise by about ₹1 lakh a month ([The Bridge Chronicle](https://www.thebridgechronicle.com/pune/pune-water-crisis-tanker-costs-housing-society-maintenance-bills-rise-agn97)). An 850-flat Kharadi society spent about ₹8 lakh a month in 2025 ([NeeRain/TOI](https://neerain.com/taps-and-borewell-dry-up-its-the-return-of-water-tanker-raj/)). Annual tanker spend ranges from a few thousand rupees to ₹30–40 lakh per society ([Citizen Matters](https://citizenmatters.in/pune-tanker-operations-corruption-20153)).

**PMC tanker trips.** Trips rose from **3,06,842 (2021-22) to 3,54,254 (2022-23) to 4,00,348 (2023-24)** ([Punekar News](https://punekarnews.in/pune-struggles-with-water-scarcity-150-160-tankers-deployed-daily-to-meet-demand-4-03-lakh-rounds-of-tankers-recorded-in-last-fiscal)), and reached about 4.9 lakh in 2024-25 ([FPJ](https://www.freepressjournal.in/amp/pune/residents-staged-a-protest-against-tanker-mafia-demand-permanent-water-supply-in-south-pune)).

**Seasonal decline.** In May 2026, **11 of Pune district's 13 talukas** showed water levels below their 5-year May average ([Pune Pulse](https://www.mypunepulse.com/?p=205378)).

**Value per society (computed).** At ₹1,500–2,000 per private load, avoiding one tanker a week saves **₹78k–1.04 lakh a year**. A ₹2–2.5k device pays back in its first summer.

**Gaps.** No survey was found of how many Pune societies have borewells. No named 2023–26 story was found of a specific Pune society's borewell failing, though shallow 30–40 ft wells drying is reported ([NeeRain/TOI](https://neerain.com/taps-and-borewell-dry-up-its-the-return-of-water-tanker-raj/)).

**Farm side.** In a Karnataka study of 1,500 farmers, **over 60 % had a well dry up, at about ₹50,000 per failed borewell**. Fewer than 25 % redrilled, and income, assets and teenage schooling fell afterwards ([IDR summary of the AER study](https://idronline.org/can-indian-farmers-adapt-to-water-loss/)). This is the best available proxy, but it is not a Maharashtra figure.

**Pump costs.** A replacement 1–3 HP submersible costs ₹7,000–19,300 ([IndiaMART](https://m.indiamart.com/impcat/borewell-pumps.html)).

### Competitor map

| Category | Example | What it does | Gap BoreWise fills |
|---|---|---|---|
| Sensorless estimator | Waterlab **Bhujal** app (2019); IoT device in field test Apr 2024; claims 98.5–100 % accuracy on 25 Bangalore bores in a CGWB test; Pune pilot ([Krishi Jagran](https://krishijagran.com/industry-news/waterlab-solutions-introduces-innovative-approach-to-groundwater-management-with-bhujal-app-bhujal-iot/?amp=1)) | Spot water-level estimate | No continuous recovery analytics, forecast or pump control (current status unknown). Closest competitor |
| Apartment water meters | **WEGoT**: 30,000+ homes, hardware free, ₹149–349/flat/month ([YourStory](https://yourstory.com/2020/07/cloud-based-water-management-startup-wegot)) | Consumption metering | Measures use, not aquifer state. Proves societies pay subscriptions |
| Industrial water IoT | **FluxGen**: 110+ customers, ~₹5 Cr FY24 revenue, ₹28 Cr pre-Series A ([YourStory](https://yourstory.com/2024/08/fluxgen-startup-water-wastage-management-in-india-industrial-sector); [Entrackr](https://entrackr.com/snippets/climate-tech-startup-fluxgen-raises-rs-28-cr-in-pre-series-a-8777160)) | Flow/level for industry | No borewell-forecast focus |
| Pump IoT | **KirloSmart** ([Impeller.net](https://impeller.net/?p=85580)); GSM starters such as IKON at ₹4,900 ([IndiaMART](https://m.indiamart.com/proddetail/mobile-motor-controller-with-float-sensor-dry-run-2856956086248.html?pos=1)) | Remote start/stop, react to dry run | Reacts after dry running begins; no level or forecast |
| Utility pilot | **BWSSB**: AI/IoT on 5 public borewells ([Benzinga](https://in.benzinga.com/content/37927769/bengalurus-solution-to-water-scarcity-ai-and-iot-for-better-borewell-management)) | Flow monitoring, throttling | Municipal only |
| Government DWLR | 5,260 DWLRs under the National Hydrology Project ([SuperKalam/PIB](https://superkalam.com/current-affairs/04-08-2026/water-management-and-conservation-c78785ee-cfd6-461a-8800-c1f2bea3a02d)); 0–400 m, 0.1 mm resolution ([Vision World Tech](https://visionworldtech.com/wp-content/uploads/2025/08/technical-spesification-of-Piezometer-With-DWLR-Vision-World-Tech-.pdf)) | Accurate level in dedicated piezometers | Needs a non-pumped piezometer; no price found |
| Imported sonic meters | **Eno** Well Sounder 2010 Pro $1,675–1,914; Well Watch 700 $2,915 ([Fondriest](https://fondriest.com/eno-scientific-well-watch-700-water-level-monitor.htm)); **Solinst 104** | ±3 cm acoustic ranging | ~50–100× BoreWise's price; no hydrogeological analytics |
| Patents | Wellintel (abandoned) ([US20140009302A1](https://patents.google.com/patent/US20140009302A1/en)); borewell tapper + GSM ([USPTO 12241770](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12241770)) | Wellhead acoustic level | Check freedom to operate; the tapper patent is the nearest Indian-style analogue |
| Citizen monitoring | MARVI Bhujal Jankaars ([IWP](https://www.indiawaterportal.org/amp/story/governance-and-policy/governance/developing-effective-participatory-groundwater-monitoring-program-village-level)); Atal Jal monthly readings | Manual levels, local-language sharing | Manual and monthly; BoreWise automates it |

### Policy hooks and channels

**Atal Bhujal Yojana.** **Only 3,892 wells had functioning meters against a target of 50,000** in the World Bank results framework ([World Bank P158119](https://projects.worldbank.org/P158119?lang=en)), while 8,203 gram panchayats, 1,133 of them in Maharashtra, prepared water budgets ([PIB, May 2026](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/may/doc2026527877101.pdf)). That gap is the strongest single policy hook for cheap automated sensing.

**Regulation.** The Maharashtra Groundwater Act 2009 defines **deep wells as deeper than 60 m**. It bans them for non-drinking use in notified areas and levies a cess elsewhere, and it requires all wells and rigs to register ([IWP note on the Act](https://oldiwp.indiawaterportal.org/sites/default/files/iwp2/the_maharashtra_groundwater_development_and_management_act_2009_english_note.pdf)). Most Pune bores exceed 60 m, so the data BoreWise produces maps directly onto the Act's categories. Whether the cess is actually implemented was not verified.

**Proof that local data changes outcomes.** Six villages with WOTR/ACWADAM water budgeting stayed off the 3,905-village scarcity list in rabi 2012-13 while their neighbours used tankers ([India Water Portal](https://www.indiawaterportal.org/drinking-water/drought-free-maharashtra-six-small-villages-one-big-lesson)).

## Conflicting statistics, reconciled

| Statistic | Conflicting values | Why they differ | Cite in the pitch |
|---|---|---|---|
| National groundwater assessment | **GWRA 2024:** 6,746 units, 751 over-exploited (11.1 %), stage 60.47 %, extraction 245.64 BCM ([GKToday](https://www.gktoday.in/groundwater-resource-assessment-report-2024/)). **GWRA 2025:** 6,762 units, 730 over-exploited (10.8 %), stage 60.63 %, extraction 247.22 BCM, recharge 448.52 BCM ([EA Water](https://www.eawater.com/?p=10539); [C4S](https://c4scourses.in/national-affairs/dynamic-ground-water-resources-of-india-2025-report/); release date [Vision IAS](https://visionias.in/current-affairs/news-today/2025-12-30/environment/ministry-of-jal-shakti-releases-dynamic-groundwater-resource-assessment-report-2025)) | Different assessment years. The over-exploited count improved while extraction rose | **GWRA 2025**: "India extracts ~247 BCM/yr, 60.6 % of what is extractable; 730 of 6,762 units are over-exploited". Note that the figures come from secondary summaries; verify against the primary report before print |
| Maharashtra stage | 52.99 % (GWRA 2024, primary CGWB) vs 54.97 % (2020, RGICS) | Different years | **52.99 % (2024)**, framed as "the state average hides seasonal, local stress" |
| Pune district stage | 71.51 % (2008-09) vs 73.87 % (2013) | Different years; no newer taluka figures found | Avoid district stage. Cite **11 of 13 talukas declining (May 2026)** and Baramati 95 % / Purandar 92 % (2013) as historical |
| CGWB Pune Aquifer-II static level | 9–70 m pre-monsoon (Table) vs 6–45 m (Sec 5.1) ([NAQUIM](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf)) | Internal inconsistency, probably pre-monsoon vs annual range | Simulate **9–70 m pre / 1.5–45 m post** |
| Aquifer-II transmissivity | 18–89 m²/d (text) vs 25–250 m²/d (Table 5.1) | Internal inconsistency; the text range matches shallow dug-well values in the 2013 report | Use **5–100 m²/d log-uniform** as the core range, with a 250 m²/d tail |
| Aquifer-II storativity | 3.4e-4–6.37e-4 (text) vs 1.2e-4–3.57e-4 (Table) | Internal inconsistency | Use **1e-4 to 1e-3** as an "effective storage" range |
| Post-monsoon dug-well depth 2011 | 0.65–15.65 m (text) vs 0.09–14.65 m (summary table) ([CGWB 2013](https://cgwb.gov.in/sites/default/files/2022-10/pune.pdf)) | Typo-level inconsistency | Either; it is immaterial to the deep simulator |
| Pune city water-level decline | 0.2–0.25 m/yr (SANDRP; internally inconsistent) vs 0.012–0.42 m/yr district station range (NAQUIM) | Different scopes | NAQUIM district range |
| Atal Bhujal impact | World Bank: 47 blocks arrested decline (target 80). PIB: 180 of 229 blocks showed improvement | Different metrics ("arrested decline" vs "measurable improvement") and dates | **World Bank 3,892 of 50,000 metered wells** (the gap BoreWise fills). If improvement is quoted, label it as PIB's metric |
| "11,000 villages drought-free" | Attributed to Atal Bhujal water budgeting (VisionIAS) vs Jalyukt Shivar (PIB doc) | Secondary site misattribution | Attribute to **Jalyukt Shivar, per PIB**, or omit |
| PMC tanker trips | 4.9 lakh (2024-25) vs "4.59 lakh in Feb 2026 alone" (same FPJ article) | The monthly figure is implausible next to the annual one | Use the **3.07 → 3.54 → 4.00 lakh (FY22–24)** series from Punekar News |
| Private tanker price | ₹1,500–1,700 per 10,000 L (FPJ) vs ₹1,000 → ₹2,000 per load (Bridge Chronicle) vs "up to ₹5,000" (councillor allegation) | Capacity often unstated; the allegation is unverified | **₹1,500–2,000 per load**; never ₹5,000 |
| Eno price | $1,675 (Fondriest) vs $1,914 (Solar Store) for the 2010 Pro; $2,915 for the Well Watch 700 | Different retailers and products | "Imported sonic meters cost **$1,700–2,900**" |
| Dry-run current | The Zbotic blog says both higher and lower current | Internal inconsistency | Physically, a dry-running submersible is underloaded, so current falls (blog: 20–40 % lower). Treat as a hypothesis to validate |

## Master parameter table

The **Used in** column refers to these simulator and pipeline modules:
- **ACU:** acoustic forward model and depth estimator
- **HW:** hardware model and power budget
- **HYD:** aquifer and well physics
- **SEAS:** seasonal recharge model
- **PUMP:** pump and schedule model
- **DIAG:** failure and fault engine
- **ML:** forecaster and validation
- **AWS:** cloud pipeline and cost model

| Parameter | Typical value / range | Units | Source | Used in |
|---|---|---|---|---|
| Speed of sound at 0 °C | 331.3 | m/s | [Wikipedia](https://en.wikipedia.org/wiki/Speed_of_sound) | ACU |
| Temperature coefficient of c | ~0.6 (0.62 with humidity term) | m/s per °C | [Wikipedia](https://en.wikipedia.org/wiki/Speed_of_sound); [Cramer impl.](https://gsd.ime.usp.br/yili/SpeedOfSound/Speed.html) | ACU |
| c at 20 / 30 °C (dry) | 343.21 / 349.02 | m/s | [Wikipedia](https://en.wikipedia.org/wiki/Speed_of_sound) | ACU |
| Cramer 1993 coefficients a0…a15 | 331.5024, 0.603055, −0.000528, 51.471935, 0.1495874, −0.000782, −1.82e-7, 3.73e-8, −2.93e-10, −85.20931, −0.228525, 5.91e-5, −2.835149, −2.15e-13, 29.179762, 0.000486 | — | [Cramer impl.](https://gsd.ime.usp.br/yili/SpeedOfSound/Speed.html) | ACU |
| Humidity sensitivity of c | +0.0125 (0 → 100 % RH ≈ +1.25 m/s at 20 °C) | m/s per %RH | [Cramer impl.](https://gsd.ime.usp.br/yili/SpeedOfSound/Speed.html) | ACU |
| Pressure / CO₂ sensitivity | −0.006 per kPa; −0.009 per +100 ppm | m/s | [Cramer impl.](https://gsd.ime.usp.br/yili/SpeedOfSound/Speed.html) | ACU (ignore) |
| Fractional temperature sensitivity | 0.168 at 25 °C | %/°C | Computed | ACU error model |
| Rule of thumb: temperature error → depth error | 5.6 °C → 1 % | — | [Solinst](https://mail.solinst.com/products/level-measurement-devices/104-sonic-water-level-meter/instructions/sonic-water-level-meter-instructions/sonic-water-level-meter-instructions.php) | ACU |
| Surface air temperature (summer) | 35–45 | °C | Inference | ACU c(z) profile |
| Groundwater / deep air-column temperature | 25–30 | °C | Assumption (unsourced) | ACU c(z) profile |
| RH near water surface | 90–100 | % | Inference | ACU |
| Air kinematic viscosity ν; Pr; γ | 1.5e-5; 0.71; 1.4 | m²/s; —; — | Standard properties | ACU |
| Air specific impedance | 413.3 (20 °C), 409.4 (25 °C) | Pa·s/m | [Wikipedia](https://en.wikipedia.org/wiki/Acoustic_impedance) | ACU |
| Water-surface reflection coefficient | +0.9994 | — | Computed (Z_water 1.48 MRayl standard) | ACU |
| Tube wall attenuation formula | α ≈ (1/(a·c))·√(ων/2)·(1+(γ−1)/√Pr) | Np/m | [arXiv 1812.11063](https://arxiv.org/pdf/1812.11063) | ACU |
| Wall loss, 25 mm tube | 0.14 / 0.20 / 0.32 / 0.46 / 0.65 at 50 / 100 / 250 / 500 / 1,000 Hz | dB/m | Computed | ACU |
| Wall loss, 32 mm tube | 0.11 / 0.16 / 0.25 / 0.36 / 0.51 | dB/m | Computed | ACU |
| Wall loss, 150 mm casing | 0.024 / 0.034 / 0.054 / 0.076 / 0.11 | dB/m | Computed | ACU |
| Excess loss over Kirchhoff | Unquantified, ∝ f | — | [Fay 1940](https://sonicfield.org/library/attenuation-of-sound-in-tubes-1940) | ACU (add 20–50 % margin, assumption) |
| Higher-order mode cutoff | f_c = 1.8412·c/(2πa): 8.0 kHz (25 mm), 6.3 kHz (32 mm), 1.34 kHz (150 mm) | Hz | Computed | ACU band limit |
| Narrow-tube phase-velocity reduction | −0.82 / −0.41 / −0.29 % at 250 / 1k / 2k Hz (25 mm); −0.64 / −0.32 % (32 mm) | % | Computed | ACU dispersion correction |
| Max range by tube ID (Solinst) | 120 / 180 / 300 / 600 m for ½" / ¾" / 1" / 2" | m | [Solinst](https://mail.solinst.com/products/level-measurement-devices/104-sonic-water-level-meter/instructions/sonic-water-level-meter-instructions/sonic-water-level-meter-instructions.php) | ACU validation |
| Max bare-casing diameter (Eno) | 12 | in | [Fondriest/Eno](https://www.fondriest.com/news/eno-scientific-well-sounder-the-power-of-sound-echoes-surface-water-measurements.htm) | ACU |
| Chirp band | 60–250 core; ≤500 for shallow; <1,000 in bare casing | Hz | Inference from attenuation + INMP441 | ACU, firmware |
| Chirp duration | 0.2–1 | s | Inference | ACU |
| Shots averaged | 10–32 | — | Inference | ACU |
| Matched-filter gain | 10·log₁₀(B·T): ~20 dB (400 Hz × 0.25 s), ~26 dB (1 s) | dB | Computed | ACU SNR |
| Averaging gain | 10·log₁₀N: +10 (N = 10), +15 (N = 32) | dB | Computed | ACU SNR |
| Range resolution | c/(2B): 35 cm (500 Hz), 17 cm (1 kHz) | m | Computed | ACU |
| Depth per sample | 10.8 mm (16 kHz), 3.6 mm (48 kHz) | mm | Computed | ACU |
| Round-trip time | 58 / 173 / 578 / 867 ms at 10 / 30 / 100 / 150 m | ms | Computed | ACU record window |
| Record window | ≥ chirp + 0.9 s (~1.5 s) | s | Computed | Firmware, HW memory |
| Pre-shot noise sample | 1 | s | [SWPSC 1363](https://www.swpshortcourse.org/ppdl/1363) | ACU |
| Coupling-lip reflection (25 mm tube) | 0.08–0.15 | — | Computed (area formula) | ACU clutter |
| Casing step 6" → 4.5" reflection | ~0.3 | — | Computed | ACU clutter |
| Riser-top reflection in 150 mm casing | 0.03–0.06 | — | Computed | ACU clutter |
| Pipe joint spacing | 3 (column pipe); 3 or 6 (casing) | m | Assumption (unsourced) | ACU clutter comb |
| Pump acoustic tones | ~48 (rotation), 100 (EM), vane-pass harmonics | Hz | Inference | ACU noise model |
| Post-pump settling time before reading | 30–60 | s | Inference | Firmware gating |
| Resonance mode spacing | Δf = c/(2L): 1.7 Hz (100 m), 1.15 Hz (150 m), 6–17 Hz (10–30 m) | Hz | Computed | ACU cross-check |
| End correction | 0.6a unflanged; Judd: L + 0.8d (open–open), L + 0.4d (closed–open) | m | Standard; [US10787899B2](https://patents.google.com/patent/US10787899) | ACU resonance |
| Commercial accuracy benchmark | ±3 cm, 1 cm resolution | cm | [Solinst](https://solinst.com/products/level-measurement-devices/104-sonic-water-level-meter/datasheet/features-advantages-specs.php); [Eno](https://thesolarstore.com/products/eno-scientific-well-sounder-2010-pro-portable-sonic-water-level-meter) | Validation |
| BoreWise accuracy target | ±0.5–1 % of depth uncalibrated | % | Inference | Validation |
| ESP32 SRAM / I2S / ADC | 520 KB; 2 I2S; 2×12-bit SAR | — | [Espressif](https://documentation.espressif.com/esp32_datasheet_en.pdf) | HW |
| ESP32 Wi-Fi active current | 160–260 (peaks ~240) | mA | [Hubble](https://hubble.com/community/guides/esp32-power-modes-explained-what-the-datasheet-tells-you-and-what-it-doesn-t/) | HW power |
| ESP32 deep sleep | 10 µA chip; 5–20 mA on DevKit | — | [Espressif](https://documentation.espressif.com/esp32_datasheet_en.pdf); [Hubble](https://hubble.com/community/guides/esp32-power-modes-explained-what-the-datasheet-tells-you-and-what-it-doesn-t/) | HW power |
| Energy per reading | ~1 mAh/day at 4 readings | mAh | Computed | HW power |
| INMP441 response, −3 dB points | 60 Hz – 15 kHz | Hz | [Datasheet](https://microcontroller-course.web.cern.ch/Project_Material/resources/INMP441.pdf) | ACU, HW |
| INMP441 SNR / EIN / AOP | 61 dBA / 33 dBA SPL / 120 dB SPL | dB | [Datasheet](https://microcontroller-course.web.cern.ch/Project_Material/resources/INMP441.pdf) | ACU noise floor |
| INMP441 sensitivity | −26 dBFS at 94 dB SPL | dBFS | [Datasheet](https://microcontroller-course.web.cern.ch/Project_Material/resources/INMP441.pdf) | ACU |
| INMP441 sample rate / current | 7.8–50 kHz, 24-bit / 2.2 mA | — | [Datasheet](https://microcontroller-course.web.cern.ch/Project_Material/resources/INMP441.pdf) | HW |
| MAX98357A output | 3.2 W into 4 Ω at 5 V; 8–96 kHz; 2.4 mA quiescent | — | [Analog Devices](https://www.analog.com/en/products/max98357a.html) | ACU source level, HW |
| In-tube source SPL (estimate) | 120–130 | dB SPL | Inference (unverified) | ACU link budget |
| DS18B20 accuracy / resolution | ±0.5 °C (−10…85 °C) / 0.0625 °C in 750 ms | °C | [Datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/DS18B20.pdf) | ACU temperature correction |
| SCT-013-010 | 10 A → 1 V; ±3 % non-linearity | — | [Zbotic](https://zbotic.in/product/sct-013-010-non-invasive-split-core-current-transformer-ac-current-sensor-10a/) | PUMP state, DIAG |
| INA219 | 0–26 V; 0.5 % gain error | — | [TI](https://www.ti.com/product/INA219) | PUMP (DC/solar) |
| JSN-SR04T range | 0.25–4.5 m (tanks/dug wells only) | m | [Components101](https://components101.com/node/1522) | Not used for borewells |
| BOM: ESP32 / INMP441 / MAX98357A / SCT-013 | ₹449 / ₹149 / ~₹469 / ₹394 | ₹ | [Robu](https://robu.in/product/esp32-38pin-development-board-wifibluetooth-ultra-low-power-consumption-dual-core/); [Robu](https://robu.in/product/inmp441-mems-high-precision-omnidirectional-microphone-module-i2s); [price-history](https://price-history.in/product/max98357a-i2s-3w-class-d-amplifier-8KrHoqG5); [Zbotic](https://zbotic.in/product/sct-013-010-non-invasive-split-core-current-transformer-ac-current-sensor-10a/) | Business model |
| Total BOM | ~1,800–2,500 | ₹ | Inference | Business model |
| Basalt flow thickness | 7–45 | m | [CGWB 2013](https://cgwb.gov.in/sites/default/files/2022-10/pune.pdf) | HYD layering |
| Vesicular top thickness | few – 10 | m | [CGWB 2013](https://cgwb.gov.in/sites/default/files/2022-10/pune.pdf) | HYD |
| Weathering depth | up to 20 | m bgl | [CGWB 2013](https://cgwb.gov.in/sites/default/files/2022-10/pune.pdf) | HYD |
| Aquifer-I depth / fracture zones | 9–30 / 5–22 | m bgl | [NAQUIM](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf) | HYD upper layer |
| Aquifer-II depth | 48–175 | m bgl | [NAQUIM](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf) | HYD lower layer, fracture depths |
| Effective recharge depth | 15–20 | m | [IWP/ACWADAM](https://www.indiawaterportal.org/amp/story/agriculture/farm/mapping-punes-aquifers) | SEAS |
| Borewell depth | 50–180 (sim 90–180; Pune rig average 61–91) | m | [NAQUIM](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf); [SANDRP](https://sandrp.in/2016/07/04/groundwater-of-pune-an-over-exploited-and-ungoverned-lifeline/) | HYD, PUMP |
| Casing diameter / length | 150–180 mm / 6–20 m overburden | — | Assumption (anecdotal) | ACU, HYD (r_c) |
| Deep static level, pre-monsoon | 9–70 | m bgl | [NAQUIM](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf) | HYD, SEAS |
| Deep static level, post-monsoon | 1.5–45 | m bgl | [NAQUIM](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf) | HYD, SEAS |
| Shallow level pre / post-monsoon | 0.9–30.35 / 0–25.2 | m bgl | [NAQUIM](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf) | SEAS, ML calibration |
| Seasonal rise (dug wells) | 0.2–12.35 | m | [CGWB 2013](https://cgwb.gov.in/sites/default/files/2022-10/pune.pdf) | SEAS |
| Long-term pre-monsoon decline | 0.012–0.42 | m/yr | [NAQUIM](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf) | SEAS trend |
| Dry-season shallow decline | 0.05–0.3 | m/day | Inference | SEAS |
| Aquifer-II yield / sustain time | ≤2.5 L/s (~150 LPM) / 0.5–3 h | — | [NAQUIM](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf) | HYD, PUMP |
| Aquifer-I yield / sustain time | 10–100 m³/d / 1–3 h | — | [NAQUIM](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf) | HYD |
| Transmissivity (sim) | 5–100 log-uniform (reported 5–55 Aq-I; 18–89 or 25–250 Aq-II) | m²/d | [NAQUIM](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf) + inference | HYD |
| Storativity (deep, effective) | 1e-4 – 1e-3 (reported 1.2e-4 – 6.37e-4) | — | [NAQUIM](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf) | HYD |
| Specific yield (shallow) | 0.01–0.03 (GEC 1–3 %; NAQUIM 0.019–0.028; dug wells 0.017–0.097) | — | [GEC-1997](https://cgwb.gov.in/sites/default/files/inline-files/GEC97.pdf); [NAQUIM](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf) | SEAS |
| Specific capacity (Aq-I) | 1.7–18.9 | lpm/m | [NAQUIM](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf) | DIAG baseline |
| Recharge factor | 0.04–0.10 weathered; 0.10–0.15 vesicular/jointed; tritium 0.04–0.096 | fraction of rain | [GEC-1997](https://cgwb.gov.in/sites/default/files/inline-files/GEC97.pdf); [Rangarajan](https://www.gondwanags.org.in/wp-content/uploads/2022/12/9-Full-Text-Rangarajan-and-Andrade.pdf) | SEAS |
| Annual rainfall (normal) | 468 (Daund) – 4,659 (Khandala); district 540–1,648 (2003–12) | mm | [CGWB 2013](https://cgwb.gov.in/sites/default/files/2022-10/pune.pdf) | SEAS forcing |
| Drainage timescale τ | ~6–7 months (dry-season drainage) | — | Inference from [ACWADAM](https://admin.indiawaterportal.org/sites/default/files/iwp2/Hydrogeological_studies_for_improved_groundwater_management_strategies_in_the_dryland_areas_underlain_by_Deccan_Basalts_Purandar_ACWADAM_2009.pdf) | SEAS |
| Pump: 1 HP | 15–105 LPM over 8–76 m head | — | [Shakedeal](https://marketplace.shakedeal.com/kirloskar-bigflow-1010a-1-hp-100-mm-borewell-water-filled-submersible-pump-dp1) | PUMP |
| Pump: 1.5 HP | 76–135 m head, 21 stages | — | [ShakeDeal](https://marketplace.shakedeal.com/kirloskar-kp4-0321s-1-5hp-oil-filled-borewell-submersible-pump-with-control-panel-dp1) | PUMP |
| Pump rate (sim) | 50–150 | LPM | Inference | PUMP |
| Intake height above bottom | 10–30 | m | Assumption | PUMP, dry-up threshold |
| Pump price (1–3 HP) | 7,000–19,300 | ₹ | [IndiaMART](https://m.indiamart.com/impcat/borewell-pumps.html) | Impact model |
| Dry-run current drop / trip | 20–40 % lower / trip at 80 % | — | [Zbotic](https://zbotic.in/water-pump-dry-run-protection-float-and-current-sensor/) (weak) | DIAG |
| Theis / Cooper-Jacob | s = (Q/4πT)W(u); T = 2.30Q/(4πΔs); valid u ≤ 0.01 | — | [ASBOG](https://open-exam-prep.com/study-guides/asbog/hydrogeology/well-hydraulics-aquifer-testing); [CZU](https://home.czu.cz/storage/575/52485_Recovery.pdf) | HYD, recovery fit |
| Theis recovery | s′ ≈ (Q/4πT)·ln((t′+t_p)/t′) | — | [CZU](https://home.czu.cz/storage/575/52485_Recovery.pdf) | Per-cycle T estimate |
| Step-drawdown | s_w = BQ + CQ² (or CQᵖ); efficiency = BQ/s_w | — | [MDPI Water](https://www.mdpi.com/2073-4441/11/9/1784/htm) | DIAG clogging |
| Walton C thresholds | <1,800 good; 1,800–3,600 mild; >3,600 severe | s²/m⁵ | [MDPI Water](https://www.mdpi.com/2073-4441/11/9/1784/htm) | DIAG |
| Wellbore-storage window | t < 25·r_c²/T (~20 min at r_c 0.075 m, T 10 m²/d) | — | Textbook, unverified; computed | HYD, recovery-fit start time |
| Deep-well legal threshold | 60 | m | [MH GW Act 2009](https://oldiwp.indiawaterportal.org/sites/default/files/iwp2/the_maharashtra_groundwater_development_and_management_act_2009_english_note.pdf) | Dashboard compliance tag |
| Drinking-source exclusion radius | 500 | m | [MH GW Act 2009](https://oldiwp.indiawaterportal.org/sites/default/files/iwp2/the_maharashtra_groundwater_development_and_management_act_2009_english_note.pdf) | Interference scenarios |
| CGWB open wells | 22,965 wells, quarterly, 2013–2022 | — | [India Data Portal](https://ckandev.indiadataportal.com/dataset/groundwater/resource/580a8f6e-3d86-4ca7-ac7d-cd5df12b443c) | ML calibration |
| IMD rainfall grid | 0.25°, daily, since 1901 | — | [imdlib](https://imdlib.readthedocs.io/en/latest/Usage.html) | SEAS forcing, ML features |
| GRACE-FO mascon | 3°, monthly | — | [Earth Engine](https://developers.google.com/earth-engine/datasets/catalog/NASA_GRACE_MASS_GRIDS_V04_MASCON) | Context only |
| Forecast horizons | 7 / 30 / 90 | days | Inference | ML |
| Interval coverage target | 80 (P10–P90) | % | Inference | ML validation |
| Monte Carlo runs per scenario | ≥1,000 society-years | — | Inference | ML validation |
| Telemetry rate | 1 per 15 min → 1.44M msgs/month for 500 wells | — | Computed | AWS |
| Lambda free tier | 1M requests; 400k GB-s | /month | [AWS](https://aws.amazon.com/lambda/pricing/) | AWS |
| Lambda config for agent | 60–120 s; 512 MB – 1 GB | — | Inference | AWS |
| DynamoDB TTL | 30–90 | days | Inference | AWS |
| WhatsApp AWS fee (India utility) | 0.002 + Meta fee | $/msg | [AWS](https://aws.amazon.com/end-user-messaging/pricing) | AWS alerts |
| Private tanker price | 1,500–2,000 | ₹/load | [FPJ](https://www.freepressjournal.in/amp/pune/residents-staged-a-protest-against-tanker-mafia-demand-permanent-water-supply-in-south-pune); [Bridge Chronicle](https://www.thebridgechronicle.com/pune/pune-water-crisis-tanker-costs-housing-society-maintenance-bills-rise-agn97) | Impact model |

## Ranked improvement roadmap

Items are ranked by impact × feasibility × judge appeal. The first block is for the hackathon build; the second is for afterwards.

| Rank | Improvement | Window | Why it matters | Evidence / status |
|---|---|---|---|---|
| 1 | **Per-cycle recovery analytics** (Theis-recovery T, specific-capacity drift, Walton C, residual-drawdown ratchet) in Lambda | Hackathon-now | Turns BoreWise from a level gauge into a diagnostic. Unique among competitors | Equations sourced; Deccan sustainability of 0.5–3 h makes every cycle a test ([NAQUIM](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf)) |
| 2 | **Physics-correct acoustic simulator** (60–250 Hz chirp, c(z), dispersion, clutter comb, pump noise, Fay excess loss) | Hackathon-now | Credibility with technical judges; the corrections above | Computed values in this report |
| 3 | **Probabilistic dry-up date** (P10/P50/P90) with IMD analog-year ensembles, validated against baselines | Hackathon-now | The headline user value: "your borewell will likely fail between 12 and 26 April" | Method from [Wunsch](https://hess.copernicus.org/articles/25/1671/2021/), [Shuai](https://www.mdpi.com/2071-1050/16/2/653/html); metric is novel |
| 4 | **Ward/village "aquifer commons" map** aggregating 500 simulated wells, with a Cedar privacy layer | Hackathon-now | Matches Atal Bhujal disclosure goals; cheap to demo | 3,892 vs 50,000 metered wells ([World Bank](https://projects.worldbank.org/P158119?lang=en)) |
| 5 | **Strands agent in Marathi/Hindi/English** that cites only tool outputs; WhatsApp-template-ready | Hackathon-now | Shows the open-source AWS tool; matches MARVI's finding that local-language delivery is what makes well data usable | [Strands](https://strandsagents.com/docs/user-guide/quickstart/python/index.md); [MARVI](https://www.indiawaterportal.org/amp/story/governance-and-policy/governance/developing-effective-participatory-groundwater-monitoring-program-village-level) |
| 6 | **Current-signature dry-run cut-off and smart scheduling** ("run 40 min, rest 2 h") | Hackathon-now (simulated relay) | Tangible saving of ₹7–19k per pump; beats reactive starters | Pump prices sourced; current thresholds weak |
| 7 | **Layered fault engine** (rules → PI tests → PELT/BOCPD → cross-well coherence) trained on injected faults | Hackathon-now | Separates sensor faults from real events; honest metrics | [Leigh et al.](https://arxiv.org/pdf/1810.13076) |
| 8 | **Bench prototype in a 30–60 m PVC pipe run** (coiled) to measure real dB/m and SNR | Post-hackathon (first) | Closes the largest evidence gap: no published low-cost SNR data | Gap noted |
| 9 | **Dipper-calibrated field pilot** in 5–10 Pune society borewells and Purandar/Baramati farm bores | Post-hackathon | Real accuracy numbers; first borewell dry-up dataset | Gap noted |
| 10 | **Pump current as the primary soft sensor** (no tube install) for a cheaper tier | Post-hackathon | Removes the installation barrier; validate the hypothesis with fleet data | [Ataei 2024](https://doaj.org/article/d91b5a14c8964aec89f4dc9ef8ae09bb) (no accuracy figures) |
| 11 | **Recharge recommendation and before/after verification** for Jalyukt Shivar 2.0 and rooftop harvesting | Post-hackathon | Independent outcome evidence where Jalyukt phase 1 drew CAG criticism | [Deccan Herald](https://www.deccanherald.com/amp/story/india%2Ffadnavis-pet-project-jalyukta-shivar-scheme-to-be-revived-1171526.html) |
| 12 | **DLT-registered SMS, WhatsApp utility templates, Marathi IVR** | Post-hackathon | Production alerting | [AWS DLT docs](https://docs.aws.amazon.com/sms-voice/latest/userguide/registrations-sms-senderid-india.md) |
| 13 | **Open-data export to CGWB/GSDA/Atal Jal format**; tamper-evident logs (S3 Object Lock or hash chain) for water-credit MRV | Post-hackathon | Policy alignment; forward-looking credits story | [ORF](https://orfonline.org/research/trading-blue-gold-a-blueprint-for-water-credit-valuation-in-india); policy nascent |
| 14 | **Hardware upgrades**: 40–50 mm woofer, 32 mm tube, low-Iq power, LoRaWAN/solar farm variant, optional water-quality (EC/nitrate) probe | Post-hackathon | Extends depth range and the farm market | Nitrate >45 mg/L in 18 of 102 deep samples ([NAQUIM](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf)) |
| 15 | **Freedom-to-operate review** against the tapper (US 12,241,770) and Judd patents | Post-hackathon | Commercial risk | [USPTO 12241770](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12241770) |

## Numbers for the pitch

| Claim | Number | Source |
|---|---|---|
| National stress | ~247 BCM/yr extracted, 60.6 % of extractable; 730 of 6,762 units over-exploited (GWRA 2025) | [EA Water](https://www.eawater.com/?p=10539); [C4S](https://c4scourses.in/national-affairs/dynamic-ground-water-resources-of-india-2025-report/) |
| Local stress | 11 of 13 Pune talukas below their 5-year May average (May 2026) | [Pune Pulse](https://www.mypunepulse.com/?p=205378) |
| Why basalt borewells fail fast | Deep Pune aquifer sustains pumping for only 0.5–3 h | [CGWB NAQUIM](https://cgwb.gov.in/sites/default/files/2022-11/pune_f.pdf) |
| Society pain | Private tankers ~₹1,000 → ~₹2,000/load in 2026; ₹7.5 lakh in one season at one society | [Bridge Chronicle](https://www.thebridgechronicle.com/pune/pune-water-crisis-tanker-costs-housing-society-maintenance-bills-rise-agn97) |
| City trend | PMC tanker trips 3.07 → 4.00 lakh (FY22 → FY24) | [Punekar News](https://punekarnews.in/pune-struggles-with-water-scarcity-150-160-tankers-deployed-daily-to-meet-demand-4-03-lakh-rounds-of-tankers-recorded-in-last-fiscal) |
| Farmer pain | >60 % of sampled farmers had a well dry up; ~₹50k per failed borewell (Karnataka) | [IDR](https://idronline.org/can-indian-farmers-adapt-to-water-loss/) |
| Monitoring gap | 3,892 functioning metered wells vs 50,000 target (Atal Bhujal) | [World Bank](https://projects.worldbank.org/P158119?lang=en) |
| Price disruption | ~₹2–2.5k BOM vs $1,700–2,900 imported sonic meters | BOM sources above; [Fondriest](https://fondriest.com/eno-scientific-well-watch-700-water-level-monitor.htm) |
| Payback | One avoided tanker a week ≈ ₹78k–1 lakh/yr saved (computed) | Derived from tanker prices |
| Scale | 21.93 million groundwater irrigation schemes nationally | [News On AIR](https://newsonair.gov.in/maharashtra-becomes-second-highest-state-that-possesses-largest-number-of-minor-irrigation-schemes-after-up) |
| Unregulated drilling | ~5,000+ new bores a year in Pune city, no permission sought | [SANDRP](https://sandrp.in/2016/07/04/groundwater-of-pune-an-over-exploited-and-ungoverned-lifeline/) |
| Cloud cost | Demo fits always-free Lambda/DynamoDB/SNS allowances plus $100–200 new-account credits | [AWS News Blog](https://aws.amazon.com/blogs/aws/aws-free-tier-update-new-customers-can-get-started-and-explore-aws-with-up-to-200-in-credits) |

## Conclusion

The research shifts BoreWise's centre of gravity. The acoustic sensor is not the innovation: echo sounding is a century-old oilfield method, and US sonic meters already reach ±3 cm. The new element is that Deccan basalt's tiny storage turns ordinary society pumping schedules into repeated aquifer tests, and nobody is currently reading them. Per-cycle transmissivity, specific-capacity drift and residual-drawdown ratchets are a far richer signal than a water level alone. They let BoreWise separate a drying aquifer from a clogged well, a worn pump or a neighbour's interference. That is the claim to defend in front of judges, and it holds even with metre-level acoustic accuracy, because slopes and ratios survive a constant calibration offset.

The work is honest only within clear limits. Every high-frequency behaviour is validated in simulation alone. India's open data cannot test daily forecasts. The deep-tube link budget is theoretical until someone sounds a real 60 m pipe. For the pitch, show the corrected physics, the CGWB-calibrated seasonal fit and Monte Carlo dry-up skill against naive baselines, and say plainly what has not been tested. After the hackathon, the bench tube test and a dipper-calibrated Pune pilot come first, because together they produce the field's first open borewell dry-up dataset.
