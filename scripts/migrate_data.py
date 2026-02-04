import sys
import os
import re

# Add backend directory to path so we can import app modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlmodel import Session, select
from database.session import engine, create_db_and_tables
from database.models import Product, Client

SQL_FILE_PATH = r"C:\Users\Admin2\.gemini\antigravity\scratch\stock_system\SQL\BaseDeDatos v1.0.5.sql"

def parse_mysql_insert(line):
    # Very basic parser for: INSERT INTO `table`(...) VALUES (v1, v2, ...), (v1, v2, ...);
    # This assumes simple structure as seen in the file.
    
    # Extract values part
    match = re.search(r"VALUES\s+(.*);", line, re.IGNORECASE)
    if not match:
        return []
    
    values_str = match.group(1)
    
    # Split by ),( to get rows
    # This is a naive split, assuming no closing parenthesis inside strings
    # But looking at the dump, strings are simple.
    rows_raw = re.split(r"\),\s*\(", values_str)
    
    parsed_rows = []
    for row in rows_raw:
        # Clean edges
        row = row.strip("()")
        
        # Split by comma, respecting quotes is hard with simple split, 
        # but let's try csv module logic or simple regex for now since data looks simple
        # Only strings have quotes '
        
        # Simple parser for comma separated values
        values = []
        current_val = ""
        in_quote = False
        for char in row:
            if char == "'" and not in_quote:
                in_quote = True
            elif char == "'" and in_quote:
                in_quote = False
            elif char == "," and not in_quote:
                values.append(current_val.strip().strip("'"))
                current_val = ""
                continue
            current_val += char
        values.append(current_val.strip().strip("'"))
        
        parsed_rows.append(values)
        
    return parsed_rows

def migrate():
    print("--- Starting Migration ---")
    create_db_and_tables()
    
    with open(SQL_FILE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Setup session
    session = Session(engine)
    
    # 1. Migrate Clients
    print("\nMigrating Clients...")
    # INSERT INTO `cliente`(`id`,`nombre`,`descuento`,`habilitado`) VALUES (1,'Cliente Contado','0',1);
    client_inserts = re.findall(r"INSERT\s+INTO\s+`cliente`.*", content)
    
    count_clients = 0
    for line in client_inserts:
        rows = parse_mysql_insert(line)
        for row in rows:
            # Schema: id, nombre, descuento, habilitado
            # We map: nombre -> name
            if len(row) >= 2:
                name = row[1]
                
                # Check if exists
                existing = session.exec(select(Client).where(Client.name == name)).first()
                if not existing:
                    client = Client(name=name)
                    session.add(client)
                    count_clients += 1
    
    print(f"Migrated {count_clients} clients.")

    # 2. Migrate Products
    print("\nMigrating Products...")
    # INSERT INTO `producto`(`id`,`codigo`,`nombre`,`preciocosto`,`precioventa`,`proveedor`,`departamento`,`stock`,`stockMin`,`impuesto`,`medida`,`especificaciones`,`habilitado`)
    product_inserts = re.findall(r"INSERT\s+INTO\s+`producto`.*", content)
    
    count_products = 0
    for line in product_inserts:
        rows = parse_mysql_insert(line)
        for row in rows:
            # Indices based on insert schema above:
            # 0: id, 1: codigo, 2: nombre, 3: preciocosto, 4: precioventa, 
            # 5: proveedor, 6: departamento, 7: stock, 8: stockMin
            
            if len(row) >= 9:
                try:
                    name = row[2]
                    code = row[1]
                    cost = float(row[3]) if row[3] else 0.0
                    price = float(row[4]) if row[4] else 0.0
                    stock = int(row[7]) if row[7] else 0
                    min_stock = int(row[8]) if row[8] else 5
                    
                    # Check if exists by barcode (unique)
                    existing = session.exec(select(Product).where(Product.barcode == code)).first()
                    if not existing:
                        p = Product(
                            name=name,
                            barcode=code,
                            cost_price=cost,
                            price=price,
                            stock_quantity=stock,
                            min_stock_level=min_stock
                        )
                        session.add(p)
                        count_products += 1
                except Exception as e:
                    print(f"Skipping product row due to error: {e} | Row: {row}")

    print(f"Migrated {count_products} products.")
    
    session.commit()
    session.close()
    print("\n--- Migration Complete ---")

if __name__ == "__main__":
    migrate()
