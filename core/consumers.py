# core/consumers.py
import datetime as dt
import json
import random
import re

from channels.generic.websocket import AsyncWebsocketConsumer


class BambiConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def receive(self, text_data=None, bytes_data=None):
        q = (text_data or "").strip()
        await self.send(text_data=json.dumps({"reply": self.simple_reply(q)}))

    def simple_reply(self, q: str) -> str:
        if not q:
            return "Merhaba! Ben Bambi 💖 Bugün sana nasıl yardımcı olabilirim?"
        low = q.lower()
        if any(w in low for w in ["merhaba", "selam", "hi", "hello"]):
            return "Selam tatlım! 💕 Ne konuşmak istersin?"
        if "saat" in low:
            return f"Şu an saat {dt.datetime.now().strftime('%H:%M')}."
        if "yardım" in low or "help" in low:
            return "Kısa komutlar:\n\n• “hakkında”\n• herhangi bir soru 💗"
        if re.search(r"\b(hakkında|about)\b", low):
            return "Bambicim kişisel oyunlu alanım. Bugün basit cevaplar, yarın daha akıllı! ✨"
        return random.choice([
            "Anladım tatlım. Biraz daha açar mısın? 💞",
            "Güzel soru! Birlikte çözelim mi? 💖",
            "Hmm… Biraz daha detay verir misin?"
        ])
