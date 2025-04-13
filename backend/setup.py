from setuptools import setup, find_packages

setup(
    name="trustit-backend",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "uvicorn",
        "python-dotenv",
        "pydantic",
        "requests",
        "aiohttp",
        "python-multipart",
    ],
) 