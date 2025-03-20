import os
import requests
import time
import re
from dotenv import load_dotenv
import replicate

load_dotenv()

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
COIN_GECKO_API = os.getenv("coin_gecko_api")

if not REPLICATE_API_TOKEN or not COIN_GECKO_API:
    raise ValueError("⚠️ Confira suas variáveis REPLICATE_API_TOKEN e coin_gecko_api no .env!")

os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

BASE_URL = "https://api.coingecko.com/api/v3"


def montar_prompt_inicial(question):
    return f'''
Você é especialista na API CoinGecko. Escolha o endpoint correto para responder:

- /simple/price?ids={{coin}}&vs_currencies={{currency}}
- /coins/{{coin}}/market_chart?vs_currency={{currency}}&days={{days}}
- /coins/{{coin}}/market_chart/range?vs_currency={{currency}}&from={{timestamp}}&to={{timestamp}}
- /coins/{{coin}}/ohlc?vs_currency={{currency}}&days={{days}}
- /coins/markets?vs_currency={{currency}}
- /exchange_rates
- /global

IMPORTANTE: Sempre que pedir médias, máximos, mínimos ou histórico, use /coins/{{coin}}/market_chart com parâmetros obrigatórios: vs_currency (usd), days (período).

Retorne APENAS o endpoint completo com parâmetros, SEM a URL base, entre ASTERISCOS DUPLOS (**), como no exemplo:
**/simple/price?ids=bitcoin&vs_currencies=usd**

Pergunta a responder:
"{question}"
'''


def montar_prompt_alternativo(question, endpoints_falhos):
    return f'''
O(s) endpoint(s) anterior(es) falhou(falharam): {endpoints_falhos}.
Escolha outro endpoint válido para responder à pergunta: "{question}".

Retorne APENAS o endpoint completo com parâmetros, SEM a URL base, entre ASTERISCOS DUPLOS (**), como no exemplo:
**/coins/bitcoin**

Sem explicações adicionais.
'''


def montar_prompt_final(question, coin_data):
    return f'''
O usuário perguntou: "{question}". Com base nestes dados da API CoinGecko: {coin_data}, responda de maneira descontraída, divertida, clara e em primeira pessoa.
'''


def consultar_deepseek_stream(prompt):
    resposta_final = ""
    for evento in replicate.stream(
        "deepseek-ai/deepseek-r1",
        input={
            "prompt": prompt,
            "top_p": 1,
            "max_tokens": 20480,
            "temperature": 0.2,
            "presence_penalty": 0,
            "frequency_penalty": 0
        },
    ):
        resposta_final += str(evento)
        print(str(evento), end="", flush=True)
    print()
    return resposta_final.strip()


def consultar_coingecko(endpoint):
    headers = {
        'accept': 'application/json',
        'x-cg-demo-api-key': COIN_GECKO_API
    }
    response = requests.get(endpoint, headers=headers)
    response.raise_for_status()
    return response.json()


def extrair_endpoint(resposta):
    match = re.search(r"\*\*(.*?)\*\*", resposta)
    return match.group(1).strip() if match else None


def obter_dados(question):
    endpoints_falhos = []
    for tentativa in range(2):
        prompt = (montar_prompt_inicial(question) if tentativa == 0
                  else montar_prompt_alternativo(question, endpoints_falhos))

        resposta_completa = consultar_deepseek_stream(prompt)
        endpoint_gerado = extrair_endpoint(resposta_completa)

        if not endpoint_gerado:
            print("⚠️ Não consegui extrair o endpoint da resposta do modelo.")
            endpoints_falhos.append("Extração falhou")
            continue

        endpoint_completo = BASE_URL + endpoint_gerado

        try:
            dados = consultar_coingecko(endpoint_completo)
            return dados
        except requests.HTTPError as e:
            print(f"⚠️ Erro na consulta ao CoinGecko (tentativa {tentativa+1}): {e}")
            endpoints_falhos.append(endpoint_gerado)
            if tentativa == 0:
                print("🔄 Tentando endpoint alternativo...")
                time.sleep(1)
            else:
                print("❌ Endpoint alternativo também falhou.")
    return None


def main():
    print("🚀 Bem-vindo ao Consultor Cripto Avançado com DeepSeek! 🚀\n")

    while True:
        question = input("🪙 O que deseja consultar no mundo das criptos? (ou digite 'sair')\n👉 ").strip()

        if question.lower() == "sair":
            print("👋 Até mais! Bons investimentos!")
            break

        print("\n🔍 Consultando CoinGecko com ajuda do DeepSeek...\n")

        coin_data = obter_dados(question)

        if coin_data:
            print("\n💬 Gerando resposta personalizada:\n")
            consultar_deepseek_stream(montar_prompt_final(question, coin_data))
            print("\n✅ Concluído com sucesso!\n")
        else:
            print("\n😢 Não consegui obter as informações desta vez. Tente outra consulta!\n")


if __name__ == "__main__":
    main()
