import os
import requests
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Armac Viagem Corporativa API")

# =========================
# 🔥 CORS (ESSENCIAL)
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# 🔧 CONFIG
# =========================
FLYTOUR_BASE_URL = os.getenv(
    "FLYTOUR_BASE_URL",
    "http://api-armac-prd.eba-gprb3wed.sa-east-1.elasticbeanstalk.com"
)

FLYTOUR_USER = os.getenv("FLYTOUR_USER", "admin")
FLYTOUR_PASS = os.getenv("FLYTOUR_PASS", "Armac2025@Secure")

AUTH = (FLYTOUR_USER, FLYTOUR_PASS)
REQUEST_TIMEOUT = 20

# =========================
# 🧰 HELPERS
# =========================
def safe_float(v: Any) -> float:
    try:
        return float(v) if v not in (None, "") else 0.0
    except:
        return 0.0


# =========================
# 🔄 BUSCAR TODAS AS VENDAS (PAGINAÇÃO REAL)
# =========================
def fetch_all_vendas(idv: str) -> List[Dict]:
    all_data = []
    page = 1

    while True:
        url = f"{FLYTOUR_BASE_URL}/api/armac/vendas"
        params = {
            "idvExterno": idv,
            "page": page
        }

        resp = requests.get(url, params=params, auth=AUTH, timeout=REQUEST_TIMEOUT)

        if resp.status_code != 200:
            print("Erro API:", resp.text)
            break

        json_data = resp.json()
        data = json_data.get("data", [])

        if not data:
            break

        all_data.extend(data)

        if len(data) < 50:
            break

        page += 1

    return all_data


# =========================
# 📊 ENDPOINT PRINCIPAL
# =========================
@app.get("/compare/{idv}")
def compare(idv: str):

    vendas = fetch_all_vendas(idv)

    items = []

    for v in vendas:
        item = {
            "tipo": "flight",
            "viajante": v.get("passageiro"),
            "aprovador": v.get("solicitante"),
            "departamento": v.get("ccustosCliente"),
            "flytour": {
                "type": "flight",
                "fornecedor": v.get("nomeFornecedor")
            },
            "categoria": None,
            "preco_total": safe_float(v.get("tarifa")),
            "preco_unitario": safe_float(v.get("tarifa")),
            "origem": v.get("origemRotaAereo"),
            "destino": v.get("destinoRotaAereo"),
            "rota": v.get("rotaResumida"),
            "data": v.get("dataLancamento")
        }

        items.append(item)

    return {
        "idv": idv,
        "total_items": len(items),
        "items": items
    }


# =========================
# 📈 HISTÓRICO (NOVO)
# =========================
@app.get("/historico/{idv}")
def historico(idv: str):

    vendas = fetch_all_vendas(idv)

    historico = {}

    for v in vendas:
        data = v.get("dataLancamento")
        valor = safe_float(v.get("tarifa"))

        if not data:
            continue

        dia = data[:10]

        if dia not in historico:
            historico[dia] = {
                "data": dia,
                "gasto": 0.0,
                "quantidade": 0
            }

        historico[dia]["gasto"] += valor
        historico[dia]["quantidade"] += 1

    return sorted(historico.values(), key=lambda x: x["data"])


# =========================
# ❤️ HEALTH CHECK
# =========================
@app.get("/")
def root():
    return {"status": "API online"}
