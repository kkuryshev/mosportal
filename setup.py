from distutils.core import setup

setup(
    name='mosportal',
    packages=['mosportal'],
    version='0.1.5',
    license='MIT',
    description='api для работы с порталом москвы',
    author='@kkuryshev',
    author_email='kkurishev@gmail.com',
    url='https://github.com/kkuryshev/mosportal',
    keywords=['mosportal'],
    install_requires=[
        'requests'
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
)
