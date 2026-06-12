from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from auth import verify_password, create_access_token, hash_password, get_current_user
from models.usuario import Usuario, RolUsuario

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="templates")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(Usuario).filter(Usuario.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Usuario o contraseña incorrectos"},
            status_code=401,
        )
    token = create_access_token({"sub": user.username})
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie("access_token", token, httponly=True, max_age=60 * 60 * 24 * 7)
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie("access_token")
    return response


@router.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request, db: Session = Depends(get_db)):
    if db.query(Usuario).count() > 0:
        return RedirectResponse(url="/auth/login")
    return templates.TemplateResponse("setup.html", {"request": request})


@router.post("/setup")
def setup(
    nombre: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    whatsapp: str = Form(default=""),
    db: Session = Depends(get_db),
):
    if db.query(Usuario).count() > 0:
        raise HTTPException(status_code=400, detail="Setup ya completado")
    user = Usuario(
        nombre=nombre,
        username=username,
        password_hash=hash_password(password),
        rol=RolUsuario.admin,
        whatsapp=whatsapp or None,
    )
    db.add(user)
    db.commit()
    return RedirectResponse(url="/auth/login", status_code=302)
