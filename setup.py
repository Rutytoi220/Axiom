from setuptools import setup, find_packages

setup(
    name="axiom-core",
    version="1.0.0",
    description="A Local-First AI Operating System for Linux.",
    author="AXIOM Contributors",
    author_email="admin@axiom.local",
    packages=find_packages(include=["axiom*"]),
    install_requires=[
        "PySide6>=6.0",
        "aiosqlite>=0.20.0",
        "chromadb>=0.4.0",
        "faster-whisper>=1.0.0",
        "openwakeword>=0.4.0",
        "pyttsx3>=2.90",
        "litellm>=1.93.0",
        "pydantic>=2.0",
        "sounddevice>=0.4.0"
    ],
    entry_points={
        "console_scripts": [
            "axiom=axiom.gui.app:main",
            "axiomd=main:daemon_entry_point",
        ],
    },
    python_requires=">=3.9",
)
