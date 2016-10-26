from math import isclose
from collections import namedtuple
import sdl2
import sdl2.ext

ButtonEvent = namedtuple('ButtonEvent', ['time', 'state'])
AxisEvent = namedtuple('AxisEvent', ['time', 'state'])
HatEvent = namedtuple('HatEvent', ['time', 'state'])
DeviceEvent = namedtuple('DeviceEvent', ['number'])


class AbstractState(object):
    def __init__(self):
        pass

    def __str__(self):
        return '<State {}>'.format(self.value())

    def __repr__(self):
        return str(self)

    def __call__(self):
        value = self.value()
        self.clear()
        return value

    def zero(self, value):
        pass

    def process_event(self, event):
        raise NotImplemented()

    def value(self):
        raise NotImplemented()

    def clear(self):
        pass


class CurrentButtonState(AbstractState):
    def __init__(self):
        self._value = False

    def process_event(self, event):
        self._value = event.state

    def value(self):
        return self._value


class ToggleButtonState(AbstractState):
    def __init__(self):
        self._value = False

    def process_event(self, event):
        self._value ^= event.state

    def value(self):
        return self._value

    def clear(self):
        self._value = False


class ClickedButtonState(AbstractState):
    def __init__(self):
        self._value = False

    def process_event(self, event):
        self._value |= event.state

    def value(self):
        return self._value

    def clear(self):
        self._value = False


class DecimalAxisState(AbstractState):
    VAR_MAX = 32767
    VAR_MIN = -32768

    def __init__(self):
        self.zero_value = 0
        self.__value = 0

    def process_event(self, event: AxisEvent):
        self.__value = event.state

    def value(self):
        normal = self.__value - self.zero_value
        if self.__value > 0:
            normal = normal / (self.VAR_MAX - self.zero_value)
        else:
            normal = -normal / (self.VAR_MIN - self.zero_value)

        if isclose(normal, 0, abs_tol=0.03):
            return 0
        return normal

    def zero(self, current):
        self.zero_value = current


class DecimalTriggerState(AbstractState):
    VAR_MAX = 32767
    VAR_MIN = -32768

    def __init__(self):
        self.zero_value = 0
        self.__value = 0

    def process_event(self, event: AxisEvent):
        self.__value = event.state

    def value(self):
        return (self.__value - self.VAR_MIN) / (self.VAR_MAX - self.VAR_MIN)


class PulledTriggerState(DecimalTriggerState):
    def __init__(self):
        super().__init__()
        self._value = False

    def process_event(self, event):
        super().process_event(event)
        self._value |= super().value() > .9

    def value(self):
        return self._value

    def clear(self):
        self._value = False


class HatState(AbstractState):
    def __init__(self):
        self.__value = 0

    def process_event(self, event: HatEvent):
        self.__value = event.state

    def value(self):
        value = self.__value
        if value & 1:
            result = 'u'
        elif value & 4:
            result = 'd'
        else:
            result = ' '

        if value & 2:
            result += 'r'
        elif value & 8:
            result += 'l'
        else:
            result += ' '

        return result


class HatSwitchesState(HatState):
    def __init__(self):
        super().__init__()
        self.__value = set()

    def process_event(self, event):
        super().process_event(event)
        self.__value.add(super().value().strip())

    def value(self):
        return tuple(self.__value)

    def clear(self):
        self.__value.clear()


class Controller(object):
    '''
    - Does not handle many controllers
    '''
    def __init__(self, number: int):
        self.number = number
        self.device = sdl2.joystick.SDL_JoystickOpen(number)
        assert sdl2.haptic.SDL_JoystickIsHaptic(self.device)
        self.haptic = sdl2.haptic.SDL_HapticOpenFromJoystick(self.device)
        sdl2.haptic.SDL_HapticRumbleInit(self.haptic)

        self.a = CurrentButtonState()
        self.b = CurrentButtonState()
        self.x = CurrentButtonState()
        self.y = CurrentButtonState()
        self.left_bumper = CurrentButtonState()
        self.right_bumper = CurrentButtonState()
        self.start_button = CurrentButtonState()
        self.select_button = CurrentButtonState()
        self.center_button = CurrentButtonState()
        self.left_stick_button = CurrentButtonState()
        self.right_stick_button = CurrentButtonState()

        self.left_x = DecimalAxisState()
        self.left_y = DecimalAxisState()
        self.left_trigger = PulledTriggerState()
        self.right_x = DecimalAxisState()
        self.right_y = DecimalAxisState()
        self.right_trigger = PulledTriggerState()

        self.hat = HatSwitchesState()

        self.zero()

    @classmethod
    def init(cls):
        sdl2.SDL_Init(sdl2.SDL_INIT_JOYSTICK | sdl2.SDL_INIT_HAPTIC)

    def zero(self):
        for i, axis in enumerate(self._axises()):
            axis.zero(sdl2.joystick.SDL_JoystickGetAxis(self.device, i))

    def _axises(self):
        axis_array = (
            self.left_x, self.left_y, self.left_trigger,
            self.right_x, self.right_y, self.right_trigger)
        return axis_array

    def get_name(self):
        return sdl2.joystick.SDL_JoystickName(self.device)

    def update(self):
        sdl2.SDL_JoystickUpdate()

        button_array = (
            self.a, self.b, self.x, self.y,
            self.left_bumper, self.right_bumper,
            self.start_button, self.select_button, self.center_button,
            self.left_stick_button, self.right_stick_button)

        axis_array = self._axises()

        for event in sdl2.ext.get_events():
            if event.type == sdl2.SDL_JOYBUTTONUP:
                button_array[event.jbutton.button].process_event(
                    ButtonEvent(event.jbutton.timestamp, False))
            elif event.type == sdl2.SDL_JOYBUTTONDOWN:
                button_array[event.jbutton.button].process_event(
                    ButtonEvent(event.jbutton.timestamp, True))
            elif event.type == sdl2.SDL_JOYAXISMOTION:
                axis_array[event.jaxis.axis].process_event(
                    AxisEvent(event.jaxis.timestamp, event.jaxis.value))
            elif event.type == sdl2.SDL_JOYHATMOTION:
                self.hat.process_event(HatEvent(event.jhat.timestamp, event.jhat.value))

            # elif event.type == sdl2.SDL_JOYDEVICEADDED:
            # elif event.type == sdl2.SDL_JOYDEVICEREMOVED:
