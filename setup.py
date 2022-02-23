from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in payment_gateway_payfast/__init__.py
from payment_gateway_payfast import __version__ as version

setup(
	name="payment_gateway_payfast",
	version=version,
	description="Payfast Payment Gateway Intergration",
	author="Alberto Gutierrez",
	author_email="albertogutierrez826@gmail.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
