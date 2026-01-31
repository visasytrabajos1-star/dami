import pandas as pd
import os

# Data from user image
data = [
    {
        "Name": "Ojota lisa",
        "Barcode": "210 NEGRO",
        "Category": "Verano-Ojotas Dama",
        "Price": 1750,
        "Description": "Talle del 35/6 al 39/40",
        "Numeracion": "35-40",
        "CantBulto": 12,
        "Stock": 100
    },
    {
        "Name": "Ojota faja lisa",
        "Barcode": "7059 NEGRO",
        "Category": "Verano-Ojotas Dama",
        "Price": 4200,
        "Description": "Talle del 35/6 al 39/40",
        "Numeracion": "35-40",
        "CantBulto": 12,
        "Stock": 100
    },
    {
        "Name": "Gomones",
        "Barcode": "128BB ROSA",
        "Category": "Verano-Gomones-BB",
        "Price": 3500,
        "Description": "Talle del 19/20 al 23/24",
        "Numeracion": "19-24",
        "CantBulto": 12,
        "Stock": 100
    },
    {
        "Name": "Faja",
        "Barcode": "795 NEGRO",
        "Category": "Verano-Fajas-Dama",
        "Price": 5500,
        "Description": "Talle del 35/6 al 39/40",
        "Numeracion": "35-40",
        "CantBulto": 20,
        "Stock": 100
    },
    {
        "Name": "Sandalia velcro",
        "Barcode": "417BLANCO",
        "Category": "Verano-Fajas-Dama",
        "Price": 13000,
        "Description": "Talle del 35/6 al 39/40",
        "Numeracion": "35-40",
        "CantBulto": 6,
        "Stock": 100
    },
    {
        "Name": "Entrededo",
        "Barcode": "401/6",
        "Category": "Verano-Fajas-Hombre",
        "Price": 3000,
        "Description": "Talle del 37/38 al 43/44",
        "Numeracion": "37-44",
        "CantBulto": 25,
        "Stock": 100
    }
]

df = pd.DataFrame(data)

# Ensure artifacts dir exists
output_path = r"c:\Users\Admin2\.gemini\antigravity\brain\587f2a0d-9fac-4c58-852a-0851732ddffb\productos_prueba.xlsx"
df.to_excel(output_path, index=False)
print(f"File created at {output_path}")
