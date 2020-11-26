#!/usr/bin/python

import os
import sys
import signal
import logging
import logging.handlers
import dbus
import dbus.service
import dbus.mainloop.glib
try:
    import gobject
except ImportError:
    from gi.repository import GLib
import re
import subprocess


LOG_LEVEL = logging.INFO
#LOG_LEVEL = logging.DEBUG
LOG_FILE = "/dev/log"
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
BLUEZ_DEV = "org.bluez.MediaTransport1"

def device_property_changed_cb(property_name, value, path, interface, device_path):
	global bus
	if property_name != BLUEZ_DEV:
		return

	device = dbus.Interface(bus.get_object("org.bluez", device_path), "org.freedesktop.DBus.Properties")
	properties = device.GetAll(BLUEZ_DEV)

	logger.info("Getting dbus interface for device: %s interface: %s property_name: %s" % (device_path, interface, property_name))

	vol = properties["Volume"]
	volume_percentage = format(vol / 1.27, '.2f')
	
	set_device_volume(float(volume_percentage), properties["Device"])

def set_device_volume(vol, devName):
	args = ['pacmd', 'list-sources']
	r = subprocess.run(args, stdout=subprocess.PIPE)
	res = f'{r.stdout}'
	#Get the device index for devName from the output
	m = re.findall(r'index: (\d+)', res[:res.find(f'bluez.path = "{devName}"')+1])
	if not m:
		return
	devIndex = m[-1]
	setVolume = int(65535 * vol / 100)
	args = ['pacmd', 'set-source-volume', devIndex, f'{setVolume}']
	subprocess.run(args)

def shutdown(signum, frame):
	mainloop.quit()

if __name__ == "__main__":
	# shut down on a TERM signal
	signal.signal(signal.SIGTERM, shutdown)

	# start logging
	logger = logging.getLogger("volume-watcher")
	logger.setLevel(LOG_LEVEL)
	logger.addHandler(logging.handlers.SysLogHandler(address = "/dev/log"))
	logger.info("Starting to monitor for AVRCP Volume changes")

	# Get the system bus
	try:
		dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
		bus = dbus.SystemBus()
	except Exception as ex:
		logger.error("Unable to get the system dbus: '{0}'. Exiting. Is dbus running?".format(ex.message))
		sys.exit(1)

	# listen for signals on the Bluez bus
	bus.add_signal_receiver(device_property_changed_cb, bus_name="org.bluez", signal_name="PropertiesChanged", path_keyword="device_path", interface_keyword="interface")

	try:
		mainloop = GLib.MainLoop()
		mainloop.run()
	except KeyboardInterrupt:
		pass
	except:
		logger.error("Unable to run the gobject main loop")
		sys.exit(1)

	logger.info("Shutting down")
	sys.exit(0)
