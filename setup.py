from setuptools import find_packages, setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='anydex',
    author='Tribler',
    description='The Universal Decentralized Exchange',
    long_description=long_description,
    long_description_content_type='text/markdown',
    version='0.1.0',
    url='https://github.com/Tribler/anydex-core',
    package_dir={'': 'anydex'},
    packages=find_packages("anydex", exclude=["ipv8"]),
    py_modules=[],
    install_requires=[
        "autobahn",
        "bitcoinlib==0.4.14",
        "cryptography",
        "libnacl",
        "netifaces",
        "aiohttp",
        "pyOpenSSL",
        "requests",
        "web3",
        "sqlalchemy",
        "monero",
        "responses",
        "stellar-sdk"

    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Scientific/Engineering",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Distributed Computing",
    ]
)
