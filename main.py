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

REQUEST_TIMEOUT = 20


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


# =========================
# 🔥 BUSCA TOTAL (SEM FILTRO)
# =========================

def get_vendas() -> Dict[str, Any]:
    url = f"{FLYTOUR_BASE_URL}/api/armac/vendas"

    all_data = []
    page = 1
    page_size = 100
    max_pages = 10  # ⚠️ evita 502 no Render

    while True:
        if page > max_pages:
            break

        params = {
            "page": page,
            "pageSize": page_size
        }

        try:
            r = requests.get(
                url,
                auth=AUTH,
                params=params,
                timeout=REQUEST_TIMEOUT
            )

            r.raise_for_status()
            data = r.json()

            items = data.get("data") if isinstance(data, dict) else data

            if not items:
                break

            print(f"📄 Página {page}: {len(items)} registros")

            # 🔥 TRAZ TUDO
            all_data.extend(items)

            if len(items) < page_size:
                break

            page += 1

        except Exception as e:
            print("❌ ERRO FLYTOUR:", str(e))
            break

    print(f"✅ TOTAL FINAL: {len(all_data)} registros")

    return {"data": all_data}


# =========================
# NORMALIZAÇÃO
# =========================

def normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:

    preco = (
        safe_float(item.get("valorTotal"))
        or safe_float(item.get("tarifaTotal"))
        or safe_float(item.get("valor"))
        or safe_float(item.get("tarifa"))
        or 0.0
    )

    tipo = item.get("codigoProduto")

    data_evento = parse_date(
        item.get("dtInicioServicos")
        or item.get("dataLancamento")
        or item.get("dtCriacao")
    )

    return {
        "tipo": tipo,
        "viajante": item.get("passageiro"),
        "aprovador": item.get("solicitante"),
        "departamento": item.get("nomeFantasiaCliente"),
        "registro_venda": item.get("numeroVenda"),
        "preco_total": preco,
        "data_evento": data_evento,
    }


# =========================
# PROCESSAMENTO
# =========================

def process_all():
    vendas = get_vendas()

    itens = []

    for raw in vendas.get("data", []):
        if not isinstance(raw, dict):
            continue

        itens.append(normalize_item(raw))

    return {
        "total_itens": len(itens),
        "itens": itens
    }


# =========================
# ENDPOINTS
# =========================

@app.get("/")
def root():
    return {"status": "API online"}


@app.get("/all")
def get_all():
    return process_all()
