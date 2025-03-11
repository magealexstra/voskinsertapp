from setuptools import setup, find_packages

setup(
    name="vosk-dictation",
    version="0.1.0",
    description="A standalone dictation tool using VOSK for speech recognition",
    author="MageAlexstra",
    packages=find_packages(),
    install_requires=[
        "vosk==0.3.45",
        "sounddevice==0.4.6",
        "python-dotenv==1.0.0"
    ],
    entry_points={
        'console_scripts': [
            'vosk-dictation=vosk_dictation.dictation:main',
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires=">=3.6",
)
