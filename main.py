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

REQUEST_TIMEOUT = 20

# =========================
# HELPERS
# =========================

def safe_float(v: Any) -> float:
    try:
        if v in (None, "", "null"):
            return 0.0
        return float(str(v).replace(",", "."))
    except:
        return 0.0


def split_ids(ids: str) -> List[str]:
    return [x.strip() for x in ids.split(",") if x.strip()]


def parse_date(d):
    try:
        if not d:
            return None
        return datetime.fromisoformat(str(d).replace("Z", ""))
    except:
        return None


# =========================
# 🔥 FLYTOUR (COM PAGINAÇÃO)
# =========================

def get_vendas(idv: Optional[str] = None) -> Dict[str, Any]:
    url = f"{FLYTOUR_BASE_URL}/api/armac/vendas"

    all_data = []
    page = 1
    page_size = 100

    while True:
        params = {
            "page": page,
            "pageSize": page_size
        }

        if idv:
            params["idvExterno"] = idv

        try:
            r = requests.get(
                url,
                auth=AUTH,
                params=params,
                timeout=REQUEST_TIMEOUT
            )

            r.raise_for_status()
            data = r.json()

            if isinstance(data, dict) and "data" in data:
                items = data["data"]
            elif isinstance(data, list):
                items = data
            else:
                items = []

            if not items:
                break

            all_data.extend(items)

            print(f"Página {page}: {len(items)} itens")

            if len(items) < page_size:
                break

            page += 1

        except Exception as e:
            print("ERRO FLYTOUR:", str(e))
            break

    print(f"TOTAL FINAL: {len(all_data)} registros")

    return {"data": all_data}


# =========================
# 🔥 NORMALIZAÇÃO FINAL
# =========================

def normalize_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:

    # 🔥 VALOR (corrigido)
    preco = (
        safe_float(item.get("valorTotal")) or
        safe_float(item.get("tarifa")) or
        safe_float(item.get("valor")) or
        0
    )

    if preco <= 0:
        return None

    # 🔥 CATEGORIA
    tipo_raw = str(item.get("codigoProduto", "")).upper()

    if tipo_raw in ["TKT", "AIR"]:
        categoria = "aereo"
    elif tipo_raw in ["HTL", "HOTEL"]:
        categoria = "hotel"
    elif tipo_raw in ["CAR", "LOC"]:
        categoria = "carro"
    else:
        categoria = "outros"

    # 🔥 DATAS REAIS
    data_venda = item.get("dataLancamento") or item.get("dtCriacao")
    data_viagem = item.get("dtInicioServicos")
    data_retorno = item.get("dtFimServicos")

    d1 = parse_date(data_viagem)
    d2 = parse_date(data_retorno)

    dias = 1
    if d1 and d2:
        dias = max((d2 - d1).days, 1)

    diaria = round(preco / dias, 2)

    # 🔥 FATURAS
    faturas = (
        item.get("faturas") or
        item.get("numeroFatura") or
        item.get("fatura") or
        []
    )

    # 🔥 POLÍTICA
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
        "preco_total": preco,
        "preco_unitario": diaria,

        "data_lancamento": data_venda,
        "data_viagem": data_viagem,
        "data_retorno": data_retorno,

        "data": data_viagem or data_venda,

        "dias": dias,
        "politica": politica,
        "motivo": motivo,
        "faturas": faturas,

        "fornecedor": item.get("nomeFornecedor"),
        "origem": item.get("origemRotaAereo"),
        "destino": item.get("destinoRotaAereo"),
        "rota": item.get("rotaResumida"),
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
            "registro_venda": raw.get("id") or raw.get("idVenda"),

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
