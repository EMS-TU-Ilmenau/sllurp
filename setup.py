from setuptools import setup, find_packages
import os
import codecs

here = os.path.abspath(os.path.dirname(__file__))

def read(filename):
    """
    Get the long description from a file.
    """
    fname = os.path.join(here, filename)
    with codecs.open(fname, encoding='utf-8') as f:
        return f.read()

setup(
    name='sllurp',
    version='0.3.11',
    description='RFID reader control library',
    long_description=read('README.rst'),
    author='Ben Ransford',
    author_email='ben@ransford.org',
    url='https://github.com/ransford/sllurp',
    license='GPLv3',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 2.7',
    ],
    keywords='llrp rfid reader',
    packages=find_packages(),
)
