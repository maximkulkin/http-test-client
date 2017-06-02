from setuptools import setup

setup(
    name='http_test_client',
    version='0.1',
    description='Library to simplify writing HTTP REST service integration tests',
    author='Maxim Kulkin',
    author_email='maxim.kulkin@gmail.com',
    url='https://github.com/maximkulkin/http-test-client',
    license='MIT',
    py_modules=['http_test_client'],
    install_requires=[
        'requests>=2.14',
        'six>=1.10',
    ],
    setup_requires=['pytest-runner'],
    tests_require=[
        'pytest',
        'mockito>=1.0',
        'responses>=0.5',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
)
