###### setup.py package setup script for pyCalTopo ######

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="sartopo_python",
    version="1.1.2",
    author="Tom Grundy",
    author_email="nccaves@yahoo.com",
    description="Python interface to unofficial SARTopo API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ncssar/sartopo_python",
    packages=setuptools.find_packages(),
    download_url="https://github.com/ncssar/sartopo_python/archive/1.1.2.tar.gz",
    install_requires=[
        'requests',
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
    ],
)
