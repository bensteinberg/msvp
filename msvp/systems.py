import time
import atexit

try:
    import board
    import busio
    import digitalio
    import adafruit_max31865
    import RPi.GPIO as GPIO
except NotImplementedError:
    pass


class MsvpSystem:
    """ Parent class for particular systems """
    def __init__(self, period, **kwargs):
        self.period = period
        self.__dict__.update(kwargs)
        self.last = time.time()
        atexit.register(self._shutdown)

    def temperature(self):
        return None

    def control(self, value):
        ''' run _process '''
        now = time.time()
        self._process(value, now - self.last)
        self.last = now

    def _process(self, value, dt):
        pass

    def _shutdown(self):
        pass


class MsvpMockVariable(MsvpSystem):
    """
    simulation of a boiler with a continuously-variable control,
    from the simple-pid example
    """
    def temperature(self):
        return self.temp

    def _process(self, value, dt):

        value = value / 100.0

        if value > 0.0:
            self.temp += 1 * value * dt

        self.temp -= 0.02 * dt

        time.sleep(self.period)


class MsvpMockRelay(MsvpSystem):
    """
    simulation of a boiler with an on-off control, modulated via
    time proportional output
    """
    def __init__(self, period, **kwargs):
        super().__init__(period, **kwargs)
        self.relay = self.last_relay = 'off'

    def temperature(self):
        return self.temp

    def _process(self, value, dt):
        duty_cycle = value / 100.0
        on_time = duty_cycle * self.period
        # maybe use last_duty_cycle
        if duty_cycle > 0.0 and self.last_relay == 'off':
            self.relay = 'on'
        time.sleep(on_time)
        self.temp += 1 * duty_cycle * dt
        if 0.0 < duty_cycle < 1.0:
            self.relay = 'off'
        time.sleep(self.period - on_time)
        self.temp -= 0.02 * dt
        self.last_relay = self.relay


class MsvpRtdRelay(MsvpSystem):

    def __init__(self, period, **kwargs):
        super().__init__(period, **kwargs)
        self.sensor = self._initialize_hardware()

    def _process(self, value, dt):
        duty_cycle = value / 100.0
        on_time = duty_cycle * self.period
        if duty_cycle > 0.0:
            self.relay('on')
            time.sleep(on_time)
        if 0.0 < duty_cycle < 1.0:
            self.relay('off')
        time.sleep(self.period - on_time)

    def temperature(self):
        return self.sensor.temperature

    def _initialize_hardware(self):
        '''Set up the sensor and relay'''
        spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
        cs = digitalio.DigitalInOut(getattr(board, f'D{self.sensor_pin}'))
        sensor = adafruit_max31865.MAX31865(spi, cs, wires=3,
                                            rtd_nominal=1000.0,
                                            ref_resistor=4300.0)

        # set up relay
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.relay_pin, GPIO.OUT)

        return sensor

    def relay(self, state):
        '''Turn relay on or off'''
        GPIO.output(self.relay_pin, True if state == 'on' else False)

    def _shutdown(self):
        '''Turn relay off'''
        self.relay('off')
