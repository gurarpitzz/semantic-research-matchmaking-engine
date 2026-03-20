from openai import OpenAI
import os

class NLPEngine:
    def __init__(self):
        print("Initializing Cloud NLPEngine (OpenAI)...")
        # Ensure OpenAI API key is available
        api_key = os.getenv("OPENAI_API_KEY", "DUMMY_KEY")
        if api_key == "DUMMY_KEY":
            print("WARNING: OPENAI_API_KEY is not set in environment.")
            
        self.client = OpenAI(api_key=api_key)
        self.model_name = "text-embedding-3-small"
        self.dimensions = 768  # Crucial: Matches your init.sql pgvector(768) schema!

    def encode(self, text):
        if not text or not str(text).strip():
            return None
        response = self.client.embeddings.create(
            input=[text],
            model=self.model_name,
            dimensions=self.dimensions
        )
        return response.data[0].embedding

    def batch_encode(self, texts):
        if not texts:
            return []
            
        valid_texts = [t for t in texts if t and str(t).strip()]
        if not valid_texts:
            return []
            
        response = self.client.embeddings.create(
            input=valid_texts,
            model=self.model_name,
            dimensions=self.dimensions
        )
        return [item.embedding for item in response.data]

# Global engine instance
nlp_engine = NLPEngine()
