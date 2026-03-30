import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Armac Travel API")

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
REQUEST_TIMEOUT = 60  # 🔥 aumentado

# =========================
# HELPERS
# =========================

def safe_float(v: Any) -> float:
    try:
        if v in (None, "", "null"):
            return 0.0

        valor = float(str(v).replace(",", "."))

        if valor > 10000:
            valor = valor / 100

        return valor

    except:
        return 0.0


def split_ids(ids: str) -> List[str]:
    return [x.strip() for x in ids.split(",") if x.strip()]


def parse_date(date_str: Optional[str]) -> Optional[str]:
    try:
        if not date_str:
            return None
        return datetime.fromisoformat(str(date_str).replace("Z", "")).isoformat()
    except:
        return None


# =========================
# 🔥 FLYTOUR (PAGINAÇÃO COMPLETA)
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

            print(f"📄 Página {page}: {len(items)} registros")

            if len(items) < page_size:
                break

            page += 1

        except Exception as e:
            print("❌ ERRO FLYTOUR:", str(e))
            break

    print(f"✅ TOTAL FINAL: {len(all_data)} registros")

    return {"data": all_data}


# =========================
# 🔥 NORMALIZAÇÃO FINAL
# =========================

def normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:

    preco = (
        safe_float(item.get("valorTotal")) or
        safe_float(item.get("tarifaTotal")) or
        safe_float(item.get("valor")) or
        safe_float(item.get("tarifa")) or
        0.0
    )

    tipo_raw = str(item.get("codigoProduto", "")).upper()
    descricao = str(item).lower()

    if tipo_raw in ["TKT", "AIR"]:
        categoria = "aereo"
    elif tipo_raw in ["HTL", "HOTEL"]:
        categoria = "hotel"
    elif tipo_raw in ["CAR", "LOC"]:
        categoria = "carro"
    elif "hotel" in descricao:
        categoria = "hotel"
    elif any(x in descricao for x in ["carro", "locacao", "locadora"]):
        categoria = "carro"
    elif any(x in descricao for x in ["aereo", "voo", "flight"]):
        categoria = "aereo"
    else:
        categoria = "outros"

    data_lancamento = parse_date(
        item.get("dataLancamento") or
        item.get("dtLancamento") or
        item.get("dtCriacao")
    )

    dt_inicio = parse_date(item.get("dtInicioServicos"))
    dt_fim = parse_date(item.get("dtFimServicos"))

    data_evento = dt_inicio or data_lancamento or datetime.now().isoformat()

    dias = 1
    try:
        if dt_inicio and dt_fim:
            d1 = datetime.fromisoformat(dt_inicio)
            d2 = datetime.fromisoformat(dt_fim)
            dias = max((d2 - d1).days, 1)
    except:
        dias = 1

    diaria = round(preco / dias, 2) if dias else preco

    faturas = (
        item.get("faturas") or
        item.get("numeroFatura") or
        item.get("fatura") or
        item.get("numFatura") or
        None
    )

    if isinstance(faturas, list):
        faturas = ", ".join([str(f) for f in faturas if f])
    elif isinstance(faturas, dict):
        faturas = str(faturas)

    numero_venda = (
        item.get("numeroVenda") or
        item.get("idVenda") or
        item.get("id") or
        item.get("idvExterno")
    )

    return {
        "type": categoria,
        "categoria": categoria,
        "numero_venda": numero_venda,
        "preco_total": preco,
        "preco_unitario": diaria,
        "data_evento": data_evento,
        "data": data_evento,
        "data_lancamento": data_lancamento,
        "dt_inicio_servico": dt_inicio,
        "dt_fim_servico": dt_fim,
        "checkin": dt_inicio,
        "checkout": dt_fim,
        "faturas": faturas,
        "dias": dias
    }


# =========================
# PROCESSAMENTO
# =========================

def process_single_idv(idv: str):
    try:
        vendas = get_vendas(idv)
    except Exception:
        return {
            "idv": idv,
            "total_itens": 0,
            "itens": [],
            "erro": "Erro ao buscar dados da Flytour"
        }

    itens = []
    data = vendas.get("data", [])

    if isinstance(data, dict):
        data = list(data.values())

    for raw in data:
        if not isinstance(raw, dict):
            continue

        item = normalize_item(raw)

        itens.append({
            "tipo": item["type"],
            "viajante": raw.get("passageiro"),
            "aprovador": raw.get("solicitante"),
            "departamento": raw.get("nomeFantasiaCliente"),
            "registro_venda": item.get("numero_venda"),
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
