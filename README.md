# NetsBlox-python

NetsBlox is a block-based programming environment which has a focus on distributed computing and internet connectivity.
One of the core features of NetsBlox are _remote procedure calls_ (RPCs), which connect to the NetsBlox server and provide access to online resources such as databases, GoogleMaps, online translation, wireless robotics, mobile phone sensors/control, and more.

NetsBlox-python is an interface for accessing all [NetsBlox](https://netsblox.org/) services from within python.
You can import this package in any python program that has internet access and begin calling RPCs and sending/receiving messages!

For more information about NetsBlox and the available services, see the official [NetsBlox Documentation](https://editor.netsblox.org/docs/index.html).

# Example Usage

Here's a short example to see how you can access the [`MaunaLoaCO2Data`](https://editor.netsblox.org/docs/services/MaunaLoaCO2Data/index.html) service from python.

```py
import netsblox
nb = netsblox.Client() # create a client to access NetsBlox

data = nb.mauna_loa_co2_data.get_co2_trend(2000, 2010)
print(data)
```

# Turtle IDE

NetsBlox-python, while useful on its own for accessing NetsBlox services, has a side goal of helping transition students from block-based languages like NetsBlox and Snap! into textual languages like python.
Because of this, NetsBlox-python comes with a custom wrapper for the popular `turtle` environment, as well as an IDE for creating python projects in a way that is still structured like a NetsBlox/Snap! project in both appearnance and concurrency model (closest approximation).

These features are only activated when explicitly called, leaving the default behavior as a normal python package for accessing NetsBlox services.

To launch the IDE, you can simply run the NetsBlox-python pypi package as a module:

```sh
python -m netsblox
```

# Installation

NetsBlox-python is available as a pip package called `netsblox` (keep in mind that NetsBlox-python is a python3 package, so you may need to use `pip3` if your `pip` still points to the python2 version).

```sh
pip install netsblox
```

This will pull all of the core python dependencies for using NetsBlox services, but some additional setup is needed for the turtle environment and IDE to work.

## Windows

_No additional install dependencies_

## Mac

```sh
brew install python-tk
```

## Linux

```sh
sudo apt install python3-pil python3-pil.imagetk
sudo apt install idle3
```

# Structured Data

Due to the limited type primitives in Snap!, one NetsBlox typing convention is "structured data", which is really just a list of lists (pairs) denoting (unique string) keys and values.
In the python interface, this is replaced by `dict` for both input and return value.
The python interface will automatically convert input `dict` values into lists of lists, and convert lists of lists return values into `dict` (where appropriate).

# Naming Conventions

The python names for services, functions, and input parameters are identical to those in the official [NetsBlox documentation](https://editor.netsblox.org/docs/index.html), except that they are converted into snake case to by more pythonic.
Of course, any modern editor will have some form of intellisense built in, so in practice this is a non-issue.
