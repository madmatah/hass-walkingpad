# Walkingpad - Home Assistant custom integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)


**This integration will set up the following platforms.**

Platform | Description
-- | --
`sensor` | WalkingPad usage metrics.

## Installation

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
1. If you do not have a `custom_components` directory (folder) there, you need to create it.
1. In the `custom_components` directory (folder) create a new folder called `king_smith`.
1. Download _all_ the files from the `custom_components/king_smith/` directory (folder) in this repository.
1. Place the files you downloaded in the new directory (folder) you created.
1. Restart Home Assistant
1. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "WalkingPad"

## Configuration

To add your WalkingPad device to Home assistant, you must have a bluetooth adapter configured or a bluetooth proxy. This part is documented in the [Bluetooth](https://www.home-assistant.io/integrations/bluetooth/) page of the official Home Assistant documentation.

Before all, ensure that your WalkingPad device is not connected to any device, or it will not be detected.

This custom integration offers 2 configuration modes :

### 1. Automatic bluetooth discovery

Your WalkingPad can be detected automatically by HomeAssistant if its name is recognized by this integration.

In this case, you will see a new discovered device in `Settings > Devices & Services`.

![Disvocered device](./assets/images/discovered-device.png)

Just click and configure and enter a friendly name for your device:

![Automatic config flow](./assets/images/bluetooth-config-flow.png)


That's it!

If your device is not detected, read the [FAQ](#my-walkingpad-device-is-not-detected) and try to use the Manual configuration mode.

### 2. Manual configuration

In `Settings > Devices & Services`, click on `Add integration` and look for `KingSmith WalkingPad` brand.

If you click on it, it will open the manual configuration form:

![Manual configuration](./assets/images/manual-config-flow.png)


Enter your device MAC address in the "device" field and a friendly name in the "name" field.

See the [FAQ](#my-walkingpad-device-is-not-detected) for more details.

<!---->

## FAQ

### My WalkingPad device is not detected

First, make sure no other Bluetooth device is connected to your WalkingPad.

If your device is still not automatically detected by Home Assistant, it's
probably due to the fact that its bluetooth name is unknown. In this
case, you can try to add it manually to Home Assistant.

First, launch a LE scan from your host system (or any other device with a
Bluetooth LE scanner application) to get the MAC address of your WalkingPad
device.

For example, to launch a bluetooth LE scan, on linux, you can run:
```
$> sudo hcitool lescan

LE Scan ...
85:AA:BB:CC:DD:FF KS-ST-A1P
85:AA:BB:CC:EE:FF KS-ST-A1P
```

Note the MAC address (`85:AA:BB:CC:DD:FF` in the previous example), then go to
`Home Assistant` > `Settings` > `Devices and Services` > `Add integration` > Search for `Kingsmith Walkingpad`.

It should open the manual configuration form. Enter the MAC address in the
`Device` form field, any the name of your choice in the `Name` field.
Click on `Submit` and cross your fingers!

If it works, please open an issue here and tell me the Bluetooth name of your
WalkingPad and which model it corresponds to. This will enable me to activate
automatic detection for this model.

## FAQ for developers

### How to enable my bluetooth adapter in the devcontainer ?

I've wasted some time on this problem, so here are a few pointers to get a working development environment.
I assume you're running Linux. Sorry, I don't know how to do this for other operating systems.

Everything is documented on the [Home Assistant Bluetooth page](https://www.home-assistant.io/integrations/bluetooth#additional-details-for-container-core-and-supervised-installs), but here is a summary of the
steps to be performed **on your host system**:

#### 1. Install and enable DBus-Broker

See the [official dbus-broker instructions](https://github.com/bus1/dbus-broker/wiki) for more details. On Ubuntu I had to run the following commands:

```
sudo apt install dbus-broker
sudo systemctl enable dbus-broker.service
sudo systemctl --global enable dbus-broker.service

reboot
````

#### 2. Ensure that bluez is installed

You need to have Bluez >= 5.63 installed on your host system.

#### 3. Ensure that your dbus socket is in /run/dbus

It should be OK in most case, but if your DBus socket is not
in `/run/dbus`, you might have to tweak the .devcontainer.json (see `runArgs`).


#### 4. Profit

Then, you can run the devcontainer and start Home Assistant with `scripts/develop`.

You might have a TLS error on the first run in the logs. Just restart the command and everything should be fine, your bluetooth adapter should be detected by Home Assistant.


## Acknowledgements

This project uses [ph4-walkingpad](https://github.com/ph4r05/ph4-walkingpad) library to control the WalkingPad device. Thanks [@ph4r05](https://github.com/ph4r05)!

This project takes inspiration and code from [@indiefan](https://github.com/indiefan)'s [king smith](https://github.com/indiefan/king_smith) custom integration.

***

[commits-shield]: https://img.shields.io/github/commit-activity/y/madmatah/hass-walkingpad.svg?style=for-the-badge
[commits]: https://github.com/madmatah/hass-walkingpad/commits/main
[license-shield]: https://img.shields.io/github/license/madmatah/hass-walkingpad.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/madmatah/hass-walkingpad.svg?style=for-the-badge
[releases]: https://github.com/madmatah/hass-walkingpad/releases
