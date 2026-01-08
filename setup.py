from setuptools import setup, find_packages

setup(
    name='wallshuffle',
    version='1.0.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'Pillow>=10.0.0',
        'requests>=2.31.0',
        'pygobject>=3.42.0',
    ],
    entry_points={
        'console_scripts': [
            'wallshuffle=wallshuffle.__main__:main',
        ],
    },
    author='Carlos',
    description='A wallpaper changer for Linux desktops.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/carlos/wallshuffle',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
    ],
    python_requires='>=3.8',
)
