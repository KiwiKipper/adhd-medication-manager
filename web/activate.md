1: Create the venv: 
python -m venv web/backend/venv
py -3.13 -m venv venv


2: Activate it:
source web/backend/venv/Scripts/activate

2.1: Your prompt should now show (venv). If PowerShell blocks the script with an execution-policy error, run this once (per user, not admin):
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

3: Install requirements.txt 
pip install -r web\backend\requirements.txt



