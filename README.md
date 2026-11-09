# web-matrix
Web management for a Raspberry Pi RGB Matrix display


## Install

mkdir ~/venv
python -m venv ~/venv/pixels --system-site-packages
sudo apt-get install python-dev-is-python3 python3-pil cython3
source ~/venv/pixels/bin/activate
pip install --upgrade Cython
pip install git+https://github.com/hzeller/rpi-rgb-led-matrix
pip install Flask Pillow APScheduler SQLAlchemy waitress


