from setuptools import setup


with open('requirements.txt', 'r') as f:
    requirements = list(f)

setup(
    name='MEAXtd',
    version='0.0.1',
    description="MEA MultiChannel signal analysis",
    author="Aaron Blare",
    author_email='aaron.blare@mail.ru',
    url='https://github.com/AaronBlare/MEAXtd',
    packages=['meaxtd', 'meaxtd.images',
              'meaxtd.tests'],
    package_data={'meaxtd.images': ['*.png']},
    entry_points={
        'console_scripts': [
            'MEAXtd=meaxtd.MEAXtd:main'
        ]
    },
    install_requires=requirements,
    setup_requires=['pytest-runner'],
    tests_require=[
        'pytest', 
        'pytest-cov',
        'pytest-faulthandler',
        'pytest-mock',
        'pytest-qt',
        'pytest-xvfb'
    ],
    zip_safe=False,
    keywords='MEAXtd',
    classifiers=[
        'Programming Language :: Python :: 3.8',
    ],
)
