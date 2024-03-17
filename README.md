# PyBlox

NetsBlox is a block-based programming environment which has a focus on distributed computing and internet connectivity.
One of the core features of NetsBlox are _remote procedure calls_ (RPCs), which connect to the NetsBlox server and provide access to online resources such as databases, GoogleMaps, online translation, wireless robotics, mobile phone sensors/control, and more.

PyBlox is an interface for accessing all [NetsBlox](https://netsblox.org/) services from within python.
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

# Graphical Environment

PyBlox, while useful on its own for accessing NetsBlox services, has a side goal of helping transition students from block-based languages like NetsBlox and Snap! into textual languages like python.
Because of this, PyBlox comes with a power graphical environment that supports most of the same features as NetsBlox/Snap!, as well as an IDE for creating python projects in a way that is still structured like a NetsBlox/Snap! project in both appearance and concurrency model (closest approximation).

These features are only activated when explicitly called, leaving the default behavior as a normal python package for accessing NetsBlox services.

To launch the IDE, you can simply run PyBlox (`netsblox`) as a module:

```sh
python -m netsblox
```

# Installation

PyBlox is available as a pip package called `netsblox` (keep in mind that PyBlox is a python3 package, so you may need to use `pip3` if your `pip` still points to the python2 version).

```sh
pip install netsblox
```

If you run into installation issues with the `nb2pb` dependency, follow the instruction [here](https://github.com/dragazo/nb2pb).
It is possible that there is not a wheel build for your platform and/or python version, which means that it must be compiled from source.
This requires installing [`cargo`](https://doc.rust-lang.org/cargo/getting-started/installation.html), after which you can reattempt installing `netsblox`.
If this solves your problem, feel free to [submit an issue](https://github.com/dragazo/PyBlox/issues/new) including your operating system and processor architecture.

The following additional setup is required, depending on your operating system.

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
Note that this conversion is only performed by the static service wrappers like `Client.chart.default_options()`, and not for the dynamic invocation method: `Client.call('Chart', 'defaultOptions')`.

# Naming Conventions

The python names for services, functions, and input parameters are identical to those in the official [NetsBlox documentation](https://editor.netsblox.org/docs/index.html), except that they are converted into snake case to by more pythonic.
Of course, any modern editor will have some form of intellisense built in, so in practice this is a non-issue.
