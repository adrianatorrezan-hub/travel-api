import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Armac Viagem Corporativa API")

# =========================
# 🔥 CORS
# =========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# CONFIG
# =========================

FLYTOUR_BASE_URL = os.getenv(
    "FLYTOUR_BASE_URL",
    "http://api-armac-prd.eba-gprb3wed.sa-east-1.elasticbeanstalk.com",
)

FLYTOUR_USER = os.getenv("FLYTOUR_USER", "admin")
FLYTOUR_PASS = os.getenv("FLYTOUR_PASS", "Armac2025@Secure")

AUTH = (FLYTOUR_USER, FLYTOUR_PASS)

REQUEST_TIMEOUT = 15

# =========================
# HELPERS
# =========================

def safe_float(v: Any) -> float:
    try:
        return float(v) if v not in (None, "") else 0.0
    except:
        return 0.0

def safe_int(v: Any) -> int:
    try:
        return int(float(v)) if v not in (None, "") else 0
    except:
        return 0

def split_ids(ids: str) -> List[str]:
    return [x.strip() for x in ids.split(",") if x.strip()]

# =========================
# 🔥 FLYTOUR
# =========================

def get_vendas(idv: Optional[str] = None) -> Dict[str, Any]:
    url = f"{FLYTOUR_BASE_URL}/api/armac/vendas"

    params = {}
    if idv:
        params["idvExterno"] = idv

    try:
        r = requests.get(url, auth=AUTH, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()

        print("\n===== DEBUG FLYTOUR =====")
        print(data)

        if isinstance(data, dict) and "data" in data:
            return {"data": data["data"]}

        if isinstance(data, list):
            return {"data": data}

        return {"data": []}

    except Exception as e:
        print("ERRO FLYTOUR:", str(e))
        return {"data": []}

# =========================
# 🔥 NORMALIZAÇÃO (FIX NULL)
# =========================

def normalize_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:

    preco = (
        safe_float(item.get("tarifa")) or
        safe_float(item.get("valorTotal")) or
        safe_float(item.get("valor")) or
        0
    )

    if preco == 0:
        return None

    return {
        "type": item.get("codigoProduto") or "outros",
        "fornecedor": item.get("nomeFornecedor") or "N/A",
        "categoria": item.get("classe") or item.get("categoriaHotel") or "N/A",
        "preco_total": preco,
        "preco_unitario": preco,
        "origem": item.get("origemRotaAereo") or "",
        "destino": item.get("destinoRotaAereo") or "",
        "rota": item.get("rotaResumida") or "",
        "data": item.get("dtInicioServicos") or item.get("dataLancamento"),
    }

# =========================
# PROCESSAMENTO
# =========================

def process_single_idv(idv: str):
    vendas = get_vendas(idv)

    itens = []
    data = vendas.get("data", [])

    if isinstance(data, dict):
        data = list(data.values())

    if not isinstance(data, list):
        data = []

    for raw in data:

        if not isinstance(raw, dict):
            continue

        contract_item = normalize_item(raw)

        if not contract_item:
            continue

        itens.append({
            "tipo": contract_item["type"],
            "viajante": raw.get("passageiro") or "N/A",
            "aprovador": raw.get("solicitante") or "N/A",
            "departamento": raw.get("nomeFantasiaCliente") or "N/A",
            "flytour": contract_item
        })

    return {
        "idv": idv,
        "total_itens": len(itens),
        "itens": itens
    }

# =========================
# 📈 HISTÓRICO (NOVO)
# =========================

def build_historico(idv: str):
    vendas = get_vendas(idv)

    historico = {}
    data = vendas.get("data", [])

    if not isinstance(data, list):
        data = []

    for item in data:
        if not isinstance(item, dict):
            continue

        data_str = item.get("dtInicioServicos") or item.get("dataLancamento")
        valor = safe_float(item.get("tarifa"))

        if not data_str:
            continue

        dia = data_str[:10]

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
# ENDPOINTS
# =========================

@app.get("/")
def root():
    return {"status": "API online"}

@app.get("/compare/{idv}")
def compare_one(idv: str):
    return process_single_idv(idv)

@app.get("/compare")
def compare_many(ids: str = Query(...)):
    return {
        "resultados": [process_single_idv(i) for i in split_ids(ids)]
    }

@app.get("/feed")
def feed(ids: Optional[str] = None):
    id_list = split_ids(ids) if ids else ["1169902"]

    return {
        "resultados": [process_single_idv(i) for i in id_list]
    }

@app.get("/historico/{idv}")
def historico(idv: str):
    return build_historico(idv)
