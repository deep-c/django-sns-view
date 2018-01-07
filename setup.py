from setuptools import setup

import os
import textwrap

import django_sns_view as app

ROOT = os.path.abspath(os.path.dirname(__file__))

setup(
    name='django-sns-view',
    version=app.__version__,
    author='Deeptesh Chagan',
    packages=[
        'django_sns_view', 'django_sns_view.tests'],
    url='https://github.com/deep-c/django_sns_view',
    description=(
        "A Django view that can be subscribed to Amazon SNS"
    ),
    long_description=textwrap.dedent(
        open(os.path.join(ROOT, 'README.rst')).read()),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'Django>=1.7',
        'pyopenssl>=0.13.1',
        'pem>=16.0.0',
        'requests>=2.18.0',
    ],
    keywords="aws sns django",
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Internet :: WWW/HTTP']
)