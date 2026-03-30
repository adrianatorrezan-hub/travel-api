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

        valor = float(v)

        # 🔥 CORREÇÃO DE ESCALA (centavos)
        if valor > 10000:
            valor = valor / 100

        return valor

    except:
        return 0.0


def split_ids(ids: str) -> List[str]:
    return [x.strip() for x in ids.split(",") if x.strip()]


def parse_date(date_str: Optional[str]) -> Optional[str]:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "")).isoformat()
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

        if isinstance(data, dict) and "data" in data:
            return {"data": data["data"]}

        if isinstance(data, list):
            return {"data": data}

        return {"data": []}

    except Exception as e:
        print("❌ ERRO FLYTOUR:", str(e))
        return {"data": []}


# =========================
# 🔥 NORMALIZAÇÃO FINAL
# =========================

def normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:

    # 🔥 PREÇO CORRETO
    preco = (
        safe_float(item.get("valorTotal")) or
        safe_float(item.get("tarifaTotal")) or
        safe_float(item.get("valor")) or
        safe_float(item.get("tarifa")) or
        safe_float(item.get("preco")) or
        0.0
    )

    # 🔥 DETECÇÃO DE CATEGORIA ROBUSTA
    tipo_raw = str(item.get("codigoProduto", "")).upper()
    descricao = str(item).lower()

    if any(x in tipo_raw for x in ["TKT", "AIR"]) or "aereo" in descricao:
        categoria = "aereo"

    elif any(x in tipo_raw for x in ["HTL", "HOTEL"]) or "hotel" in descricao:
        categoria = "hotel"

    elif any(x in tipo_raw for x in ["CAR", "LOC"]) or any(
        x in descricao for x in ["carro", "locacao", "rent"]
    ):
        categoria = "carro"

    else:
        categoria = "outros"

    # 🔥 DATAS
    checkin = parse_date(item.get("dtInicioServicos"))
    checkout = parse_date(item.get("dtFimServicos"))
    data_compra = parse_date(item.get("dtCriacao") or item.get("dataCriacao"))
    data_aprovacao = parse_date(item.get("dtAprovacao") or item.get("dataAprovacao"))

    data_evento = checkin or data_compra or data_aprovacao or datetime.now().isoformat()

    # 🔥 DIAS
    dias = 1
    try:
        if checkin and checkout:
            d1 = datetime.fromisoformat(checkin)
            d2 = datetime.fromisoformat(checkout)
            dias = max((d2 - d1).days, 1)
    except:
        dias = 1

    diaria = round(preco / dias, 2) if dias else preco

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
        "fornecedor": item.get("nomeFornecedor"),

        "preco_total": preco,
        "preco_unitario": diaria,

        "origem": item.get("origemRotaAereo"),
        "destino": item.get("destinoRotaAereo"),
        "rota": item.get("rotaResumida"),

        "data": data_evento,
        "data_evento": data_evento,

        "checkin": checkin,
        "checkout": checkout,
        "data_compra": data_compra,
        "data_aprovacao": data_aprovacao,

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

        item = normalize_item(raw)

        itens.append({
            "tipo": item["type"],
            "viajante": raw.get("passageiro"),
            "aprovador": raw.get("solicitante"),
            "departamento": raw.get("nomeFantasiaCliente"),
            "flytour": item
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
