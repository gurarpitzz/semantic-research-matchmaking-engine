from sentence_transformers import SentenceTransformer
import torch

class NLPEngine:
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        print(f"Initializing NLPEngine with {model_name}...")
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model = SentenceTransformer(model_name, device=self.device)
        print("NLPEngine initialized.")

    def encode(self, text):
        if not text:
            return None
        return self.model.encode(text).tolist()

    def batch_encode(self, texts):
        return self.model.encode(texts).tolist()

# Global engine instance
nlp_engine = NLPEngine()
