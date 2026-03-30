import requests
import time
import re
import json

# URL base da API
BASE_URL = "http://api-armac-prd.eba-gprb3wed.sa-east-1.elasticbeanstalk.com/api/armac/vendas"


def extrair_total_paginas(message):
    """
    Extrai o total de páginas da mensagem da API
    Ex: 'Successfully retrieved 50 vendas... (Page 1 of 190)'
    """
    match = re.search(r'Page\s+\d+\s+of\s+(\d+)', message)
    if match:
        return int(match.group(1))
    return None


def buscar_todas_vendas():
    page = 1
    page_size = 50
    todas_vendas = []
    total_paginas = None

    print("🚀 Iniciando coleta de dados da API...\n")

    while True:
        try:
            url = f"{BASE_URL}?page={page}&pageSize={page_size}"

            response = requests.get(url, timeout=30)

            if response.status_code != 200:
                print(f"❌ Erro HTTP {response.status_code}")
                break

            json_data = response.json()

            # Descobrir total de páginas na primeira chamada
            if total_paginas is None:
                total_paginas = extrair_total_paginas(json_data.get("message", ""))

            # Mostrar progresso
            if total_paginas:
                print(f"📄 Página {page}/{total_paginas}")
            else:
                print(f"📄 Página {page}")

            vendas = json_data.get("data", [])

            if not vendas:
                print("⚠️ Nenhum dado retornado. Encerrando...")
                break

            todas_vendas.extend(vendas)

            # Parada segura pela quantidade total de páginas
            if total_paginas and page >= total_paginas:
                print("\n🏁 Última página alcançada.")
                break

            # Fallback (caso API mude comportamento)
            if len(vendas) < page_size:
                print("\n🏁 Última página detectada por volume.")
                break

            page += 1

            # Evita sobrecarga na API
            time.sleep(0.3)

        except Exception as e:
            print(f"❌ Erro inesperado: {e}")
            break

    print(f"\n✅ Total final coletado: {len(todas_vendas)} vendas\n")
    return todas_vendas


def salvar_em_json(dados, arquivo="vendas.json"):
    try:
        with open(arquivo, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        print(f"💾 Dados salvos em: {arquivo}")
    except Exception as e:
        print(f"❌ Erro ao salvar arquivo: {e}")


def main():
    vendas = buscar_todas_vendas()

    if vendas:
        salvar_em_json(vendas)
    else:
        print("⚠️ Nenhum dado foi coletado.")


if __name__ == "__main__":
    main()
