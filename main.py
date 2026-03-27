import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, Query
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
# CONFIG
# =========================

FLYTOUR_BASE_URL = os.getenv(
    "FLYTOUR_BASE_URL",
    "http://api-armac-prd.eba-gprb3wed.sa-east-1.elasticbeanstalk.com",
)
FLYTOUR_USER = os.getenv("FLYTOUR_USER", "admin")
FLYTOUR_PASS = os.getenv("FLYTOUR_PASS", "Armac2025@Secure")
AUTH = (FLYTOUR_USER, FLYTOUR_PASS)

REQUEST_TIMEOUT = 10

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

def calc_unit_price(total: float, qty: int) -> float:
    return round(total / qty, 2) if qty else total

def split_ids(ids: str) -> List[str]:
    return [x.strip() for x in ids.split(",") if x.strip()]

# =========================
# FLYTOUR
# =========================

def get_vendas(idv: str) -> List[Dict[str, Any]]:
    url = f"{FLYTOUR_BASE_URL}/api/armac/vendas"
    params = {"idvExterno": idv} if idv else {}

    try:
        r = requests.get(url, auth=AUTH, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()

        print("\n===== DEBUG FLYTOUR =====")
        print(data)

        # API padrão Flytour
        if isinstance(data, dict) and "data" in data:
            return data["data"]

        # fallback
        if isinstance(data, list):
            return data

        return []

    except Exception as e:
        print("ERRO FLYTOUR:", str(e))
        return []

# =========================
# NORMALIZAÇÃO
# =========================

def normalize_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tipo = safe_int(item.get("tipoRoteiro"))

    # ✈️ AÉREO
    if tipo == 2:
        preco = safe_float(item.get("tarifa"))
        rota = item.get("rotaResumida", "")

        origem = item.get("origemRotaAereo")
        destino = item.get("destinoRotaAereo")

        return {
            "type": "flight",
            "fornecedor": item.get("nomeFornecedor"),
            "categoria": item.get("classe"),
            "preco_total": preco,
            "preco_unitario": preco,
            "origem": origem,
            "destino": destino,
            "rota": rota,
            "data": item.get("dtInicioServicos"),
        }

    # 🏨 HOTEL
    if tipo == 3:
        total = safe_float(item.get("valorTotal"))
        diarias = safe_int(item.get("qtdTrechosDiarias")) or 1

        return {
            "type": "hotel",
            "fornecedor": item.get("nomeFornecedor"),
            "categoria": item.get("categoriaHotel"),
            "preco_total": total,
            "preco_unitario": calc_unit_price(total, diarias),
            "cidade": item.get("cidadeFornecedor"),
            "diarias": diarias,
        }

    # 🚗 CARRO
    if tipo == 1:
        total = safe_float(item.get("valorTotal"))
        diarias = safe_int(item.get("qtdTrechosDiarias")) or 1

        return {
            "type": "car",
            "fornecedor": item.get("nomeFornecedor"),
            "categoria": item.get("categoriaVeiculo"),
            "preco_total": total,
            "preco_unitario": calc_unit_price(total, diarias),
            "cidade": item.get("cidadeFornecedor"),
            "diarias": diarias,
        }

    return None

# =========================
# PROCESSAMENTO
# =========================

def process_single_idv(idv: str):
    registros = get_vendas(idv)
    itens = []

    for raw in registros:

        if not isinstance(raw, dict):
            continue

        # 🔥 filtro correto (não quebra se vier vazio)
        if idv and str(raw.get("idvExterno")) != str(idv):
            continue

        contract_item = normalize_item(raw)

        if not contract_item:
            continue

        itens.append({
            "tipo": contract_item["type"],
            "viajante": raw.get("passageiro"),
            "aprovador": raw.get("solicitante"),
            "departamento": raw.get("nomeFantasiaCliente"),
            "flytour": contract_item
        })

    return {
        "idv": idv,
        "total_itens": len(itens),
        "itens": itens
    }

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
