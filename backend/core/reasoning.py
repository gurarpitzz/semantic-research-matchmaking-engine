from litellm import completion
import os

class ReasoningEngine:
    def __init__(self):
        self.model = os.getenv("LLM_MODEL", "gpt-3.5-turbo") # Or gemini/gemini-pro

    def generate_explanation(self, profile_text, paper_title, paper_abstract):
        prompt = f"""
        You are an expert research matchmaking assistant.
        Given a researcher's interests and a professor's paper, explain in 1-2 concise sentences 
        why this professor is a relevant collaborator.

        Researcher interests: {profile_text}
        
        Professor's Paper Title: {paper_title}
        Professor's Paper Abstract: {paper_abstract}

        Explanation:
        """
        try:
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error generating explanation: {e}")
            return "Relevant due to semantic overlap in research domains."

# Global instance
reasoner = ReasoningEngine()
