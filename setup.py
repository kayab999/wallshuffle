from setuptools import find_packages, setup

setup(
    name='wallshuffle',
    version='1.0.3',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'Pillow>=10.0.0',
        'requests>=2.31.0',
        'pygobject>=3.42.0,<3.51',
    ],
    entry_points={
        'console_scripts': [
            'wallshuffle=wallshuffle.__main__:main',
        ],
    },
    author='Kayab Software',
    description='A wallpaper changer for Linux desktops.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/kayab999/wallshuffle',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
    ],
    python_requires='>=3.10',
    data_files=[
        ('share/applications', ['data/io.github.kayab999.WallShuffle.desktop']),
        ('share/metainfo', ['data/io.github.kayab999.WallShuffle.metainfo.xml']),
        ('share/icons/hicolor/256x256/apps', ['data/io.github.kayab999.WallShuffle.png']),
    ],
)
