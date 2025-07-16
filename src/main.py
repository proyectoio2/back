from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import os

from src.auth.router import router as auth_router
from src.plant_identification.router import router as plant_router
from src.gardens.router import router as garden_router
from src.notes.router import router as notes_router
from src.plants.router  import router as plantas
from src.config import get_settings

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

app = FastAPI(
    title="API de Flora find ",
    description="API para manejo de autenticación, usuarios e identificación de plantas",
    version="1.0.0",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.swagger_ui_init_oauth = {"usePkceWithAuthorizationCodeGrant": True}

app.include_router(auth_router)
app.include_router(plant_router, prefix="/plants", tags=["plantas"])
app.include_router(garden_router, prefix="/gardens", tags=["jardines"])
app.include_router(notes_router, prefix="/plants", tags=["notas de plantas"])
app.include_router(plantas, prefix="/plants", tags=["plantas"])

# Usar ruta absoluta para los templates
templates_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=templates_path)

original_openapi = app.openapi
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = original_openapi()
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Manejador de errores de validación
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        error_dict = {
            "type": error["type"],
            "loc": error["loc"],
            "msg": str(error["msg"]),
            "input": error["input"]
        }
        if "ctx" in error:
            error_dict["ctx"] = {k: str(v) for k, v in error["ctx"].items()}
        errors.append(error_dict)

    return JSONResponse(
        status_code=422,
        content={
            "status_code": 422,
            "message": "Error de validación",
            "detail": errors
        }
    )
