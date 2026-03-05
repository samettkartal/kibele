import os
import shutil
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from inference import process_pdf, load_sbd_model
from legislation_matcher import LegislationMatcher

app = FastAPI()

os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
os.makedirs("uploads", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

try:
    model = load_sbd_model("contract_sbd.pickle")
except Exception as e:
    print(f"Model yüklenirken hata oluştu: {e}")
    model = None

matcher = LegislationMatcher()
matcher.fetchLegislationsFromDb()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/upload")
async def uploadPdf(file: UploadFile = File(...)):
    if model is None:
        return {"error": "SBD Modeli yüklenemedi. Lütfen backend'i kontrol edin."}

    tempPath = os.path.join("uploads", file.filename)
    with open(tempPath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        results = process_pdf(tempPath, model)
        os.remove(tempPath)

        allSentences = []
        for page in results:
            allSentences.extend(page["sentences"])

        legislationInfo = matcher.analyze(allSentences)

        return {"results": results, "legislation_info": legislationInfo}

    except Exception as e:
        if os.path.exists(tempPath):
            os.remove(tempPath)
        return {"error": f"PDF işlenirken bir hata oluştu: {str(e)}"}