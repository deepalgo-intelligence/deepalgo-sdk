from setuptools import setup, find_packages

setup(
    name="deepalgo-sovereign",
    version="0.2.0",
    author="DeepAlgo Intelligence",
    author_email="support@deepalgo.co.uk",
    description="Python SDK for the DeepAlgo Sovereign AI Regime API",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/DICAP1/deepalgo-sdk",
    packages=find_packages(include=['deepalgo_sovereign', 'deepalgo_sovereign.*']),
    install_requires=[
        "requests",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Office/Business :: Financial :: Investment",
    ],
    python_requires='>=3.8',
)