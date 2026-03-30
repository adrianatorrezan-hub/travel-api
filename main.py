import requests
import time

BASE_URL = "http://api-armac-prd.eba-gprb3wed.sa-east-1.elasticbeanstalk.com/api/armac/vendas"


def buscar_todas_vendas():
    page = 1
    page_size = 50
    todas_vendas = []

    print("🚀 Iniciando coleta de dados da API...\n")

    while True:
        try:
            url = f"{BASE_URL}?page={page}&pageSize={page_size}"
            print(f"📄 Buscando página {page}...")

            response = requests.get(url, timeout=30)

            if response.status_code != 200:
                print(f"❌ Erro HTTP {response.status_code}")
                break

            json_data = response.json()

            # Estrutura da API
            vendas = json_data.get("data", [])

            if not vendas:
                print("⚠️ Nenhum dado retornado. Encerrando...")
                break

            todas_vendas.extend(vendas)

            print(f"✔ {len(vendas)} registros recebidos (Total acumulado: {len(todas_vendas)})")

            # Se veio menos que o limite → última página
            if len(vendas) < page_size:
                print("\n🏁 Última página alcançada.")
                break

            page += 1

            # Pequeno delay para não sobrecarregar API
            time.sleep(0.5)

        except Exception as e:
            print(f"❌ Erro inesperado: {e}")
            break

    print(f"\n✅ Total final coletado: {len(todas_vendas)} vendas\n")
    return todas_vendas


def salvar_em_json(dados, arquivo="vendas.json"):
    import json
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    print(f"💾 Dados salvos em {arquivo}")


def main():
    vendas = buscar_todas_vendas()

    if vendas:
        salvar_em_json(vendas)
    else:
        print("⚠️ Nenhum dado foi coletado.")


if __name__ == "__main__":
    main()
