import sys
import os

# Add backend directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlmodel import Session, select
from database.session import engine, create_db_and_tables
from database.models import Product

def seed():
    print("--- Seeding Products ---")
    create_db_and_tables()
    
    data = [
        {
            "name": "Ojota lisa",
            "barcode": "210 NEGRO",
            "category": "Verano-Ojotas Dama",
            "price": 1750,
            "description": "Talle del 35/6 al 39/40",
            "numeracion": "35-40",
            "cant_bulto": 12,
            "stock_quantity": 100
        },
        {
            "name": "Ojota faja lisa",
            "barcode": "7059 NEGRO",
            "category": "Verano-Ojotas Dama",
            "price": 4200,
            "description": "Talle del 35/6 al 39/40",
            "numeracion": "35-40",
            "cant_bulto": 12,
            "stock_quantity": 100
        },
        {
            "name": "Gomones",
            "barcode": "128BB ROSA",
            "category": "Verano-Gomones-BB",
            "price": 3500,
            "description": "Talle del 19/20 al 23/24",
            "numeracion": "19-24",
            "cant_bulto": 12,
            "stock_quantity": 100
        },
        {
            "name": "Faja",
            "barcode": "795 NEGRO",
            "category": "Verano-Fajas-Dama",
            "price": 5500,
            "description": "Talle del 35/6 al 39/40",
            "numeracion": "35-40",
            "cant_bulto": 20,
            "stock_quantity": 100
        },
        {
            "name": "Sandalia velcro",
            "barcode": "417BLANCO",
            "category": "Verano-Fajas-Dama",
            "price": 13000,
            "description": "Talle del 35/6 al 39/40",
            "numeracion": "35-40",
            "cant_bulto": 6,
            "stock_quantity": 100
        },
        {
            "name": "Entrededo",
            "barcode": "401/6",
            "category": "Verano-Fajas-Hombre",
            "price": 3000,
            "description": "Talle del 37/38 al 43/44",
            "numeracion": "37-44",
            "cant_bulto": 25,
            "stock_quantity": 100
        }
    ]

    with Session(engine) as session:
        count = 0
        for item in data:
            existing = session.exec(select(Product).where(Product.barcode == item["barcode"])).first()
            if not existing:
                p = Product(**item)
                session.add(p)
                count += 1
        
        session.commit()
        print(f"Seeded {count} products.")

if __name__ == "__main__":
    seed()
