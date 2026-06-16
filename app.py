import logging
import asyncio
from datetime import datetime
import urllib.parse
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from groq import AsyncGroq
from curl_cffi import requests
from bs4 import BeautifulSoup
import config

logging.basicConfig(level=logging.INFO)
groq_client = AsyncGroq(api_key=config.GROQ_API_KEY)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

def search_internet(query: str) -> str:
    try:
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return "No search results available."
            
        soup = BeautifulSoup(response.text, "html.parser")
        results = soup.find_all("a", class_="result__snippet")
        
        if not results:
            return "No search results found."
            
        context = ""
        for i, res in enumerate(results[:4], 1):
            title = res.find_previous("a", class_="result__url")
            title_text = title.text.strip() if title else "News"
            context += f"[{i}] {title_text}: {res.text.strip()}\n\n"
            
        return context
    except Exception as e:
        logging.error(f"Search error: {e}")
        return "Search failed."

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я бот-фактчекер.\n\n"
        "Отправь мне текст новости, я проверю её через интернет-поиск и вынесу вердикт."
    )

@dp.message(F.text)
async def check_news(message: Message):
    thinking_msg = await message.answer("🔍 Ищу информацию в интернете...")
    
    loop = asyncio.get_event_loop()
    search_results = await loop.run_in_executor(None, search_internet, message.text)
    
    await thinking_msg.edit_text("🔄 Анализирую факты...")
    
    today = datetime.now().strftime("%d.%m.%Y")
    
    dynamic_prompt = (
        f"Ты — профессиональный эксперт по фактчекингу новостей.\n"
        f"Текущая дата: {today} года.\n\n"
        f"Вот свежие данные из интернета по запросу пользователя:\n"
        f"=== ДАННЫЕ ИЗ СЕТИ ===\n"
        f"{search_results}\n"
        f"=== КОНЕЦ ДАННЫХ ===\n\n"
        f"Сравни запрос пользователя с данными из сети. Объясни, почему это правда или фейк.\n"
        f"В ответе ОБЯЗАТЕЛЬНО начни строго с одного из вердиктов:\n"
        f"🔴 ФЕЙК\n"
        f"🟢 ДОСТОВЕРНАЯ НОВОСТЬ\n"
        f"🟡 НЕОДНОЗНАЧНО (Требует подтверждения)\n\n"
        f"После вердикта напиши краткое объяснение (2-4 предложения) на русском языке."
    )
    
    try:
        chat_completion = await groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": dynamic_prompt},
                {"role": "user", "content": message.text}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.2
        )
        
        bot_response = chat_completion.choices[0].message.content
        await thinking_msg.delete()
        await message.answer(bot_response)
        
    except Exception as e:
        logging.error(f"Groq API error: {e}")
        await thinking_msg.edit_text("❌ Ошибка при генерации ответа.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
