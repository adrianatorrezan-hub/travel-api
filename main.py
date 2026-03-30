import requests
import re
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from requests.auth import HTTPBasicAuth

# 🔥 ESSENCIAL pro Render
app = FastAPI()

# 🔓 liberar acesso do frontend (Lovable)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔗 API da Armac
BASE_URL = "http://api-armac-prd.eba-gprb3wed.sa-east-1.elasticbeanstalk.com/api/armac/vendas"

# 🔐 BASIC AUTH (SEU CASO)
AUTH = HTTPBasicAuth("admin", "Armac2025@Secure")


# =========================
# extrair total de páginas
# =========================
def extrair_total_paginas(message):
    match = re.search(r"Page\s+\d+\s+of\s+(\d+)", message or "")
    if match:
        return int(match.group(1))
    return None


# =========================
# health check
# =========================
@app.get("/")
def home():
    return {"status": "API online"}


# =========================
# endpoint principal (TUDO)
# =========================
@app.get("/all")
def get_all_vendas():
    try:
        page = 1
        page_size = 50
        todas_vendas = []
        total_paginas = None

        print("🚀 Iniciando coleta...\n")

        while True:
            url = f"{BASE_URL}?page={page}&pageSize={page_size}"

            response = requests.get(
                url,
                auth=AUTH,   # 🔥 AQUI resolve o 401
                timeout=30
            )

            response.raise_for_status()

            data = response.json()

            # descobre total páginas
            if total_paginas is None:
                total_paginas = extrair_total_paginas(data.get("message", ""))

            vendas = data.get("data", [])

            # progresso
            if total_paginas:
                print(f"📄 Página {page}/{total_paginas}")
            else:
                print(f"📄 Página {page}")

            if not vendas:
                print("⚠️ Sem dados")
                break

            todas_vendas.extend(vendas)

            # última página
            if total_paginas and page >= total_paginas:
                print("🏁 Fim (total páginas)")
                break

            # fallback segurança
            if len(vendas) < page_size:
                print("🏁 Fim (fallback)")
                break

            page += 1
            time.sleep(0.2)

        print(f"\n✅ TOTAL: {len(todas_vendas)} registros\n")

        return {
            "total_itens": len(todas_vendas),
            "itens": todas_vendas
        }

    except Exception as e:
        print("❌ ERRO:", str(e))

        return {
            "total_itens": 0,
            "itens": [],
            "erro": str(e)
        }
