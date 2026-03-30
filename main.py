import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Armac Travel API")

# =========================
# CORS
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

AUTH = (
    os.getenv("FLYTOUR_USER", "admin"),
    os.getenv("FLYTOUR_PASS", "Armac2025@Secure"),
)

REQUEST_TIMEOUT = 30


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


def parse_date(date_str: Optional[str]) -> Optional[str]:
    try:
        if not date_str:
            return None
        return datetime.fromisoformat(str(date_str).replace("Z", "")).isoformat()
    except:
        return None


def match_idv(item: Dict[str, Any], idv: str) -> bool:
    return str(idv) in [
        str(item.get("idvExterno")),
        str(item.get("idVenda")),
        str(item.get("numeroVenda")),
        str(item.get("id")),
        str(item.get("codigo")),
        str(item.get("reserva")),
    ]


# =========================
# 🔥 BUSCA (2 MODOS)
# =========================

def get_vendas(idv: Optional[str] = None, full: bool = False):
    url = f"{FLYTOUR_BASE_URL}/api/armac/vendas"

    all_data = []
    page = 1
    page_size = 100

    # 🔥 diferença aqui
    max_pages = 999 if full else 10

    while True:
        if page > max_pages:
            break

        params = {"page": page, "pageSize": page_size}

        try:
            r = requests.get(url, auth=AUTH, params=params, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()

            items = data.get("data") if isinstance(data, dict) else data

            if not items:
                break

            print(f"📄 Página {page}: {len(items)}")

            for item in items:
                if idv:
                    if not match_idv(item, idv):
                        continue
                all_data.append(item)

            if len(items) < page_size:
                break

            page += 1

        except Exception as e:
            print("❌ ERRO:", str(e))
            break

    print(f"✅ TOTAL: {len(all_data)}")
    return {"data": all_data}


# =========================
# NORMALIZAÇÃO
# =========================

def normalize_item(item: Dict[str, Any]):

    preco = (
        safe_float(item.get("valorTotal"))
        or safe_float(item.get("tarifaTotal"))
        or safe_float(item.get("valor"))
        or safe_float(item.get("tarifa"))
        or 0.0
    )

    data_evento = parse_date(
        item.get("dtInicioServicos")
        or item.get("dataLancamento")
        or item.get("dtCriacao")
    )

    return {
        "tipo": item.get("codigoProduto"),
        "viajante": item.get("passageiro"),
        "departamento": item.get("nomeFantasiaCliente"),
        "registro_venda": item.get("numeroVenda"),
        "preco_total": preco,
        "data_evento": data_evento,
    }


# =========================
# PROCESSAMENTO
# =========================

def process(idv: str, full=False):
    vendas = get_vendas(idv, full=full)

    itens = [
        normalize_item(i)
        for i in vendas["data"]
        if isinstance(i, dict)
    ]

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
    return {"status": "online"}


# 🚀 rápido (UI)
@app.get("/compare/{idv}")
def compare(idv: str):
    return process(idv, full=False)


# 🔥 completo (tudo)
@app.get("/compare-full/{idv}")
def compare_full(idv: str):
    return process(idv, full=True)
