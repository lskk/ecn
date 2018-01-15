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

3. Install dependencies

        pip install -r requirements.txt

4. Edit `setenv.cmd` and ensure configuration (get from Dropbox admin)
5. Run `setenv.cmd`
6. Run `python stationd.py`
