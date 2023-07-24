from setuptools import setup, find_packages

with open("README.md", "r") as f:
    readme = f.read()

setup(
    name='pyderive3',
    version='0.0.6',
    license='MIT',
    author='Andrew Scott',
    author_email='imgurbot12@gmail.com',
    url='https://github.com/imgurbot12/pyderive',
    description="Python3 Custom Data Class Helpers",
    long_description=readme,
    long_description_content_type="text/markdown",
    python_requires='>=3.8',
    packages=find_packages(),
    install_requires=[
        'typing_extensions>=4.7.1'
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ]
)
