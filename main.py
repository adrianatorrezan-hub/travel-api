import requests
import re
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# libera acesso do Lovable (frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_URL = "http://api-armac-prd.eba-gprb3wed.sa-east-1.elasticbeanstalk.com/api/armac/vendas"


def extrair_total_paginas(message):
    """
    Extrai 'Page 1 of 190' → 190
    """
    match = re.search(r"Page\s+\d+\s+of\s+(\d+)", message or "")
    if match:
        return int(match.group(1))
    return None


@app.get("/")
def home():
    return {"status": "ok"}


@app.get("/all")
def get_all_vendas():
    try:
        page = 1
        page_size = 50
        todas_vendas = []
        total_paginas = None

        while True:
            url = f"{BASE_URL}?page={page}&pageSize={page_size}"

            response = requests.get(url, timeout=30)
            response.raise_for_status()

            data = response.json()

            # pega total de páginas só na primeira chamada
            if total_paginas is None:
                total_paginas = extrair_total_paginas(data.get("message", ""))

            vendas = data.get("data", [])

            print(f"Página {page} carregada ({len(vendas)} itens)")

            if not vendas:
                break

            todas_vendas.extend(vendas)

            # se chegou na última página → para
            if total_paginas and page >= total_paginas:
                break

            # segurança extra
            if len(vendas) < page_size:
                break

            page += 1
            time.sleep(0.2)  # evita sobrecarga

        return {
            "total_itens": len(todas_vendas),
            "itens": todas_vendas
        }

    except Exception as e:
        return {
            "total_itens": 0,
            "itens": [],
            "erro": str(e)
        }
