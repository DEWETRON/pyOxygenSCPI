"""
Setup script for pyOxygenSCPI

@author: Matthias Straka <matthias.straka@dewetron.com>
"""
import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pyOxygenSCPI",
    version="0.0.1",
    author="Matthias Straka",
    author_email="matthias.straka@dewetron.com",
    description="Python library for remote controlling Dewetron Oxygen via the SCPI interface",
    license="MIT",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/DEWETRON/pyOxygenSCPI",
    keywords='Measurement, Signal processing, Storage',
    project_urls={
        "Bug Tracker": "https://github.com/DEWETRON/pyOxygenSCPI/issues",
        "Source Code": "https://github.com/DEWETRON/pyOxygenSCPI",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    platforms=["Windows", "Linux"],
    packages=["pyOxygenSCPI"],
    package_dir={"pyOxygenSCPI": "pyOxygenSCPI"},
    install_requires=[],
    python_requires=">=3.7",
)
