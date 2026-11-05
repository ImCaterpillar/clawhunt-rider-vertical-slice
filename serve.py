# -*- coding: utf-8 -*-
import os
from pathlib import Path
import uvicorn
from fastapi.staticfiles import StaticFiles
from api_app import app

ROOT=Path(__file__).resolve().parent
app.mount('/',StaticFiles(directory=str(ROOT),html=True),name='ui')
if __name__=='__main__':
    uvicorn.run(app,host='127.0.0.1',port=8765)
