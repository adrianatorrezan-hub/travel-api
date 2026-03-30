import requests
import re
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 🔥 ESSA LINHA É CRÍTICA (resolve erro do Render)
app = FastAPI()

# 🔓 libera acesso do Lovable
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_URL = "http://api-armac-prd.eba-gprb3wed.sa-east-1.elasticbeanstalk.com/api/armac/vendas"


# =========================
# 🔍 extrai total de páginas
# =========================
def extrair_total_paginas(message):
    match = re.search(r"Page\s+\d+\s+of\s+(\d+)", message or "")
    if match:
        return int(match.group(1))
    return None


# =========================
# 🩺 health check
# =========================
@app.get("/")
def home():
    return {"status": "API online"}


# =========================
# 🚀 endpoint principal (TUDO)
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

            response = requests.get(url, timeout=30)
            response.raise_for_status()

            data = response.json()

            # descobre total de páginas na primeira chamada
            if total_paginas is None:
                total_paginas = extrair_total_paginas(data.get("message", ""))

            vendas = data.get("data", [])

            # 🔥 progresso
            if total_paginas:
                print(f"📄 Página {page}/{total_paginas}")
            else:
                print(f"📄 Página {page}")

            if not vendas:
                print("⚠️ Nenhum dado retornado")
                break

            todas_vendas.extend(vendas)

            # chegou na última página
            if total_paginas and page >= total_paginas:
                print("🏁 Última página alcançada")
                break

            # fallback
            if len(vendas) < page_size:
                print("🏁 Última página (fallback)")
                break

            page += 1
            time.sleep(0.2)

        print(f"\n✅ TOTAL FINAL: {len(todas_vendas)} registros\n")

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
