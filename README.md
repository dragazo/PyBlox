# NetsBlox-python

NetsBlox-python is a wrapper for accessing [NetsBlox](https://netsblox.org/) services from within python.
You can import this package in any python program that has internet access and begin calling RPCs and sending/receiving messages.

# Installation

NetsBlox-python is available as a pip package called `netsblox`, so you can install it with the following:

```sh
pip install netsblox
```

Keep in mind that NetsBlox-python is a python3 package, so you may need to use `pip3` if your `pip` still points to the python2 version.

# Example Usage

Here's a short example to see how you can access the [`MaunaLoaCO2Data`](https://editor.netsblox.org/docs/services/MaunaLoaCO2Data/index.html) service from python.

```py
import netsblox

client = netsblox.Client() # create a client to access NetsBlox
co2 = client.get_service('MaunaLoaCO2Data')
data = co2.get_co2_trend(2000, 2010)
print(data)
```

# Naming Conventions

As seen in the example above, services are referenced by name as a string.
These are identical to the service names shown in the [NetsBlox services documentation](https://editor.netsblox.org/docs/index.html).
The RPCs (functions) in each service, however, are methods on the service object.
NetsBlox uses `cammelCase` names, while python uses `snake_case`.
If you see a function in the NetsBlox documentation like `performSomeAction`, you just need to write the equivalent snake case name `perform_some_action`.