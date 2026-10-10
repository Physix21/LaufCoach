"""Installiert den Garmin-Client isoliert außerhalb des Repositorys."""
import subprocess
import venv

from garmin_sync import local_home

environment = local_home() / "venv"
python = environment / "Scripts" / "python.exe"
if not python.exists():
    venv.EnvBuilder(with_pip=True).create(environment)
check = subprocess.run([str(python), "-c", "from importlib.metadata import version; assert version('garminconnect') == '0.3.17'"], capture_output=True)
if check.returncode:
    subprocess.run([str(python), "-m", "pip", "install", "garminconnect==0.3.17"], check=True)
print("Garmin-Umgebung bereit. Anmeldung: garmin_login.bat; Abruf: sync_garmin.bat")
