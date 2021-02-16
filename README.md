msvp
====

`msvp` is the Minimum Sous Vide Project, or Product. This program is
intended to control a home-made sous vide bath from a Raspberry Pi.

Hardware
--------
The Pi collects temperature data with a PT1000 platinum RTD sensor
connected to a MAX31865 sensor amplifier. It turns a small immersion
heater on and off with a controllable four-outlet power relay
module. Because the immersion heater does not have any control other
than on and off, we use time proportional output to control the duty
cycle of the heater over a given period, something like slow
PWM. Water movement in the bath is not controlled by this system, and
is left as an exercise for the reader.

Sensor and relay functionality could obviously be different, and if
this project appears to be generally useful, they may be specified in
configuration rather than in code.

Installation
------------
This project uses [poetry](https://python-poetry.org/) to manage
Python dependencies. [Install
it](https://python-poetry.org/docs/#installation), then clone this
directory and install the dependencies:

    git clone https://github.com/bensteinberg/msvp.git
    cd msvp
    poetry install

Usage
-----
You start the system by running `poetry run msvp` with command-line
arguments or environment variables for setpoint, gains for
proportional, integral, and derivative terms, and so on; run `poetry
run msvp --help` to see the options. Environment variables may be set
in a `.env` file. See [sample.env](sample.env) for an example.

The program gets the temperature of the path and uses it to get a new
value from the PID controller every ten seconds, or whatever you set
`--period` to. That value then controls the duty cycle of the heater
for the next ten seconds.

A dynamic graph of the current temperature can be seen at
http://127.0.0.1:5000/ or, if you use the option `--visible`, whatever
IP address your Pi has. You can change the port with `--port`.

Tuning
------
Presently, there is no method for auto-tuning this system.

Development
-----------
To add a new hardware arrangement or simulation, you'll add a class to
`msvp/systems.py`, inheriting from `MsvpSystem`. You'll probably need
to implement at least `temperature`, `_process`, and `_shutdown`.

Because it's frequently more convenient to develop on a PC than a Pi,
this project should have a means of virtualizing or simulating a Pi,
and possibly other boards.

Possible TODOs
--------------
- Notifications: post to Zulip, Pushover, etc., or send email on
  reaching setpoint, or passing a set time after setpoint, or
  diverging too far from setpoint
- Error handling
- Should `_process` be wrapped in a `Strategy` class? or just be a
  function? Maybe a DRYer function.
- Display on sensehat, other
- Testing -- doctests?
- Build chart.js etc. instead of using CDN?
- Add or link to a wiring diagram
- Add an auto-tuning mechanism, or discuss/link to some approaches
- Add Fahrenheit setting?
- Indicate relay state in chart? Or maybe on display.
- Make the convention for output_limits configurable?
