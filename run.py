import os
import requests
import time
import re
import uuid
from dotenv import load_dotenv
import replicate
import cloudinary
import cloudinary.uploader

# 🧪 Carrega variáveis do .env
load_dotenv()

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
COIN_GECKO_API = os.getenv("coin_gecko_api")

if not REPLICATE_API_TOKEN or not COIN_GECKO_API:
    raise ValueError(
        "⚠️ Please check your REPLICATE_API_TOKEN and coin_gecko_api variables in the .env file!"
    )

os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

# 🔧 Cloudinary setup
cloudinary.config(
    secure=True,
    cloud_name=os.getenv("CLOUDINARY_URL").split("@")[-1],
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

# 🌟 Imagem do avatar
SADTALKER_IMAGE_URL = "https://res.cloudinary.com/dixebxp5r/image/upload/c_crop,g_auto,h_800,w_800/renata"

BASE_URL = "https://api.coingecko.com/api/v3"


def clean_response(text):
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def remove_emojis(text):
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub(r"", text)


def build_initial_prompt(question):
    return f'''
You are an expert in the CoinGecko API. Choose the correct endpoint to answer:

- /simple/price?ids={{coin}}&vs_currencies={{currency}}
- /coins/{{coin}}/market_chart?vs_currency={{currency}}&days={{days}}
- /coins/{{coin}}/market_chart/range?vs_currency={{currency}}&from={{timestamp}}&to={{timestamp}}
- /coins/{{coin}}/ohlc?vs_currency={{currency}}&days={{days}}
- /coins/markets?vs_currency={{currency}}
- /exchange_rates
- /global

IMPORTANT: When asked about averages, highs, lows, or historical data, use /coins/{{coin}}/market_chart with required parameters: vs_currency (usd), days (period).

Return ONLY the full endpoint with parameters, WITHOUT the base URL, surrounded by DOUBLE ASTERISKS (**), like this:
**/simple/price?ids=bitcoin&vs_currencies=usd**

User question:
"{question}"
'''


def build_alternative_prompt(question, failed_endpoints):
    return f'''
The previous endpoint(s) failed: {failed_endpoints}.
Choose another valid endpoint to answer the question: "{question}".

Return ONLY the full endpoint with parameters, WITHOUT the base URL, surrounded by DOUBLE ASTERISKS (**), like this:
**/coins/bitcoin**

No additional explanations.
'''


def build_final_prompt(question, coin_data):
    return f'''
The user asked: "{question}". Based on this data from the CoinGecko API: {coin_data}, answer in a friendly, humorous, clear, and first-person tone.
'''


def query_deepseek_stream(prompt):
    raw_response = ""
    for event in replicate.stream(
        "deepseek-ai/deepseek-r1",
        input={
            "prompt": prompt,
            "top_p": 1,
            "max_tokens": 20480,
            "temperature": 0.2,
            "presence_penalty": 0,
            "frequency_penalty": 0,
        },
    ):
        raw_response += str(event)

    final_response = clean_response(raw_response)
    return final_response.strip()


def query_coingecko(endpoint):
    headers = {
        "accept": "application/json",
        "x-cg-demo-api-key": COIN_GECKO_API,
    }
    response = requests.get(endpoint, headers=headers)
    response.raise_for_status()
    return response.json()


def extract_endpoint(response):
    match = re.search(r"\*\*(.*?)\*\*", response)
    return match.group(1).strip() if match else None


def get_data(question):
    failed_endpoints = []
    for attempt in range(2):
        prompt = build_initial_prompt(
            question) if attempt == 0 else build_alternative_prompt(question, failed_endpoints)
        response_text = query_deepseek_stream(prompt)
        endpoint = extract_endpoint(response_text)

        if not endpoint:
            print("⚠️ Failed to extract endpoint from model response.")
            failed_endpoints.append("Extraction failed")
            continue

        full_url = BASE_URL + endpoint

        try:
            return query_coingecko(full_url)
        except requests.HTTPError as e:
            print(f"⚠️ CoinGecko request error (attempt {attempt+1}): {e}")
            failed_endpoints.append(endpoint)
            if attempt == 0:
                print("🔄 Trying alternative endpoint...")
                time.sleep(1)
            else:
                print("❌ Alternative endpoint also failed.")
    return None


def save_audio_from_replicate(text):
    try:
        # Sanitiza o texto para o modelo TTS não surtar
        sanitized_text = text.replace("\n", " ").strip()
        sanitized_text = re.sub(r"[^\x00-\x7F]+", " ", sanitized_text)

        output_url = replicate.run(
            "adirik/styletts2:989cb5ea6d2401314eb30685740cb9f6fd1c9001b8940659b406f952837ab5ac",
            input={
                "beta": 0.7,
                "seed": 0,
                "text": sanitized_text,
                "alpha": 0.3,
                "diffusion_steps": 10,
                "embedding_scale": 1.5,
            },
        )

        if not output_url:
            print("⚠️ Failed to generate audio.")
            return None

        audio_id = str(uuid.uuid4())
        audio_path = f"static/audio/{audio_id}.wav"

        os.makedirs("static/audio", exist_ok=True)
        audio_data = requests.get(output_url).content
        with open(audio_path, "wb") as f:
            f.write(audio_data)

        return audio_path

    except Exception as e:
        print(f"❌ Erro ao gerar o áudio com o StyleTTS2: {e}")
        return None


def upload_to_cloudinary(audio_path):
    try:
        response = cloudinary.uploader.upload(
            audio_path, resource_type="video")
        return response.get("secure_url")
    except Exception as e:
        print(f"❌ Cloudinary upload failed: {e}")
        return None


def generate_video_with_avatar(audio_url):
    print("🎥 Gerando vídeo animado com fala sincronizada...")

    try:
        output_url = replicate.run(
            "cjwbw/sadtalker:a519cc0cfebaaeade068b23899165a11ec76aaa1d2b313d40d214f204ec957a3",
            input={
                "facerender": "facevid2vid",
                "pose_style": 0,
                "preprocess": "crop",
                "still_mode": True,
                "driven_audio": audio_url,
                "source_image": SADTALKER_IMAGE_URL,
                "use_enhancer": True,
                "use_eyeblink": True,
                "size_of_image": 256,
                "expression_scale": 1
            }
        )

        if not output_url:
            print("⚠️ Falha ao gerar o vídeo.")
            return None

        video_id = str(uuid.uuid4())
        video_path = f"static/video/{video_id}.mp4"

        os.makedirs("static/video", exist_ok=True)
        video_data = requests.get(output_url).content
        with open(video_path, "wb") as f:
            f.write(video_data)

        return video_path

    except Exception as e:
        print(f"❌ Erro ao gerar vídeo no SadTalker: {e}")
        return None


def main():
    print("🚀 Welcome to the Advanced Crypto Consultant with DeepSeek! 🚀\n")

    while True:
        question = input(
            "🪙 What do you want to ask about the crypto world? (type 'exit' to quit)\n👉 ").strip()

        if question.lower() == "exit":
            print("👋 See you next time! Happy investing!")
            break

        print("\n🔍 Querying CoinGecko with DeepSeek help...\n")
        coin_data = get_data(question)

        if coin_data:
            print("\n💬 Generating personalized response:\n")
            final_answer_with_emojis = query_deepseek_stream(
                build_final_prompt(question, coin_data))
            final_answer_clean = remove_emojis(final_answer_with_emojis)

            # debug opcional
            print(f"🧪 Texto enviado para TTS: {final_answer_clean}")

            audio_path = save_audio_from_replicate(final_answer_clean)

            if audio_path:
                public_url = upload_to_cloudinary(audio_path)

                if public_url:
                    video_path = generate_video_with_avatar(public_url)

                    print(final_answer_with_emojis)
                    print(f"\n🔊 Áudio salvo localmente em: {audio_path}")
                    print(f"🌐 URL pública do áudio: {public_url}")

                    if video_path:
                        print(f"🎬 Vídeo gerado e salvo em: {video_path}")
                    else:
                        print("⚠️ Falha ao gerar o vídeo animado.")
                else:
                    print("⚠️ Não foi possível gerar a URL pública do áudio.")
            else:
                print("😕 Audio generation failed, but here's the text:")
                print(final_answer_with_emojis)

            print("\n✅ All done!\n")
        else:
            print("\n😢 Couldn't get the info this time. Try another question!\n")


if __name__ == "__main__":
    main()
