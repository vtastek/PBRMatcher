Create a Virtual Environment:
```
python -m venv texture_tool_env
texture_tool_env\Scripts\activate
pip install pillow tkinter
```
```
texture_tool/
├── main.py         # Main Python script
├── textures/       # Folder containing texture files
├── db.json         # JSON file to store tags and progress
```

Load textures from the textures/ folder and check the db.json file for progress.\
If db.json doesn't exist, create it.
