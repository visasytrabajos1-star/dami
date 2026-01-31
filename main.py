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
from database.models import Product, Sale, User, Settings, Client, Payment, Tax
from services.stock_service import StockService
from services.auth_service import AuthService
import barcode
from barcode.writer import ImageWriter

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
    
    # Calculate balances for each client
    # Optimization: In a real app, use a SQL aggregation query. simpler loop for now.
    balances = {}
    for c in clients:
        sales_total = session.exec(select(func.sum(Sale.total_amount)).where(Sale.client_id == c.id)).one() or 0.0
        payments_total = session.exec(select(func.sum(Payment.amount)).where(Payment.client_id == c.id)).one() or 0.0
        balances[c.id] = float(sales_total - payments_total)
        
    return templates.TemplateResponse("clients.html", {"request": request, "active_page": "clients", "settings": settings, "user": user, "clients": clients, "balances": balances})

@app.get("/clients/{id}/account", response_class=HTMLResponse)
def get_client_account(id: int, request: Request, user: User = Depends(require_auth), settings: Settings = Depends(get_settings), session: Session = Depends(get_session)):
    client = session.get(Client, id)
    if not client: raise HTTPException(404, "Client not found")
    
    # 1. Get Sales
    sales = session.exec(select(Sale).where(Sale.client_id == id)).all()
    
    # 2. Get Payments
    payments_list = session.exec(select(Payment).where(Payment.client_id == id)).all()
    
    # 3. Calculate Balance & Mix Movements
    total_debt = sum(s.total_amount for s in sales)
    total_paid = sum(p.amount for p in payments_list)
    balance = float(total_debt - total_paid)
    
    movements = []
    for s in sales:
        movements.append({
            "date": s.timestamp,
            "description": f"Venta #{s.id}",
            "amount": s.total_amount,
            "type": "sale"
        })
    for p in payments_list:
        movements.append({
            "date": p.date,
            "description": f"Abono: {p.note or ''}",
            "amount": p.amount,
            "type": "payment"
        })
        
    # Sort by date descending
    movements.sort(key=lambda x: x["date"], reverse=True)
    
    return templates.TemplateResponse("client_account.html", {
        "request": request, 
        "active_page": "clients", 
        "settings": settings, 
        "user": user, 
        "client": client,
        "balance": round(balance, 2),
        "movements": movements
    })

@app.post("/api/clients/{id}/pay")
def register_payment(id: int, amount: float = Form(...), note: Optional[str] = Form(None), session: Session = Depends(get_session), user: User = Depends(require_auth)):
    client = session.get(Client, id)
    if not client: raise HTTPException(404, "Client not found")
    
    payment = Payment(client_id=id, amount=amount, note=note)
    session.add(payment)
    session.commit()
    
    return RedirectResponse(f"/clients/{id}/account", status_code=303)

@app.get("/sales", response_class=HTMLResponse)
def get_sales_page(request: Request, user: User = Depends(require_auth), settings: Settings = Depends(get_settings), session: Session = Depends(get_session)):
    # Fetch sales
    sales = session.exec(select(Sale).order_by(Sale.timestamp.desc()).limit(50)).all()
    
    # Fetch low stock products (where stock <= min_stock_level)
    low_stock_products = session.exec(select(Product).where(Product.stock_quantity <= Product.min_stock_level)).all()
    
    return templates.TemplateResponse("sales.html", {
        "request": request, 
        "active_page": "sales", 
        "settings": settings, 
        "user": user, 
        "sales": sales,
        "low_stock_products": low_stock_products
    })

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
def create_product_api(name: str = Form(...), price: float = Form(...), stock: int = Form(...), description: Optional[str] = Form(None), barcode: Optional[str] = Form(None), image: Optional[UploadFile] = File(None), session: Session = Depends(get_session), user: User = Depends(require_auth)):
    final_barcode = barcode if barcode else ""
    product = Product(name=name, price=price, stock_quantity=stock, description=description, barcode=final_barcode)
    
    if image and image.filename:
        import shutil
        import uuid
        # Generate unique filename to avoid collisions
        ext = image.filename.split(".")[-1]
        filename = f"{uuid.uuid4()}.{ext}"
        file_location = f"static/product_images/{filename}"
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        product.image_url = f"/{file_location}"

    session.add(product)
    session.commit()
    session.refresh(product)
    
    # Generate barcode only if not provided
    if not product.barcode:
        product.barcode = stock_service.generate_barcode(product.id)
        session.add(product)
        session.commit()
        
    return product

@app.put("/api/products/{id}")
def update_product_api(id: int, name: str = Form(...), price: float = Form(...), stock: int = Form(...), description: Optional[str] = Form(None), barcode: Optional[str] = Form(None), image: Optional[UploadFile] = File(None), session: Session = Depends(get_session), user: User = Depends(require_auth)):
    product = session.get(Product, id)
    if not product: raise HTTPException(404, "Not found")
    product.name = name
    product.price = price
    product.stock_quantity = stock
    product.description = description
    if barcode:
        product.barcode = barcode
    
    if image and image.filename:
        import shutil
        import uuid
        ext = image.filename.split(".")[-1]
        filename = f"{uuid.uuid4()}.{ext}"
        file_location = f"static/product_images/{filename}"
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        product.image_url = f"/{file_location}"
        
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

# --- Products: Label Printing ---
@app.get("/products/labels", response_class=HTMLResponse)
def get_labels_page(request: Request, user: User = Depends(require_auth), settings: Settings = Depends(get_settings), session: Session = Depends(get_session)):
    products = session.exec(select(Product)).all()
    return templates.TemplateResponse("print_labels_selection.html", {"request": request, "active_page": "products", "settings": settings, "user": user, "products": products})

@app.post("/products/labels/print", response_class=HTMLResponse)
async def print_labels(request: Request, session: Session = Depends(get_session)):
    form = await request.form()
    selected_ids = form.getlist("selected_products")
    
    labels_to_print = []
    
    for pid_str in selected_ids:
        pid = int(pid_str)
        product = session.get(Product, pid)
        if product:
            qty = int(form.get(f"qty_{pid}", 1))
            
            # Ensure barcode image exists
            if not product.barcode:
                 # If no barcode string, generate one (fallback)
                 product.barcode = stock_service.generate_barcode(product.id)
                 session.add(product)
                 session.commit()
                 session.refresh(product)
            
            # Check if file exists, if not recreate
            # We want the image filename. 
            # Re-using generate_barcode logic to ensure file existence for the string.
            
            # Sanitize barcode for filename
            safe_filename = "".join([c for c in product.barcode if c.isalnum()])
            # If empty fallback to id
            if not safe_filename: safe_filename = f"prod_{product.id}"
            
            file_path = f"static/barcodes/{safe_filename}"
            # Format: try EAN13 if 12/13 digits, else Code128
            b_class = barcode.get_barcode_class('ean13') if len(product.barcode) in [12, 13] and product.barcode.isdigit() else barcode.get_barcode_class('code128')
            
            # Create image
            try:
                my_code = b_class(product.barcode, writer=ImageWriter())
                my_code.save(file_path) # saves as file_path.png
                img_filename = f"{safe_filename}.png"
            except Exception as e:
                # Fallback implementation if validation fails (e.g. invalid checksum for EAN)
                # Force Code128
                my_code = barcode.get('code128', product.barcode, writer=ImageWriter())
                my_code.save(file_path)
                img_filename = f"{safe_filename}.png"

            for _ in range(qty):
                labels_to_print.append({
                    "name": product.name,
                    "price": product.price,
                    "barcode": product.barcode,
                    "barcode_file": img_filename
                })
    
    return templates.TemplateResponse("print_layout.html", {"request": request, "labels": labels_to_print})

# --- Clients ---
@app.get("/api/clients")
def get_clients_api(session: Session = Depends(get_session), user: User = Depends(require_auth)):
    return session.exec(select(Client)).all()

@app.post("/api/clients")
def create_client_api(name: str = Form(...), phone: Optional[str] = Form(None), email: Optional[str] = Form(None), address: Optional[str] = Form(None), credit_limit: Optional[float] = Form(None), session: Session = Depends(get_session), user: User = Depends(require_auth)):
    client = Client(name=name, phone=phone, email=email, address=address, credit_limit=credit_limit)
    session.add(client)
    session.commit()
    return client

@app.put("/api/clients/{id}")
def update_client_api(id: int, name: str = Form(...), phone: Optional[str] = Form(None), email: Optional[str] = Form(None), address: Optional[str] = Form(None), credit_limit: Optional[float] = Form(None), session: Session = Depends(get_session), user: User = Depends(require_auth)):
    client = session.get(Client, id)
    if not client: raise HTTPException(404, "Not found")
    client.name = name
    client.phone = phone
    client.email = email
    client.address = address
    client.credit_limit = credit_limit
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
        sale = stock_service.process_sale(session, user_id=user.id, items_data=sale_data["items"], client_id=sale_data.get("client_id"))
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
# --- Schema Migration Endpoint (V4) ---
@app.get("/migrate-schema")
def migrate_schema_v4(session: Session = Depends(get_session), user: User = Depends(require_auth)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    from sqlalchemy import text
    from database.session import create_db_and_tables
    
    # 1. Create new tables (Tax)
    create_db_and_tables() 

    try:
        # 2. Update Settings table
        session.exec(text("ALTER TABLE settings ADD COLUMN printer_name TEXT;"))
        session.commit()
    except Exception as e:
        print(f"Migration error (Settings): {e}")

    try:
        # Previous migrations (safe to retry normally, but wrapped)
        session.exec(text("ALTER TABLE product ADD COLUMN description TEXT;"))
        session.commit()
    except: pass
    
    try:
        session.exec(text("ALTER TABLE client ADD COLUMN credit_limit FLOAT;"))
        session.commit()
    except: pass

    return {"status": "success", "message": "Schema updated (Tax, Settings)"}


# --- Admin Endpoints ---

@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, user: User = Depends(require_auth)):
    if user.role != "admin":
        return RedirectResponse("/")
    return templates.TemplateResponse("admin.html", {"request": request, "user": user})

# Users
@app.get("/api/users")
def get_users(session: Session = Depends(get_session), user: User = Depends(require_auth)):
    if user.role != "admin": raise HTTPException(403)
    return session.exec(select(User)).all()

@app.post("/api/users")
def create_user(
    username: str = Form(...), 
    password: str = Form(...), 
    role: str = Form(...), 
    full_name: Optional[str] = Form(None),
    session: Session = Depends(get_session), 
    user: User = Depends(require_auth)
):
    if user.role != "admin": raise HTTPException(403)
    # Basic hash (In pro use bcrypt)
    from services.auth_service import AuthService
    # reusing AuthService logic if possible or just hash manually for now. 
    # AuthService.verify_password uses bcrypt. We need hash_password.
    # Let's assume AuthService has a hash method or we do it here.
    # For now, simplistic approach or check AuthService.
    # Wait, I don't see AuthService hash method exposed in imports.
    # I'll implement a simple hash here or add to AuthService later. 
    # Checking AuthService...
    import bcrypt
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')
    
    new_user = User(username=username, password_hash=hashed, role=role, full_name=full_name)
    session.add(new_user)
    try:
        session.commit()
    except:
        raise HTTPException(400, "Username already exists")
    return new_user

@app.delete("/api/users/{id}")
def delete_user(id: int, session: Session = Depends(get_session), user: User = Depends(require_auth)):
    if user.role != "admin": raise HTTPException(403)
    if user.id == id: raise HTTPException(400, "Cannot delete yourself")
    target = session.get(User, id)
    if target:
        session.delete(target)
        session.commit()
    return {"ok": True}

# Taxes
@app.get("/api/taxes")
def get_taxes(session: Session = Depends(get_session)):
    return session.exec(select(Tax)).all()

@app.post("/api/taxes")
def create_tax(name: str = Form(...), rate: float = Form(...), session: Session = Depends(get_session), user: User = Depends(require_auth)):
    if user.role != "admin": raise HTTPException(403)
    tax = Tax(name=name, rate=rate)
    session.add(tax)
    session.commit()
    return tax

@app.delete("/api/taxes/{id}")
def delete_tax(id: int, session: Session = Depends(get_session), user: User = Depends(require_auth)):
    if user.role != "admin": raise HTTPException(403)
    tax = session.get(Tax, id)
    if tax:
        session.delete(tax)
        session.commit()
    return {"ok": True}

# Settings
@app.post("/api/settings")
def update_settings_api(
    company_name: str = Form(...), 
    printer_name: Optional[str] = Form(None),
    session: Session = Depends(get_settings), # gets settings obj
    db: Session = Depends(get_session),
    user: User = Depends(require_auth)
):
    if user.role != "admin": raise HTTPException(403)
    # 'session' here is the Settings object from dependency, not DB session
    # Wait, get_settings returns Settings OBJECT.
    # We need to load it into DB session to update.
    current_settings = session
    current_settings.company_name = company_name
    current_settings.printer_name = printer_name
    db.add(current_settings)
    db.commit()
    return current_settings
