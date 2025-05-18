import logging
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_random_exponential
from .config import settings
import re

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.API_TIMEOUT
        )
        self.moderation_enabled = settings.CONTENT_MODERATION  # Fixed config→settings

    @retry(stop=stop_after_attempt(3), 
           wait=wait_random_exponential(min=1, max=30))
    async def get_response(self, prompt: str, knowledge: str) -> str:
        """Generate AI response with safety checks"""
        try:
            # Content moderation layer
            if self.moderation_enabled and await self._is_unsafe(prompt):
                return "⚠️ Your request contains inappropriate content."

            # Generate response
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{
                    "role": "system",
                    "content": f"Knowledge Base:\n{knowledge}\n\nRules:\n- Be concise\n- Use only provided information"
                }, {
                    "role": "user",
                    "content": prompt
                }],
                max_tokens=settings.MAX_TOKENS,
                temperature=0.7
            )
            
            return self._sanitize_output(response.choices[0].message.content)

        except Exception as e:
            logger.error(f"AI Service Error: {str(e)}")
            raise

    async def _is_unsafe(self, text: str) -> bool:
        """Check content against OpenAI's moderation API"""
        try:
            result = await self.client.moderations.create(input=text)
            return result.results[0].flagged
        except Exception as e:
            logger.warning(f"Moderation API Error: {str(e)}")
            return False

    def _sanitize_output(self, text: str) -> str:
        """Remove special characters and potential injection attempts"""
        if settings.SANITIZE_INPUT:
            return re.sub(r'[^\w\s.,!?\-@#$%&*()]', '', text).strip()
        return text.strip()
