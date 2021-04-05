from pathlib import Path
from dotenv import load_dotenv
import click
import yaml
import logging
import logging.config
from logging.handlers import QueueHandler
from simple_pid import PID
from flask import Flask, Response, render_template
import json
import threading
from queue import Queue
import inspect
import sys
import importlib
import msvp.systems  # noqa


base_dir = Path(__file__).parent.parent
load_dotenv(dotenv_path=base_dir / '.env')


@click.command(context_settings=dict(auto_envvar_prefix="MSVP"))
@click.option('--system',
              type=click.Choice(
                  [x[0] for x in
                   inspect.getmembers(sys.modules['msvp.systems'],
                                      inspect.isclass)
                   if x[0] != 'MsvpSystem'],
                  case_sensitive=True),
              help='system of sensor and heater')
@click.option('--setpoint', type=float,
              help='target temperature in degrees Celsius')
@click.option('--kp', type=float, default=1.0, show_default=True,
              help='proportional gain')
@click.option('--ki', type=float, default=0.0, show_default=True,
              help='integral gain')
@click.option('--kd', type=float, default=0.0, show_default=True,
              help='derivative gain')
@click.option('--period', type=int, default=10, show_default=True,
              help='Period for time proportional output, in seconds')
@click.option('--sensor_pin', type=int, default=5)
@click.option('--relay_pin', type=int, default=6)
@click.option('--logconfig', default='logging.yml')
@click.option('--visible/--no-visible', default=False,
              help='Serve temperature chart on the network')
@click.option('--port/', type=int, default=5000,
              help='Port on which to serve temperature chart')
@click.option('--sensehat/--no-sensehat', default=False,
              help='Enable display on sensehat matrix')
@click.option('--goalpost', default=0.2,
              help='Acceptable distance from setpoint')
@click.option('--speed', default=0.1, show_default=True,
              help='Scroll speed for Sensehat display, in seconds per column')
@click.option('--frequency', default=5,
              help='Scroll frequency for Sensehat display, in seconds')
@click.version_option()
def main(system, setpoint, kp, ki, kd, period, sensor_pin, relay_pin,
         logconfig, visible, port, sensehat, goalpost, speed, frequency):
    '''MSVP is the Minimum Sous Vide Project or Product'''
    with open(base_dir / logconfig) as f:
        logging.config.dictConfig(yaml.safe_load(f.read()))
    logger = logging.getLogger('msvp')

    sysargs = {'period': period}
    if system == 'MsvpRtdRelay':
        sysargs.update({'sensor_pin': sensor_pin, 'relay_pin': relay_pin})
    else:
        sysargs.update({'temp': 50.0})
    System = getattr(importlib.import_module('msvp.systems'), system)
    sv = System(**sysargs)

    # set up queue and log handler for passing messages to the web application
    # (there's a way to set up a QueueHandler with dictConfig, but maybe not
    # when we need to pass the queue into a thread, without a global -- and
    # since this is properly part of how the program works, it seems fine to
    # have it here)
    q = Queue()
    handler = QueueHandler(q)
    handler.setFormatter(logging.Formatter('%(asctime)s|%(message)s'))
    logger.addHandler(handler)

    # start web application; from https://stackoverflow.com/a/49482036
    thread = threading.Thread(target=web_application,
                              args=(q, setpoint, kp, ki, kd, visible, port))
    thread.setDaemon(True)
    thread.start()

    if sensehat:
        try:
            display_thread = threading.Thread(target=sensehat_display,
                                              args=(sv, setpoint, goalpost,
                                                    speed, frequency))
            display_thread.setDaemon(True)
            display_thread.start()
        except ImportError:
            logger.warn('The sense-hat package is not installed.')

    logger.info(f'startup -- setpoint {setpoint}, tuning is {kp}, {ki}, {kd}')

    pid = PID(kp, ki, kd, setpoint=setpoint,
              sample_time=period, output_limits=(0.0, 100.0))
    while True:
        temp = sv.temperature()
        logger.info(f'temperature|{temp}')
        output = pid(temp)
        logger.info(f'output|{output}')
        sv.control(output)


def web_application(q, setpoint, kp, ki, kd, visible, port):
    '''
    Flask application for serving temperature data via server-sent events (SSE)
    and chart via chart.js

    from https://ron.sh/creating-real-time-charts-with-flask/
    '''
    app = Flask(__name__)

    @app.route('/temperature')
    def temperature():
        def read_log():
            while True:
                msg = q.get().getMessage()
                if 'temperature' in msg:
                    try:
                        timestamp, _, temp = msg.split('|')
                        data = {
                            'time': timestamp.split(',')[0],  # no milliseconds
                            'value': round(float(temp), 2)
                        }
                        yield f"data:{json.dumps(data)}\n\n"
                    except ValueError:
                        pass

        return Response(read_log(), mimetype='text/event-stream')

    @app.route('/')
    def chart():
        return render_template('index.html', setpoint=setpoint,
                               kp=kp, ki=ki, kd=kd)

    app.run(host='0.0.0.0' if visible else '127.0.0.1', port=port)


def sensehat_display(sv, setpoint, goalpost, speed, frequency):
    '''Display current temperature and setpoint on a sensehat matrix'''
    import atexit
    from sense_hat import SenseHat
    from time import sleep

    sense = SenseHat()
    atexit.register(lambda: sense.clear())
    red = [255, 0, 0]
    green = [0, 255, 0]
    blue = [0, 0, 255]
    while True:
        temp = sv.temperature()
        if abs(temp - setpoint) < goalpost:
            color = green
        elif temp < setpoint:
            color = blue
        elif temp > setpoint:
            color = red
        sense.show_message(f'{round(temp, 2)}', text_colour=color,
                           scroll_speed=speed)
        sleep(frequency)
