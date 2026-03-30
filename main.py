from flask import Flask, jsonify
import requests
import base64
import time

app = Flask(__name__)

# =============================
# CONFIG
# =============================
BASE_URL = "http://api-armac-prd.eba-gprb3wed.sa-east-1.elasticbeanstalk.com/api/armac/vendas"
PAGE_SIZE = 50

# Basic Auth manual (corrige 401)
user_pass = "admin:Armac2025@Secure"
token = base64.b64encode(user_pass.encode()).decode()

HEADERS = {
    "Authorization": f"Basic {token}"
}

# =============================
# FUNÇÃO PRINCIPAL
# =============================
def buscar_todas_vendas():
    page = 1
    all_items = []

    while True:
        url = f"{BASE_URL}?page={page}&pageSize={PAGE_SIZE}"

        print(f"🔄 Buscando página {page}...")

        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=30
            )

            # Se não autorizado → erro direto
            if response.status_code == 401:
                print("❌ ERRO 401 - Não autorizado")
                return {"error": "401 Unauthorized - verifique usuário/senha ou acesso à API"}

            response.raise_for_status()
            data = response.json()

            items = data.get("data", [])

            if not items:
                print("✅ Fim dos dados")
                break

            all_items.extend(items)

            print(f"✔ Página {page} OK ({len(items)} registros)")

            page += 1
            time.sleep(0.3)  # evita overload

        except Exception as e:
            print(f"⚠️ Erro na página {page}: {e}")
            break

    return {
        "total_itens": len(all_items),
        "items": all_items
    }

# =============================
# ENDPOINT
# =============================
@app.route("/all", methods=["GET"])
def get_all():
    result = buscar_todas_vendas()
    return jsonify(result)

# =============================
# START
# =============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
