from fastapi import FastAPI, Depends, HTTPException, Request, Form, status, Response, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, func
from contextlib import asynccontextmanager
from typing import Optional
import shutil
import os

from database.session import create_db_and_tables, get_session
from database.models import Product, Sale, User, Settings, Client
from services.stock_service import StockService
from services.auth_service import AuthService

# Setup
stock_service = StockService(static_dir="static/barcodes")
templates = Jinja2Templates(directory="templates")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup
    create_db_and_tables()
    # Seed Data
    session = next(get_session())
    AuthService.create_default_user_and_settings(session)
    yield

app = FastAPI(title="NexPos System", lifespan=lifespan)

# Mount Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Dependencies ---

def get_current_user(request: Request, session: Session = Depends(get_session)) -> Optional[User]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return session.get(User, user_id)

def require_auth(request: Request, user: Optional[User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/login"})
    return user

def get_settings(session: Session = Depends(get_session)) -> Settings:
    # Always return the first settings row
    return session.exec(select(Settings)).first()

# --- Auth Routes ---

from starlette.middleware.sessions import SessionMiddleware
app.add_middleware(SessionMiddleware, secret_key="super-secret-nexpos-key")

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, settings: Settings = Depends(get_settings)):
    return templates.TemplateResponse("login.html", {"request": request, "settings": settings})

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), session: Session = Depends(get_session), settings: Settings = Depends(get_settings)):
    user = session.exec(select(User).where(User.username == username)).first()
    if not user or not AuthService.verify_password(password, user.password_hash):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Credenciales inválidas", "settings": settings})
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=302)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)

# --- App Routes (Protected) ---

@app.get("/", response_class=HTMLResponse)
def get_dashboard(request: Request, user: User = Depends(require_auth), settings: Settings = Depends(get_settings), session: Session = Depends(get_session)):
    total_products = session.exec(select(func.count(Product.id))).one()
    low_stock = session.exec(select(func.count(Product.id)).where(Product.stock_quantity < Product.min_stock_level)).one()
    recent_sales = session.exec(select(Sale).order_by(Sale.timestamp.desc()).limit(5)).all()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "active_page": "home", "settings": settings, "user": user,
        "total_products": total_products, "low_stock": low_stock, "recent_sales": recent_sales
    })

@app.get("/pos", response_class=HTMLResponse)
def get_pos(request: Request, user: User = Depends(require_auth), settings: Settings = Depends(get_settings)):
    return templates.TemplateResponse("pos.html", {"request": request, "active_page": "pos", "settings": settings, "user": user})

@app.get("/products", response_class=HTMLResponse)
def get_products_page(request: Request, user: User = Depends(require_auth), settings: Settings = Depends(get_settings), session: Session = Depends(get_session)):
    products = session.exec(select(Product)).all()
    return templates.TemplateResponse("products.html", {"request": request, "active_page": "products", "settings": settings, "user": user, "products": products})

@app.get("/clients", response_class=HTMLResponse)
def get_clients_page(request: Request, user: User = Depends(require_auth), settings: Settings = Depends(get_settings), session: Session = Depends(get_session)):
    clients = session.exec(select(Client)).all()
    return templates.TemplateResponse("clients.html", {"request": request, "active_page": "clients", "settings": settings, "user": user, "clients": clients})

@app.get("/sales", response_class=HTMLResponse)
def get_sales_page(request: Request, user: User = Depends(require_auth), settings: Settings = Depends(get_settings), session: Session = Depends(get_session)):
    # Fetch sales with items eagerly loaded if possible, otherwise lazy loading might trigger n+1 queries.
    # For SQLModel with relations, ideally we'd use .options(selectinload(Sale.items)) but let's stick to simple first.
    sales = session.exec(select(Sale).order_by(Sale.timestamp.desc()).limit(50)).all()
    return templates.TemplateResponse("sales.html", {"request": request, "active_page": "sales", "settings": settings, "user": user, "sales": sales})

@app.get("/settings", response_class=HTMLResponse)
def get_settings_page(request: Request, user: User = Depends(require_auth), settings: Settings = Depends(get_settings)):
    return templates.TemplateResponse("settings.html", {"request": request, "active_page": "settings", "settings": settings, "user": user})

@app.post("/settings")
async def update_settings(request: Request, company_name: str = Form(...), logo_file: Optional[UploadFile] = File(None), settings: Settings = Depends(get_settings), session: Session = Depends(get_session), user: User = Depends(require_auth)):
    settings.company_name = company_name
    if logo_file and logo_file.filename:
        file_location = f"static/images/{logo_file.filename}"
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(logo_file.file, buffer)
        settings.logo_url = f"/{file_location}"
    session.add(settings)
    session.commit()
    return RedirectResponse("/settings", status_code=302)

# --- API Endpoints ---

# --- Products ---
@app.get("/api/products")
def get_products_api(session: Session = Depends(get_session), user: User = Depends(require_auth)):
    return session.exec(select(Product)).all()

@app.post("/api/products")
def create_product_api(name: str = Form(...), price: float = Form(...), stock: int = Form(...), session: Session = Depends(get_session), user: User = Depends(require_auth)):
    product = Product(name=name, price=price, stock_quantity=stock, barcode="")
    session.add(product)
    session.commit()
    session.refresh(product)
    product.barcode = stock_service.generate_barcode(product.id)
    session.add(product)
    session.commit()
    return product

@app.put("/api/products/{id}")
def update_product_api(id: int, name: str = Form(...), price: float = Form(...), stock: int = Form(...), session: Session = Depends(get_session), user: User = Depends(require_auth)):
    product = session.get(Product, id)
    if not product: raise HTTPException(404, "Not found")
    product.name = name
    product.price = price
    product.stock_quantity = stock
    session.add(product)
    session.commit()
    return product

@app.delete("/api/products/{id}")
def delete_product_api(id: int, session: Session = Depends(get_session), user: User = Depends(require_auth)):
    product = session.get(Product, id)
    if not product: raise HTTPException(404, "Not found")
    session.delete(product)
    session.commit()
    return {"ok": True}

# --- Clients ---
@app.post("/api/clients")
def create_client_api(name: str = Form(...), phone: Optional[str] = Form(None), email: Optional[str] = Form(None), address: Optional[str] = Form(None), session: Session = Depends(get_session), user: User = Depends(require_auth)):
    client = Client(name=name, phone=phone, email=email, address=address)
    session.add(client)
    session.commit()
    return client

@app.put("/api/clients/{id}")
def update_client_api(id: int, name: str = Form(...), phone: Optional[str] = Form(None), email: Optional[str] = Form(None), address: Optional[str] = Form(None), session: Session = Depends(get_session), user: User = Depends(require_auth)):
    client = session.get(Client, id)
    if not client: raise HTTPException(404, "Not found")
    client.name = name
    client.phone = phone
    client.email = email
    client.address = address
    session.add(client)
    session.commit()
    return client

@app.delete("/api/clients/{id}")
def delete_client_api(id: int, session: Session = Depends(get_session), user: User = Depends(require_auth)):
    client = session.get(Client, id)
    if not client: raise HTTPException(404, "Not found")
    session.delete(client)
    session.commit()
    return {"ok": True}

# --- Sales ---
@app.post("/api/sales")
def create_sale_api(sale_data: dict, session: Session = Depends(get_session), user: User = Depends(require_auth)):
    try:
        sale = stock_service.process_sale(session, user_id=user.id, items_data=sale_data["items"])
        return sale
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Migration Endpoint (Temporary) ---
@app.get("/migrate-legacy")
def migrate_legacy_data(session: Session = Depends(get_session), user: User = Depends(require_auth)):
    # Only admin can migrate
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    import re
    import os
    
    # Path to dump file
    sql_path = "legacy_data/dump.sql"
    if not os.path.exists(sql_path):
        return {"error": "Dump file not found"}
        
    with open(sql_path, 'r', encoding='utf-8') as f:
        content = f.read()

    results = {"clients": 0, "products": 0, "errors": []}
    
    def parse_mysql_insert(line):
        match = re.search(r"VALUES\s+(.*);", line, re.IGNORECASE)
        if not match: return []
        values_str = match.group(1)
        rows_raw = re.split(r"\),\s*\(", values_str)
        parsed_rows = []
        for row in rows_raw:
            row = row.strip("()")
            values = []
            current_val = ""
            in_quote = False
            for char in row:
                if char == "'" and not in_quote: in_quote = True
                elif char == "'" and in_quote: in_quote = False
                elif char == "," and not in_quote:
                    values.append(current_val.strip().strip("'"))
                    current_val = ""
                    continue
                current_val += char
            values.append(current_val.strip().strip("'"))
            parsed_rows.append(values)
        return parsed_rows

    # Migrate Clients
    try:
        client_inserts = re.findall(r"INSERT\s+INTO\s+`cliente`.*", content)
        for line in client_inserts:
            rows = parse_mysql_insert(line)
            for row in rows:
                if len(row) >= 2:
                    name = row[1]
                    if not session.exec(select(Client).where(Client.name == name)).first():
                        session.add(Client(name=name))
                        results["clients"] += 1
    except Exception as e:
        results["errors"].append(f"Client error: {str(e)}")

    # Migrate Products
    try:
        product_inserts = re.findall(r"INSERT\s+INTO\s+`producto`.*", content)
        for line in product_inserts:
            rows = parse_mysql_insert(line)
            for row in rows:
                if len(row) >= 9:
                    try:
                        name = row[2]
                        code = row[1]
                        cost = float(row[3]) if row[3] else 0.0
                        price = float(row[4]) if row[4] else 0.0
                        stock = int(row[7]) if row[7] else 0
                        min_stock = int(row[8]) if row[8] else 5
                        
                        if not session.exec(select(Product).where(Product.barcode == code)).first():
                            session.add(Product(
                                name=name, barcode=code, cost_price=cost,
                                price=price, stock_quantity=stock, min_stock_level=min_stock
                            ))
                            results["products"] += 1
                    except Exception as e:
                        print(f"Skipping product: {e}")
    except Exception as e:
        results["errors"].append(f"Product error: {str(e)}")

    session.commit()
    return results

# --- Schema Migration Endpoint (Temporary) ---
@app.get("/migrate-schema")
def migrate_schema_v3(session: Session = Depends(get_session), user: User = Depends(require_auth)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    from sqlalchemy import text
    try:
        # Add description column if not exists
        session.exec(text("ALTER TABLE product ADD COLUMN description TEXT;"))
        session.commit()
        return {"status": "success", "message": "Added description column to Product table"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
