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

def split_ids(ids: str) -> List[str]:
    return [x.strip() for x in ids.split(",") if x.strip()]

def parse_date(dt):
    try:
        if not dt:
            return None
        return datetime.fromisoformat(dt.replace("Z", ""))
    except:
        return None

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

        if isinstance(data, dict):
            if "data" in data:
                return {"data": data["data"]}
            if "itens" in data:
                return {"data": data["itens"]}
            return {"data": list(data.values())}

        if isinstance(data, list):
            return {"data": data}

        return {"data": []}

    except Exception as e:
        print("ERRO FLYTOUR:", str(e))
        return {"data": []}

# =========================
# 🔥 NORMALIZAÇÃO FINAL
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

    tipo_raw = str(item.get("codigoProduto", "")).upper()

    if any(x in tipo_raw for x in ["TKT", "AIR", "FLT"]):
        categoria = "aereo"

    elif any(x in tipo_raw for x in ["HTL", "HOTEL", "HOS", "ACC"]):
        categoria = "hotel"

    elif any(x in tipo_raw for x in ["CAR", "LOC", "VEI", "RENT"]):
        categoria = "carro"

    else:
        if item.get("dtInicioServicos") and item.get("dtFimServicos"):
            categoria = "hotel"
        else:
            categoria = "outros"

    # =========================
    # DATAS
    # =========================

    checkin_dt = parse_date(item.get("dtInicioServicos"))
    checkout_dt = parse_date(item.get("dtFimServicos"))

    data_compra_dt = parse_date(
        item.get("dtCriacao") or item.get("dataCriacao")
    )

    data_principal = checkin_dt or data_compra_dt

    # =========================
    # DIAS
    # =========================

    dias = 1
    if checkin_dt and checkout_dt:
        dias = max((checkout_dt - checkin_dt).days, 1)

    diaria = round(preco / dias, 2) if dias else preco

    # =========================
    # POLÍTICA
    # =========================

    politica = "dentro"
    motivo = None

    if categoria == "hotel" and diaria > 500:
        politica = "fora"
        motivo = "Diária acima de R$500"

    if categoria == "aereo" and preco > 2000:
        politica = "fora"
        motivo = "Passagem acima de R$2000"

    return {
        "type": categoria,
        "categoria": categoria,
        "fornecedor": item.get("nomeFornecedor"),

        "preco_total": preco,
        "preco_unitario": diaria,

        "origem": item.get("origemRotaAereo"),
        "destino": item.get("destinoRotaAereo"),
        "rota": item.get("rotaResumida"),

        "checkin": checkin_dt.isoformat() if checkin_dt else None,
        "checkout": checkout_dt.isoformat() if checkout_dt else None,
        "data": data_principal.isoformat() if data_principal else None,

        "dias": dias,
        "politica": politica,
        "motivo": motivo
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
            "viajante": raw.get("passageiro"),
            "aprovador": raw.get("solicitante"),
            "departamento": raw.get("nomeFantasiaCliente"),
            "flytour": contract_item
        })

    print(f"IDV {idv} -> {len(itens)} itens")

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

# 🔥 ENDPOINT PRINCIPAL (LOVABLE)
@app.get("/historico/{idv}")
def historico(idv: str):
    resultado = process_single_idv(idv)

    return {
        "itens": resultado["itens"]
    }

# 🔥 FEED
@app.get("/feed")
def feed(ids: Optional[str] = None):
    id_list = split_ids(ids) if ids else ["1169902"]

    return {
        "resultados": [process_single_idv(i) for i in id_list]
    }
