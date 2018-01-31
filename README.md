# Earthquake Catcher Network (ECN) Stream Processors

## Development Setup

Requirements:

* Anaconda / Python 3.6
* This guide assumes Windows 64bit

1. Create virtual environment:

        python -m venv venv

2. Activate virtual environment

        venv\Scripts\activate

3. Install requirements

        pip install -r requirements.txt

Environment variables:

    QUEUE_PREFIX=ecn_dev_
    MONGODB_URI=mongodb://localhost/ecn
    AMQP_HOST=localhost
    AMQP_VHOST=/
    AMQP_USER=guest
    AMQP_PASSWORD=guest

## Deployment in Production

1. Install Anaconda with Python 3.6.
   This guide assumes Windows 64bit.

2. Create virtual environment

        python -m venv venv

3. Activate the virtual environment

        venv\Scripts\activate

4. Install dependencies

        pip install -r requirements.txt

5. Edit `setenv.cmd` and ensure configuration (get from Dropbox admin)
6. Run `setenv.cmd`
7. Run `python stationd.py`

### Autostart Script (Windows Server)

    E:
    cd \ecn
    call setenv
    venv\Scripts\python stationd.py

## Protocol Buffers

The protobuf file **must** be in sync with the file used by GeoAssistant Android client.

Compile protobuf to Python library:

    E:\protobuf\bin\protoc -I=. --python_out=ecn/ ecn_mobile.proto
