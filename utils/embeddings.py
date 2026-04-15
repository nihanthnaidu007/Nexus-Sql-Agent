import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))


def embed_text(text: str) -> list:
    text = text.strip()[:20000]
    response = _client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


def embed_batch(texts: list) -> list:
    texts = [t.strip()[:20000] for t in texts]
    response = _client.embeddings.create(
        model="text-embedding-3-small",
        input=texts
    )
    return [item.embedding for item in response.data]
