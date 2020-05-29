from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="b3_ir_calc", # Replace with your own username
    version="0.0.2",
    author="Koji",
    author_email="robson.koji@gmail.com",
    description="B3 income tax calculator",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitlab.com/robson.koji/b3_ir_calc",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Just use",
        #"Operating System :: OS Independent",
    ],
    python_requires='>=3.6',

    test_suite = 'tests',

)
