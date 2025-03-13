
import os
import requests
import time
from dotenv import load_dotenv
import replicate

load_dotenv()

replicate_token = os.getenv("REPLICATE_API_TOKEN")
coin_gecko_api = os.getenv("coin_gecko_api")
os.environ["REPLICATE_API_TOKEN"] = replicate_token

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

    Retorne somente o endpoint completo com todos os parâmetros, sem a URL base, para responder:
    "{question}"
    '''


def montar_prompt_alternativo(question, endpoints_falhos):
    return f'''
    O endpoint(s) anterior(es) falhou(falharam): {endpoints_falhos}.
    Escolha outro endpoint válido para responder: "{question}".
    Retorne somente o endpoint completo sem URL base.
    '''


def montar_prompt_final(question, coin_data):
    return f'''
    O usuário perguntou: "{question}". Com base nestes dados da API CoinGecko: {coin_data}, responda de maneira descontraída, divertida, clara e em primeira pessoa.
    '''


def consultar_deepseek(prompt):
    output = replicate.run(
        "deepseek-ai/deepseek-r1",
        input={"prompt": prompt}
    )
    return ''.join(output).strip().replace('`', '')


def consultar_coingecko(endpoint):
    headers = {'accept': 'application/json',
               'x-cg-demo-api-key': coin_gecko_api}
    response = requests.get(endpoint, headers=headers)
    response.raise_for_status()
    return response.json()


def obter_dados(question):
    endpoints_falhos = []
    for tentativa in range(2):
        prompt = (montar_prompt_inicial(question) if tentativa == 0
                  else montar_prompt_alternativo(question, endpoints_falhos))
        endpoint = BASE_URL + consultar_deepseek(prompt)

        try:
            return consultar_coingecko(endpoint)
        except requests.HTTPError as e:
            print(
                f"⚠️ Erro na consulta ao CoinGecko (tentativa {tentativa+1}): {e}")
            endpoints_falhos.append(endpoint)
            if tentativa == 0:
                print("🔄 Tentando endpoint alternativo...")
                time.sleep(1)
            else:
                print("❌ Endpoint alternativo também falhou.")
    return None


def main():
    print("🚀 Bem-vindo ao consultor cripto avançado com Deepseek!           ")

    while True:
        question = input("🪙 O que deseja consultar no mundo das criptos? (ou 'sair')
                         👉 ")

        if question.lower() == "sair":
            print("👋 Até mais! Bons investimentos!")
            break

        coin_data = obter_dados(question)

        if coin_data:
            resposta_final = consultar_deepseek(
                montar_prompt_final(question, coin_data))
            print("
                  ✨ " + resposta_final)
        else:
            print(
                "😢 Não consegui obter as informações desta vez. Tente outra consulta!                   ")


if __name__ == "__main__":
    main()
